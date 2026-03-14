# CLAUDE.md — Habit Tracker

## What This Is
A self-hosted personal habit tracker with an iPhone Home Screen shortcut integration.
One tap logs a habit. A web dashboard shows history as a GitHub-style contribution graph.
Designed to be cloned and self-hosted per user — no shared infrastructure, no shared auth.

## Stack
- Python 3.10+
- `fastapi` + `uvicorn` — HTTP server + API
- `python-dotenv` — `.env` management
- SQLite — zero-config local database
- Vanilla HTML/CSS/JS — dashboard frontend (no framework)

## Running
```bash
pip install -r requirements.txt
python main.py            # live server on http://localhost:8000
python main.py --dry-run  # seeds fake data, no iPhone shortcut needed
```

## Key Files
| File | Purpose |
|---|---|
| `main.py` | FastAPI app — routes, startup, static file serving |
| `database.py` | SQLite init, `log_habit()`, `get_counts_by_day()` |
| `static/index.html` | Dashboard — GitHub contribution grid, hover tooltips |
| `railway.toml` | Railway deployment config |
| `Dockerfile` | Container build for Railway/Render |

## Configuration (`.env`)
| Variable | Purpose |
|---|---|
| `HABIT_TRACKER_API_KEY` | Secret token for the `/log` endpoint (put this in the iPhone shortcut) |
| `HABIT_NAME` | Display name for the habit (e.g. `Water`, `Breathing`) |
| `TZ` | Your timezone for day bucketing (e.g. `America/Los_Angeles`) |

Generate an API key: `python -c "import secrets; print(secrets.token_hex(16))"`

## API Endpoints
| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/log` | API key | Increment habit counter |
| `GET` | `/data` | None | Return `{date: count}` for last 365 days |
| `GET` | `/` | None | Serve dashboard |
| `GET` | `/health` | None | Health check |

Auth: `X-API-Key` header **or** `?api_key=` query param (query param is used by iPhone shortcut).

## iPhone Shortcut Setup
1. Open the **Shortcuts** app on iPhone
2. Create a new shortcut → add action **"Get Contents of URL"**
3. Set Method: `POST`
4. Set URL: `https://your-app.up.railway.app/log?api_key=YOUR_KEY`
5. Add the shortcut to your Home Screen

## Deployment (Railway)
1. Fork/clone this repo
2. Copy `.env.example` → `.env`, fill in values
3. Connect repo to [Railway](https://railway.app) or run `railway up`
4. Set the same env vars in the Railway dashboard
5. Copy your Railway URL into the iPhone shortcut

## Secrets (never commit)
| File | Contains |
|---|---|
| `.env` | `HABIT_TRACKER_API_KEY`, `HABIT_NAME`, `TZ` |
| `habit_tracker.db` | SQLite database (auto-created on first run) |
