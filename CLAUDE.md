# CLAUDE.md — Habit Tracker

## What This Is
A self-hosted personal habit tracker with an iPhone Home Screen shortcut integration.
One tap logs a habit with a full UTC timestamp. A web dashboard shows a full year of analytics
including a GitHub-style heatmap, trends, streaks, day-of-week patterns, hour-of-day patterns,
and period-over-period comparisons.

Designed to be cloned and self-hosted per user — no shared infrastructure, no shared auth.

## Stack
- Python 3.10+
- `fastapi` + `uvicorn` — HTTP server + API
- `python-dotenv` — `.env` management
- SQLite — zero-config local database (individual timestamped rows, not pre-aggregated counts)
- Vanilla HTML/CSS/JS + Chart.js — dashboard frontend (no framework, no build step)
- Docker — container build
- Railway — hosting with persistent volume for SQLite

## Running
```bash
pip install -r requirements.txt
python main.py            # live server on http://localhost:8000
python main.py --dry-run  # seeds ~400 days of fake data, no iPhone shortcut needed
```

## Key Files
| File | Purpose |
|---|---|
| `main.py` | FastAPI app — routes, startup, static file serving |
| `database.py` | SQLite init, `log_habit()`, `get_analytics()`, `seed_fake_data()` |
| `static/index.html` | Full analytics dashboard — heatmap, 6 charts, KPI cards, period tabs |
| `railway.toml` | Railway deployment config — Dockerfile builder + persistent volume mount at `/data` |
| `Dockerfile` | Container build |

## Configuration (`.env`)
| Variable | Purpose |
|---|---|
| `HABIT_TRACKER_API_KEY` | Secret token for the `/log` endpoint (put this in the iPhone shortcut) |
| `HABIT_NAME` | Display name for the habit (e.g. `Water`, `Breathing`) |
| `TZ` | Your timezone for day/hour bucketing (e.g. `America/Los_Angeles`) |

Generate an API key: `python -c "import secrets; print(secrets.token_hex(16))"`

## API Endpoints
| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/log` | API key | Insert a timestamped log row |
| `GET` | `/analytics` | None | Full analytics JSON — heatmap, streaks, periods, trends, patterns, distribution |
| `GET` | `/data` | None | Lightweight `{date: count}` for last 365 days (backwards compat) |
| `GET` | `/` | None | Serve dashboard |
| `GET` | `/health` | None | Health check |

Auth: `X-API-Key` header **or** `?api_key=` query param (query param used by iPhone shortcut).

## Analytics JSON shape (`/analytics`)
```json
{
  "habit_name": "Water",
  "heatmap":    { "2026-03-14": 5, ... },
  "streaks":    { "current": 12, "longest": 34 },
  "best_day":   { "date": "2026-01-10", "count": 11 },
  "periods": {
    "week":  { "total": 35, "avg": 5.0, "days_active": 6, "change_pct": 8.5 },
    "month": { ... },
    "year":  { ... },
    "all":   { "total": 2100, "avg": 5.1, "days_active": 365, "change_pct": null }
  },
  "daily":        [ { "date": "2025-03-14", "count": 4 }, ... ],
  "weekly":       [ { "week": "2025-12-30", "total": 32 }, ... ],
  "monthly":      [ { "month": "2025-04", "total": 118 }, ... ],
  "by_dow":       [4.1, 5.8, 5.2, 6.0, 5.9, 7.1, 6.4],
  "by_hour":      [0, 0, 0, 0, 0, 1, 2, 5, 8, 4, ...],
  "distribution": [18, 8, 14, 22, 30, 45, 52, 48, 38, 22, 12, 6]
}
```

## Database schema
```sql
CREATE TABLE logs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);
```
Logs are stored in UTC. All timezone conversion happens at read time in `get_analytics()` using `zoneinfo`.
On Railway, the DB file lives at `/data/habit_tracker.db` (persistent volume). Locally it falls back to `habit_tracker.db`.

## iPhone Shortcut Setup
1. Open the **Shortcuts** app on iPhone
2. Create a new shortcut → add action **"Get Contents of URL"**
3. Set Method: `POST`
4. Set URL: `https://your-app.up.railway.app/log?api_key=YOUR_KEY`
5. Add the shortcut to your Home Screen

## Deployment (Railway)
1. Push repo to GitHub
2. New project at railway.app → Deploy from GitHub repo
3. Set env vars in Railway dashboard: `HABIT_TRACKER_API_KEY`, `HABIT_NAME`, `TZ`
4. Railway provisions a persistent volume at `/data` (defined in `railway.toml`)
5. Generate a public domain under Settings → Networking
6. Paste the URL into the iPhone shortcut

## Secrets (never commit)
| File | Contains |
|---|---|
| `.env` | `HABIT_TRACKER_API_KEY`, `HABIT_NAME`, `TZ` |
| `habit_tracker.db` | SQLite database (auto-created, in `.gitignore`) |
