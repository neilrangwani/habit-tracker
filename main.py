import csv
import io
import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import database

load_dotenv()

API_KEY = os.getenv("HABIT_TRACKER_API_KEY", "")
TZ = os.getenv("TZ", "UTC")

app = FastAPI(title="Habit Tracker")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def startup():
    database.init_db()
    if "--dry-run" in sys.argv:
        print("Dry-run mode: seeding fake data…")
        database.seed_fake_data(TZ)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse("static/index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/log")
async def log(request: Request):
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if not API_KEY or key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    database.log_habit()
    return {"status": "logged"}


@app.get("/analytics")
def analytics():
    return JSONResponse(database.get_analytics(TZ))


@app.post("/admin/seed")
async def admin_seed(request: Request):
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if not API_KEY or key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    database.seed_fake_data(TZ)
    return {"status": "seeded"}


@app.post("/admin/import")
async def admin_import(request: Request, file: UploadFile = File(...)):
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if not API_KEY or key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    content = (await file.read()).decode("utf-8-sig")  # strip BOM if present
    reader = csv.DictReader(io.StringIO(content))
    # Normalise header names to lowercase
    rows = [{k.lower(): v for k, v in row.items()} for row in reader]
    if not rows or "date" not in rows[0] or "count" not in rows[0]:
        raise HTTPException(status_code=400, detail="CSV must have 'date' and 'count' columns")
    inserted = database.import_csv(rows, TZ)
    return {"status": "imported", "inserted": inserted}


@app.delete("/admin/reset")
async def admin_reset(request: Request):
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if not API_KEY or key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    database.clear_logs()
    return {"status": "cleared"}


# Backwards-compatible endpoint from CLAUDE.md
@app.get("/data")
def data():
    return database.get_analytics(TZ)["heatmap"]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=False,
    )
