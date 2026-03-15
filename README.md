# Habit Tracker

A self-hosted habit tracking platform with multi-user accounts, one-tap iPhone logging, and a full analytics dashboard. Deploy it once, create accounts for yourself and your friends, and everyone tracks their own habit privately on a shared server.

![Dashboard preview](https://raw.githubusercontent.com/neilrangwani/habit-tracker/main/static/preview.png)

---

## What it does

**For users:** log any habit — water intake, meditation, exercise, supplements — with a single tap on your iPhone home screen. Sign in to a personal dashboard that shows a full year of activity and breaks down your patterns so you can actually understand your behavior, not just count streaks.

**For the server owner:** deploy once to Railway, create accounts for anyone you want via a simple API call, and each person gets their own login, isolated data, and a personal iPhone shortcut URL. No self-registration, no user management UI — just one curl command per person.

**Analytics per user:**
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
| Auth | JWT (python-jose) + bcrypt (passlib) | Stateless, secure, works for iPhone shortcut URLs |
| Database | SQLite with WAL mode | Zero infrastructure, concurrent reads, persists individual timestamps |
| Frontend | Vanilla HTML/CSS/JS + Chart.js | No build step, instant load, full control over design |
| Container | Docker | Consistent deploys anywhere |
| Hosting | Railway | One-click deploys from GitHub, persistent volumes |

No ORM, no frontend framework, no managed database. Everything runs in a single container.

---

## Local development

**Requirements:** Python 3.10+, pip

```bash
git clone https://github.com/neilrangwani/habit-tracker.git
cd habit-tracker

pip install -r requirements.txt
cp .env.example .env        # fill in your values

python main.py --dry-run    # creates a demo/demo account and seeds a year of fake data
```

Open [http://localhost:8000](http://localhost:8000) and sign in with `demo` / `demo`.

---

## Configuration

These are server-level settings, set once at deploy time. Per-user settings (habit name, timezone) are specified when creating each account.

Copy `.env.example` to `.env`:

| Variable | Description | Example |
|---|---|---|
| `HABIT_TRACKER_API_KEY` | Master key — only you have this. Used to create user accounts. | `a3f9d2...` |
| `HABIT_NAME` | Default habit name assigned to new users | `Water` |
| `TZ` | Default timezone assigned to new users | `America/New_York` |
| `JWT_SECRET` | Secret used to sign JWT tokens (defaults to `HABIT_TRACKER_API_KEY` if unset) | `s3cr3t...` |

Generate secure secrets:
```bash
python -c "import secrets; print(secrets.token_hex(16))"
```

Valid timezone strings: [TZ database names on Wikipedia](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) — use the **TZ identifier** column.

---

## Deploying to Railway

Railway builds and runs your container automatically on every push to GitHub. The Hobby plan is $5/month with $5 in included usage — enough to run this app continuously.

### Step 1 — Push to GitHub

```bash
gh repo create habit-tracker --public --source=. --remote=origin --push
```

Or fork this repo and clone your fork.

### Step 2 — Create a Railway account

Go to [railway.app](https://railway.app) and sign up with your GitHub account.

### Step 3 — Create a new project

1. Click **New Project** → **Deploy from GitHub repo**
2. If no repos appear, click **Configure GitHub App**, grant access to `habit-tracker`, then click **Refresh**
3. Select `habit-tracker` — Railway starts building immediately (1–2 min)

### Step 4 — Add environment variables

Go to your service → **Variables** tab and add:

| Variable | Value |
|---|---|
| `HABIT_TRACKER_API_KEY` | Your generated key |
| `HABIT_NAME` | e.g. `Water` |
| `TZ` | e.g. `America/New_York` |
| `JWT_SECRET` | Another random secret (or omit to reuse `HABIT_TRACKER_API_KEY`) |

Click **Deploy** after adding variables.

### Step 5 — Generate a public domain

1. Go to **Settings** → **Networking** → **Generate Domain**
2. Enter port `8080`
3. Railway assigns a URL like `https://habit-tracker-production-xxxx.up.railway.app`

### Step 6 — Create user accounts

Create your own account:

```bash
curl -X POST https://YOUR-APP.up.railway.app/admin/create-user \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"username":"neil","password":"yourpassword","habit_name":"Water","tz":"America/New_York"}'
```

To add a friend, run the same command with their details:

```bash
curl -X POST https://YOUR-APP.up.railway.app/admin/create-user \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"alicepassword","habit_name":"Meditation","tz":"America/Los_Angeles"}'
```

Each response includes a `shortcut_token` unique to that user. Share their login URL (`https://YOUR-APP.up.railway.app/login`) and credentials with them — they log in, see only their own data, and can set up their own iPhone shortcut from the ⚙ admin panel.

### Step 7 — Verify

Open your Railway URL, sign in, and you should see the dashboard.

**Important:** Do not run commands in the Railway shell — it can interfere with the running container and corrupt the database. All admin operations are available through the dashboard's ⚙ admin panel.

### Persistent storage

The `railway.toml` configures a persistent volume at `/data`. Your SQLite database survives redeploys and container restarts automatically.

---

## iPhone shortcut setup

One tap on your home screen logs the habit instantly — no app to open.

1. Open the **Shortcuts** app on iPhone
2. Tap **+** → **Add Action** → search for **Get Contents of URL** → select it
3. Set **URL** to:
   ```
   https://your-app.up.railway.app/log?token=YOUR_SHORTCUT_TOKEN
   ```
   Use the `shortcut_token` from the create-user response, or copy it from the ⚙ admin panel in the dashboard.
4. Tap **Show More** and set **Method** to `POST`
5. Set **Request Body** to `JSON` (leave the body empty)
6. Tap the shortcut name to rename it (e.g. `Water 💧`)
7. Tap the share icon → **Add to Home Screen**

When you run the shortcut, it returns `{"status":"logged"}`. Refresh the dashboard to confirm.

---

## Admin panel

Click the **⚙** icon in the dashboard header. You must be signed in.

| Action | Description |
|---|---|
| **iPhone Shortcut URL** | Your personal shortcut URL with token — copy and paste into the Shortcuts app |
| **Import Historical Data** | Upload a CSV of past logs. Required: `date` (YYYY-MM-DD), `count`. Optional: `timestamp` (YYYY-MM-DD HH:MM:SS). If no timestamp, logs are spread evenly 9am–9pm. |
| **Clear All Data** | Permanently deletes your logs. Requires typing `CONFIRM`. |

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
| `POST` | `/auth/login` | None | Returns a JWT token |
| `GET` | `/me` | JWT | Current user info + shortcut token |
| `POST` | `/log` | JWT | Record a habit log |
| `GET` | `/analytics` | JWT | Full analytics JSON |
| `GET` | `/data` | JWT | `{date: count}` for last 365 days |
| `POST` | `/admin/import` | JWT | Import CSV data |
| `DELETE` | `/admin/reset` | JWT | Delete your logs |
| `POST` | `/admin/create-user` | API key | Create a new user account |
| `GET` | `/health` | None | Health check |

JWT auth: `Authorization: Bearer <token>` header or `?token=<token>` query param.
API key auth: `X-API-Key` header or `?api_key=` query param (owner operations only).

---

## Architecture notes

- Each log is stored as an individual timestamped row (not a pre-aggregated count), enabling accurate time-of-day and day-of-week analytics.
- All aggregation runs in a single pass over the filtered log table — no N+1 queries.
- Logs are stored in UTC and converted to local time at read time using Python's `zoneinfo`.
- JWT tokens are long-lived (365 days) so iPhone shortcuts don't expire unexpectedly.
- WAL mode is enabled on SQLite to support concurrent reads from multiple users without locking.
- The frontend fetches one JSON payload on load and handles all period filtering client-side — no re-fetching on tab switches.

---

## Privacy

Self-hosted. All habit data lives on your own server — no third-party analytics, no tracking, no external services. Each user's data is fully isolated; no user can see another's logs.

---

## License

MIT
