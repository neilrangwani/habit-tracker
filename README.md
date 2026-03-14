# Habit Tracker

A self-hosted habit tracking app with one-tap iPhone logging and a full analytics dashboard. Built to be simple, private, and genuinely useful for building consistent daily routines.

![Dashboard preview](https://raw.githubusercontent.com/neilrangwani/habit-tracker/main/static/preview.png)

---

## What it does

Log any habit — water intake, meditation, exercise, supplements — with a single tap on your iPhone home screen. The dashboard shows a full year of activity and breaks down your patterns so you can actually understand your behavior, not just count streaks.

**Analytics included:**
- GitHub-style activity heatmap (365 days)
- Daily trend with rolling average, filterable by week / month / year / all time
- Period-over-period change (e.g. this month vs last month)
- Average by day of week — see which days you're most consistent
- Average by hour of day — see when you actually do the habit
- Weekly and monthly totals
- Daily distribution — how often you hit 0, 1, 2, 3+ logs in a day
- Current streak, longest streak, best day

---

## Stack

| Layer | Tech | Why |
|---|---|---|
| API | Python + FastAPI | Fast to build, async-ready, automatic OpenAPI docs |
| Database | SQLite | Zero infrastructure, persists individual timestamps for full time-of-day analytics |
| Frontend | Vanilla HTML/CSS/JS + Chart.js | No build step, instant load, full control over design |
| Container | Docker | Consistent deploys anywhere |
| Hosting | Railway | One-click deploys from GitHub, persistent volumes |

No ORM, no frontend framework, no managed database. Everything runs in a single container.

---

## Quick start

```bash
git clone https://github.com/neilrangwani/habit-tracker.git
cd habit-tracker

pip install -r requirements.txt
cp .env.example .env        # fill in your values

python main.py --dry-run    # seeds a year of fake data — no iPhone needed
```

Open [http://localhost:8000](http://localhost:8000).

To run with real data:

```bash
python main.py
```

---

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Description | Example |
|---|---|---|
| `HABIT_TRACKER_API_KEY` | Secret token for the `/log` endpoint | `a3f8...` |
| `HABIT_NAME` | What you're tracking | `Water`, `Meditation` |
| `TZ` | Your timezone (for correct day bucketing) | `America/New_York` |

Generate an API key:
```bash
python -c "import secrets; print(secrets.token_hex(16))"
```

---

## iPhone shortcut setup

One tap on your home screen logs the habit instantly — no app to open.

1. Open the **Shortcuts** app → New Shortcut
2. Add action: **Get Contents of URL**
3. Method: `POST`
4. URL: `https://your-app.up.railway.app/log?api_key=YOUR_KEY`
5. Long-press the shortcut → **Add to Home Screen**

---

## Deployment (Railway)

1. Fork this repo
2. Create a new project at [railway.app](https://railway.app) → **Deploy from GitHub**
3. Add environment variables in the Railway dashboard (`HABIT_TRACKER_API_KEY`, `HABIT_NAME`, `TZ`)
4. Railway auto-provisions a persistent volume (defined in `railway.toml`) so the database survives redeploys
5. Under **Settings → Networking**, generate a public domain
6. Paste that URL into your iPhone shortcut

Every push to `main` triggers an automatic redeploy.

---

## API

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/log` | API key | Record a habit log with current timestamp |
| `GET` | `/analytics` | None | Full analytics JSON (heatmap, trends, patterns, streaks) |
| `GET` | `/data` | None | `{date: count}` for last 365 days (lightweight) |
| `GET` | `/` | None | Dashboard |
| `GET` | `/health` | None | Health check |

Auth via `X-API-Key` header or `?api_key=` query param.

---

## Architecture notes

- Each log is stored as an individual timestamped row, not a pre-aggregated count. This allows all time-of-day and day-of-week analytics to be computed accurately.
- All aggregation happens in `database.py` in a single pass over the log table — no N+1 queries.
- Timezone handling is explicit throughout: logs are stored in UTC and converted to local time at read time using Python's `zoneinfo`.
- The frontend fetches one JSON payload on load and handles all period filtering client-side — no re-fetching on tab switches.

---

## Privacy

This is designed to be self-hosted. Your habit data never leaves your own server. No accounts, no tracking, no third-party services.

---

## License

MIT
