# CLAUDE.md — Habit Tracker

## What This Is
A self-hosted habit tracker with JWT-authenticated multi-user accounts and iPhone Home Screen shortcut integration.
One tap logs a habit with a full UTC timestamp. A web dashboard shows a full year of analytics:
GitHub-style heatmap, daily/weekly/monthly trends, streaks, day-of-week and hour-of-day patterns,
period-over-period comparisons, and daily distribution.

Users sign in with username + password. Each user's data is fully isolated.
The server owner creates accounts via API — no self-registration.

## Stack
- Python 3.10+
- `fastapi` + `uvicorn` — HTTP server + API
- `python-jose` — JWT token creation and verification
- `passlib[bcrypt]` + `bcrypt==4.0.1` — password hashing (bcrypt pinned for passlib compatibility)
- `python-dotenv` — `.env` management
- `python-multipart` — file upload support for CSV import
- SQLite with WAL mode — zero-config local database, concurrent reads, individual timestamped rows
- Vanilla HTML/CSS/JS + Chart.js — dashboard frontend (no framework, no build step)
- Docker — container build
- Railway — hosting with persistent volume for SQLite

## Running
```bash
pip install -r requirements.txt
python main.py            # live server on http://localhost:8000
python main.py --dry-run  # creates demo/demo user and seeds ~400 days of fake data
```

## Key Files
| File | Purpose |
|---|---|
| `main.py` | FastAPI app — routes, JWT auth helpers, startup |
| `database.py` | SQLite init, all DB functions — all scoped to `user_id` |
| `static/index.html` | Analytics dashboard — heatmap, 6 charts, KPI cards, period tabs, admin modal |
| `static/login.html` | Login page — posts to `/auth/login`, stores JWT in localStorage |
| `railway.toml` | Railway deployment config — Dockerfile builder + persistent volume at `/data` |
| `Dockerfile` | Container build |

## Configuration (`.env`)
| Variable | Purpose |
|---|---|
| `HABIT_TRACKER_API_KEY` | Master key for creating user accounts (owner only) |
| `HABIT_NAME` | Default habit name for new users (e.g. `Water`) |
| `TZ` | Default timezone for new users (e.g. `America/Los_Angeles`) |
| `JWT_SECRET` | Secret for signing JWTs (defaults to `HABIT_TRACKER_API_KEY` if unset) |

## Auth Flow
- Users log in at `/login` with username + password → receive a JWT (valid 365 days)
- JWT stored in `localStorage`, sent as `Authorization: Bearer <token>` on all API calls
- `/log` accepts `?token=<jwt>` query param for iPhone shortcut compatibility
- Server owner creates users via `POST /admin/create-user` with `X-API-Key` header
- Response includes `shortcut_token` for the iPhone shortcut URL

## API Endpoints
| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/auth/login` | None | Returns JWT |
| `GET` | `/me` | JWT | Current user info + shortcut token |
| `POST` | `/log` | JWT | Insert a timestamped log row |
| `GET` | `/analytics` | JWT | Full analytics JSON |
| `GET` | `/data` | JWT | Lightweight `{date: count}` for last 365 days |
| `POST` | `/admin/import` | JWT | Import CSV — columns: `date`, `count`, optional `timestamp` |
| `DELETE` | `/admin/reset` | JWT | Delete current user's logs |
| `POST` | `/admin/create-user` | API key | Create a new user account |
| `GET` | `/` | None | Dashboard (redirects to `/login` if no token) |
| `GET` | `/login` | None | Login page |
| `GET` | `/health` | None | Health check |

## Admin Panel
The ⚙ gear icon opens an admin modal (requires being signed in):
- **iPhone Shortcut URL** — shows the user's personal shortcut URL with their token
- **Import Historical Data** — CSV upload, appends to existing data
- **Clear All Data** — deletes the current user's logs, requires typing `CONFIRM`

Do NOT use the Railway shell to run database commands — this can crash the deployment.

## Database Schema
```sql
CREATE TABLE users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT    NOT NULL UNIQUE,
    password   TEXT    NOT NULL,  -- bcrypt hash
    habit_name TEXT    NOT NULL DEFAULT 'Habit',
    tz         TEXT    NOT NULL DEFAULT 'UTC'
);

CREATE TABLE logs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    user_id   INTEGER REFERENCES users(id)
);
```
Logs stored in UTC. Timezone conversion at read time in `get_analytics()` using `zoneinfo`.
WAL mode enabled for concurrent reads.
On Railway: DB at `/data/habit_tracker.db`. Locally: `habit_tracker.db`.

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

## CSV Import Format
```
date,count,timestamp
2026-01-01,5,
2026-01-02,1,2026-01-02 08:30:00
```
- `date`: YYYY-MM-DD (required)
- `count`: integer logs for that day (required)
- `timestamp`: YYYY-MM-DD HH:MM:SS in local time (optional — spread evenly 9am–9pm if omitted)

## iPhone Shortcut Setup
1. Open **Shortcuts** app → tap **+** → Add Action → **Get Contents of URL**
2. Set URL: `https://your-app.up.railway.app/log?token=YOUR_SHORTCUT_TOKEN`
3. Set Method: `POST`, Request Body: `JSON` (empty body)
4. Add to Home Screen

Get your `shortcut_token` from the ⚙ admin panel or from the `POST /admin/create-user` response.

## Deployment (Railway)
1. Push repo to GitHub: `gh repo create habit-tracker --public --source=. --remote=origin --push`
2. railway.app → New Project → Deploy from GitHub repo → select `habit-tracker`
3. Grant Railway access via Configure GitHub App if needed
4. Set env vars: `HABIT_TRACKER_API_KEY`, `HABIT_NAME`, `TZ`, optionally `JWT_SECRET`
5. Settings → Networking → Generate Domain → port `8080`
6. Create your user account via `POST /admin/create-user` with your API key
7. Sign in at the Railway URL, copy your shortcut token from the admin panel

Every push to `main` triggers automatic redeploy.

## Secrets (never commit)
| File | Contains |
|---|---|
| `.env` | `HABIT_TRACKER_API_KEY`, `JWT_SECRET`, `HABIT_NAME`, `TZ` |
| `habit_tracker.db` | SQLite database (auto-created, in `.gitignore`) |
