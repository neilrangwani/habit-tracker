import asyncio
import csv
import io
import os
import secrets
import sys
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from passlib.context import CryptContext

import database

load_dotenv()

API_KEY    = os.getenv("HABIT_TRACKER_API_KEY", "")
TZ         = os.getenv("TZ", "UTC")
JWT_SECRET = os.getenv("JWT_SECRET", API_KEY) or "change-me-please"
ALGORITHM  = "HS256"
TOKEN_DAYS = 365  # long-lived so iPhone shortcuts don't expire

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="Habit Tracker")
app.mount("/static", StaticFiles(directory="static"), name="static")


_demo_task = None  # hold reference so asyncio doesn't GC it


async def _demo_refresh_loop(user_id: int, tz_name: str):
    """Hourly background task: fill in today's demo logs if missing."""
    while True:
        await asyncio.sleep(3600)
        try:
            database.keep_demo_current(user_id, tz_name)
        except Exception as e:
            print(f"Demo refresh error: {e}")


# ── Startup ───────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    global _demo_task
    database.init_db()
    if "--dry-run" in sys.argv:
        user = database.get_user_by_username("demo")
        if not user:
            print("Dry-run: creating demo user and seeding data…")
            ph  = pwd_context.hash("demo")
            uid = database.create_user("demo", ph, os.getenv("HABIT_NAME", "Water"), TZ)
            database.seed_fake_data(TZ, uid)
        else:
            uid = user["id"]
            print("Dry-run: demo user already exists, skipping seed.")
        database.keep_demo_current(uid, TZ)
        _demo_task = asyncio.create_task(_demo_refresh_loop(uid, TZ))


# ── Auth helpers ──────────────────────────────────────────────
def create_access_token(user_id: int, username: str) -> str:
    exp = datetime.utcnow() + timedelta(days=TOKEN_DAYS)
    return jwt.encode({"sub": str(user_id), "username": username, "exp": exp},
                      JWT_SECRET, algorithm=ALGORITHM)


def get_current_user(request: Request) -> dict:
    auth  = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")
    user = database.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_admin_key(request: Request):
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if not API_KEY or key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def require_not_demo(user: dict):
    if user["username"] == "demo":
        raise HTTPException(status_code=403, detail="Demo account is read-only")


# ── Static pages ──────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def index():
    return FileResponse("static/index.html")


@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse("static/login.html")


@app.get("/register", include_in_schema=False)
def register_page():
    return FileResponse("static/register.html")


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Auth ──────────────────────────────────────────────────────
@app.post("/auth/register")
async def register(request: Request):
    body       = await request.json()
    invite     = body.get("invite", "").strip()
    username   = body.get("username", "").strip()
    password   = body.get("password", "")
    habit_name = (body.get("habit_name") or "").strip() or os.getenv("HABIT_NAME", "Habit")
    tz         = body.get("tz", TZ)
    if not invite:
        raise HTTPException(status_code=400, detail="Invite token required")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if database.get_user_by_username(username):
        raise HTTPException(status_code=409, detail="Username already taken")
    if not database.claim_invite(invite):
        raise HTTPException(status_code=400, detail="Invalid or already-used invite link")
    uid   = database.create_user(username, pwd_context.hash(password), habit_name, tz)
    token = create_access_token(uid, username)
    return {"token": token, "username": username}


@app.post("/auth/login")
async def login(request: Request):
    body     = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "")
    user     = database.get_user_by_username(username)
    if not user or not pwd_context.verify(password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(user["id"], user["username"])
    return {"token": token, "username": user["username"]}


@app.get("/me")
def me(request: Request):
    token = (request.headers.get("Authorization", "")[7:] or
             request.query_params.get("token", ""))
    user  = get_current_user(request)
    return {"username": user["username"], "habit_name": user["habit_name"],
            "tz": user["tz"], "shortcut_token": token}


# ── Habit logging ─────────────────────────────────────────────
@app.post("/log")
async def log(request: Request):
    user = get_current_user(request)
    require_not_demo(user)
    database.log_habit(user["id"])
    return {"status": "logged"}


# ── Analytics ─────────────────────────────────────────────────
@app.get("/analytics")
def analytics(request: Request):
    user = get_current_user(request)
    return JSONResponse(database.get_analytics(user["id"], user["tz"]))


@app.get("/data")
def data(request: Request):
    user = get_current_user(request)
    return database.get_analytics(user["id"], user["tz"])["heatmap"]


# ── Admin: per-user data ──────────────────────────────────────
@app.post("/admin/import")
async def admin_import(request: Request, file: UploadFile = File(...)):
    user    = get_current_user(request)
    require_not_demo(user)
    content = (await file.read()).decode("utf-8-sig")
    reader  = csv.DictReader(io.StringIO(content))
    rows    = [{k.lower(): v for k, v in row.items()} for row in reader]
    if not rows or "date" not in rows[0] or "count" not in rows[0]:
        raise HTTPException(status_code=400, detail="CSV must have 'date' and 'count' columns")
    inserted = database.import_csv(rows, user["tz"], user["id"])
    return {"status": "imported", "inserted": inserted}


@app.delete("/admin/reset")
async def admin_reset(request: Request):
    user = get_current_user(request)
    require_not_demo(user)
    database.clear_logs(user["id"])
    return {"status": "cleared"}


# ── Admin: user management (owner only) ──────────────────────
@app.post("/admin/create-invite")
async def admin_create_invite(request: Request):
    require_admin_key(request)
    token    = secrets.token_urlsafe(32)
    database.create_invite(token)
    base_url = str(request.base_url).rstrip("/")
    return {"invite_url": f"{base_url}/register?invite={token}"}


@app.post("/admin/create-user")
async def admin_create_user(request: Request):
    require_admin_key(request)
    body       = await request.json()
    username   = body.get("username", "").strip()
    password   = body.get("password", "")
    habit_name = body.get("habit_name", os.getenv("HABIT_NAME", "Habit"))
    tz         = body.get("tz", TZ)
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")
    if database.get_user_by_username(username):
        raise HTTPException(status_code=409, detail="Username already exists")
    uid   = database.create_user(username, pwd_context.hash(password), habit_name, tz)
    token = create_access_token(uid, username)
    return {"user_id": uid, "username": username, "shortcut_token": token}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)
