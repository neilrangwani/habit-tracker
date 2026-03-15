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

## Quick start (local)

**Requirements:** Python 3.10+, pip

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

Copy `.env.example` to `.env` and fill in three values:

| Variable | Description | Example |
|---|---|---|
| `HABIT_TRACKER_API_KEY` | Secret token that protects the `/log` endpoint | `a3f9d2...` |
| `HABIT_NAME` | What you're tracking — shown in the dashboard header | `Water`, `Meditation` |
| `TZ` | Your timezone, used to bucket logs into the correct local day | `America/New_York` |

Generate a secure API key:
```bash
python -c "import secrets; print(secrets.token_hex(16))"
```

A full list of valid timezone strings is available at [this Wikipedia page](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) — use the value in the **TZ identifier** column.

---

## Deploying to Railway

Railway is a cloud hosting platform that builds and runs your container automatically on every push to GitHub. The free trial includes $5 in credits; the Hobby plan is $5/month with $5 in included usage — enough to run this app continuously.

### Step 1 — Fork and push to GitHub

If you cloned this repo directly, push it to your own GitHub account:

```bash
gh repo create habit-tracker --public --source=. --remote=origin --push
```

Or fork it on GitHub and clone your fork.

### Step 2 — Create a Railway account

Go to [railway.app](https://railway.app) and sign up using your GitHub account. This is required so Railway can access your repo.

### Step 3 — Create a new project

1. Click **New Project**
2. Select **Deploy from GitHub repo**
3. If no repos appear, click **Configure GitHub App** and grant Railway access to your `habit-tracker` repo, then click **Refresh**
4. Select `habit-tracker` from the list

Railway will immediately start building the Docker container. This takes 1–2 minutes.

### Step 4 — Add environment variables

While the build runs, go to your service → **Variables** tab and add:

| Variable | Value |
|---|---|
| `HABIT_TRACKER_API_KEY` | Your generated API key (see above) |
| `HABIT_NAME` | e.g. `Water` |
| `TZ` | e.g. `America/New_York` |

Click **Deploy** after adding variables to trigger a fresh build with them applied.

### Step 5 — Generate a public domain

1. Go to your service → **Settings** → **Networking**
2. Click **Generate Domain**
3. When prompted for a port, enter `8080`
4. Railway will assign a URL like `https://habit-tracker-production-xxxx.up.railway.app`

### Step 6 — Verify it's working

Open your Railway URL in a browser. You should see the dashboard. If you see "Application failed to respond", check the **Deployments** tab for error logs.

**Important:** Do not run commands in the Railway shell — this can interfere with the running container and corrupt the database. All admin operations are available through the dashboard's built-in admin panel (⚙ icon).

### Persistent storage

The `railway.toml` in this repo configures a persistent volume mounted at `/data`. This means your SQLite database survives redeploys and container restarts. You do not need to configure this manually — it is set up automatically.

---

## iPhone shortcut setup

One tap on your home screen logs the habit instantly — no app to open.

1. Open the **Shortcuts** app on iPhone
2. Tap **+** to create a new shortcut
3. Tap **Add Action** → search for **Get Contents of URL** → select it
4. Set **URL** to:
   ```
   https://your-app.up.railway.app/log?api_key=YOUR_KEY
   ```
5. Tap **Show More** and set **Method** to `POST`
6. Set **Request Body** to `JSON` (leave the body empty)
7. Tap the shortcut name at the top to rename it (e.g. `Water 💧`)
8. Tap the share icon → **Add to Home Screen**

When you run the shortcut, it should return `{"status": "logged"}`. You can verify by refreshing the dashboard.

---

## Admin panel

Click the **⚙** icon in the top-right corner of the dashboard. You'll be prompted for your API key before any action runs.

| Action | Description |
|---|---|
| **Import CSV** | Upload historical data. Required columns: `date` (YYYY-MM-DD), `count`. Optional: `timestamp` (YYYY-MM-DD HH:MM:SS). If no timestamp, logs are spread evenly through the day. |
| **Seed Historical Data** | Populate with ~1 year of realistic fake data — useful for testing or demos |
| **Clear All Data** | Permanently delete all log entries. Requires typing `CONFIRM`. |

CSV example:
```
date,count
2026-01-01,5
2026-01-02,3
2026-01-03,7
```

---

## API

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/log` | API key | Record a habit log with current timestamp |
| `GET` | `/analytics` | None | Full analytics JSON (heatmap, trends, patterns, streaks) |
| `GET` | `/data` | None | `{date: count}` for last 365 days (lightweight) |
| `POST` | `/admin/import` | API key | Import CSV data |
| `POST` | `/admin/seed` | API key | Seed fake historical data |
| `DELETE` | `/admin/reset` | API key | Delete all logs |
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
