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
| `database.py` | SQLite init, `log_habit()`, `get_analytics()`, `seed_fake_data()`, `import_csv()`, `clear_logs()` |
| `static/index.html` | Full analytics dashboard — heatmap, 6 charts, KPI cards, period tabs, admin modal |
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
| `POST` | `/admin/import` | API key | Import CSV — columns: `date`, `count`, optional `timestamp` |
| `POST` | `/admin/seed` | API key | Seed ~400 days of fake data |
| `DELETE` | `/admin/reset` | API key | Delete all log rows |
| `GET` | `/` | None | Serve dashboard |
| `GET` | `/health` | None | Health check |

Auth: `X-API-Key` header **or** `?api_key=` query param (query param used by iPhone shortcut).

## Admin Panel
The ⚙ gear icon in the dashboard header opens an admin modal. Requires the API key.
- **Import CSV** — adds historical data without wiping existing logs
- **Seed** — populates with fake data (replaces existing)
- **Clear** — deletes all logs, requires typing `CONFIRM`

Do NOT use the Railway shell to run database commands — this can crash the deployment.

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

## CSV Import format
```
date,count,timestamp
2026-01-01,5,
2026-01-02,1,2026-01-02 08:30:00
```
- `date`: YYYY-MM-DD (required)
- `count`: integer number of logs for that day (required)
- `timestamp`: YYYY-MM-DD HH:MM:SS in local time (optional — if omitted, logs are spread evenly 9am–9pm)
- Import appends to existing data; clear first if you want a clean slate

## iPhone Shortcut Setup
1. Open the **Shortcuts** app on iPhone
2. Tap **+** → Add Action → **Get Contents of URL**
3. Set Method: `POST`
4. Set URL: `https://your-app.up.railway.app/log?api_key=YOUR_KEY`
5. Set Request Body to `JSON` (leave body empty)
6. Add the shortcut to your Home Screen

## Deployment (Railway)
1. Push repo to GitHub (`gh repo create habit-tracker --public --source=. --remote=origin --push`)
2. Go to railway.app → New Project → Deploy from GitHub repo → select `habit-tracker`
3. Grant Railway access to the repo via Configure GitHub App if needed
4. Set env vars in Railway dashboard: `HABIT_TRACKER_API_KEY`, `HABIT_NAME`, `TZ`
5. Go to Settings → Networking → Generate Domain → enter port `8080`
6. Paste the Railway URL into the iPhone shortcut

Railway uses the `Dockerfile` to build and the `railway.toml` to configure the persistent volume at `/data`.
Every push to `main` triggers an automatic redeploy.

## Secrets (never commit)
| File | Contains |
|---|---|
| `.env` | `HABIT_TRACKER_API_KEY`, `HABIT_NAME`, `TZ` |
| `habit_tracker.db` | SQLite database (auto-created, in `.gitignore`) |
