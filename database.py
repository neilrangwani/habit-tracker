import os
import random
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

DB_PATH = os.getenv("DB_PATH", "/data/habit_tracker.db" if os.path.isdir("/data") else "habit_tracker.db")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    NOT NULL UNIQUE,
                password   TEXT    NOT NULL,
                habit_name TEXT    NOT NULL DEFAULT 'Habit',
                tz         TEXT    NOT NULL DEFAULT 'UTC'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                logged_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
                user_id   INTEGER REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invites (
                token      TEXT PRIMARY KEY,
                used       INTEGER NOT NULL DEFAULT 0,
                created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
            )
        """)
        # Migration: add user_id to existing logs table if missing
        try:
            conn.execute("ALTER TABLE logs ADD COLUMN user_id INTEGER REFERENCES users(id)")
        except sqlite3.OperationalError:
            pass
        conn.commit()


def create_user(username: str, password_hash: str, habit_name: str = "Habit", tz: str = "UTC") -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password, habit_name, tz) VALUES (?, ?, ?, ?)",
            (username, password_hash, habit_name, tz),
        )
        conn.commit()
        return cur.lastrowid


def create_invite(token: str):
    with _conn() as conn:
        conn.execute("INSERT INTO invites (token) VALUES (?)", (token,))
        conn.commit()


def claim_invite(token: str) -> bool:
    """Mark the invite as used. Returns True if it was valid and unused."""
    with _conn() as conn:
        row = conn.execute("SELECT used FROM invites WHERE token = ?", (token,)).fetchone()
        if not row or row["used"]:
            return False
        conn.execute("UPDATE invites SET used = 1 WHERE token = ?", (token,))
        conn.commit()
        return True


def get_user_by_username(username: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def log_habit(user_id: int):
    with _conn() as conn:
        conn.execute("INSERT INTO logs (user_id) VALUES (?)", (user_id,))
        conn.commit()


def import_csv(rows: list[dict], tz_name: str, user_id: int) -> int:
    tz = ZoneInfo(tz_name)
    records = []
    for row in rows:
        date_str = row["date"].strip()
        count = int(row["count"])
        ts = row.get("timestamp", "").strip()
        if ts:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    dt_local = datetime.strptime(ts, fmt).replace(tzinfo=tz)
                    break
                except ValueError:
                    continue
            else:
                dt_local = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=12, tzinfo=tz)
            records.append((dt_local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), user_id))
        else:
            if count <= 0:
                continue
            start_min, end_min = 9 * 60, 21 * 60
            interval = (end_min - start_min) / count
            for i in range(count):
                h, m = divmod(int(start_min + i * interval), 60)
                dt_local = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=h, minute=m, tzinfo=tz)
                records.append((dt_local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), user_id))
    with _conn() as conn:
        conn.executemany("INSERT INTO logs (logged_at, user_id) VALUES (?, ?)", records)
        conn.commit()
    return len(records)


def clear_logs(user_id: int):
    with _conn() as conn:
        conn.execute("DELETE FROM logs WHERE user_id = ?", (user_id,))
        conn.commit()


_HOUR_WEIGHTS = [0, 0, 0, 0, 0, 1, 2, 5, 8, 4, 3, 3, 6, 4, 3, 3, 4, 5, 8, 7, 4, 2, 1, 0]
# Daily count distribution: range 4-15, peak at 10, realistic (not normal).
# Gradual climb, plateau near peak, longer right tail for high-motivation days.
_DAY_COUNT_WEIGHTS = [2, 5, 7, 10, 12, 14, 15, 13, 9, 6, 3, 2]  # counts 4,5,6,7,8,9,10,11,12,13,14,15


def seed_fake_data(tz_name: str, user_id: int):
    """Seed ~400 days of historical data. Skips if the user already has data."""
    with _conn() as conn:
        existing = conn.execute(
            "SELECT COUNT(*) FROM logs WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    if existing > 0:
        return  # already seeded — don't wipe history on redeploy

    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    records = []
    for days_ago in range(400, -1, -1):
        day = (now - timedelta(days=days_ago)).replace(hour=0, minute=0, second=0, microsecond=0)
        for _ in range(random.choices(range(4, 16), weights=_DAY_COUNT_WEIGHTS)[0]):
            hour = random.choices(range(24), weights=_HOUR_WEIGHTS)[0]
            dt = day.replace(hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59))
            records.append((dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), user_id))
    with _conn() as conn:
        conn.execute("DELETE FROM logs WHERE user_id = ?", (user_id,))
        conn.executemany("INSERT INTO logs (logged_at, user_id) VALUES (?, ?)", records)
        conn.commit()


def keep_demo_current(user_id: int, tz_name: str):
    """Insert today's logs for the demo user if none exist yet for today."""
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    utc_start = today_start.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    utc_end   = tomorrow_start.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with _conn() as conn:
        existing = conn.execute(
            "SELECT COUNT(*) FROM logs WHERE user_id = ? AND logged_at >= ? AND logged_at < ?",
            (user_id, utc_start, utc_end),
        ).fetchone()[0]

    if existing > 0:
        return

    count = random.choices(range(4, 16), weights=_DAY_COUNT_WEIGHTS)[0]
    records = []
    for _ in range(count):
        hour = random.choices(range(24), weights=_HOUR_WEIGHTS)[0]
        dt = today_start.replace(
            hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59)
        )
        records.append((dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), user_id))

    with _conn() as conn:
        conn.executemany("INSERT INTO logs (logged_at, user_id) VALUES (?, ?)", records)
        conn.commit()


def get_analytics(user_id: int, tz_name: str = "UTC") -> dict:
    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()

    with _conn() as conn:
        rows = conn.execute(
            "SELECT logged_at FROM logs WHERE user_id = ? ORDER BY logged_at", (user_id,)
        ).fetchall()
        user = conn.execute("SELECT habit_name FROM users WHERE id = ?", (user_id,)).fetchone()

    habit_name = user["habit_name"] if user else os.getenv("HABIT_NAME", "Habit")

    by_date: dict[date, int] = defaultdict(int)
    by_hour = [0] * 24
    for row in rows:
        dt_utc = datetime.strptime(row["logged_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        dt_local = dt_utc.astimezone(tz)
        by_date[dt_local.date()] += 1
        by_hour[dt_local.hour] += 1

    if not by_date:
        return _empty_analytics(habit_name)

    first_day = min(by_date)

    # Streaks
    start = today if by_date.get(today, 0) > 0 else today - timedelta(days=1)
    current_streak, d = 0, start
    while by_date.get(d, 0) > 0:
        current_streak += 1
        d -= timedelta(days=1)

    longest_streak = streak = 0
    d = first_day
    while d <= today:
        if by_date.get(d, 0) > 0:
            streak += 1
            longest_streak = max(longest_streak, streak)
        else:
            streak = 0
        d += timedelta(days=1)

    best_date = max(by_date, key=lambda x: by_date[x])

    def period_stats(n_days: int) -> dict:
        cur    = sum(by_date.get(today - timedelta(days=i), 0) for i in range(n_days))
        prev   = sum(by_date.get(today - timedelta(days=n_days + i), 0) for i in range(n_days))
        active = sum(1 for i in range(n_days) if by_date.get(today - timedelta(days=i), 0) > 0)
        change = round((cur - prev) / prev * 100, 1) if prev else None
        return {"total": cur, "avg": round(cur / n_days, 1), "days_active": active, "change_pct": change}

    all_days  = (today - first_day).days + 1
    all_total = sum(by_date.values())
    periods   = {
        "week":  period_stats(7),
        "month": period_stats(30),
        "year":  period_stats(365),
        "all":   {"total": all_total, "avg": round(all_total / all_days, 1),
                  "days_active": len(by_date), "change_pct": None},
    }

    heatmap = {
        (today - timedelta(days=i)).isoformat(): by_date.get(today - timedelta(days=i), 0)
        for i in range(364, -1, -1)
    }
    daily = [
        {"date": (today - timedelta(days=364 - i)).isoformat(),
         "count": by_date.get(today - timedelta(days=364 - i), 0)}
        for i in range(365)
    ]

    weekly = []
    for w in range(11, -1, -1):
        week_end   = today - timedelta(weeks=w)
        week_start = week_end - timedelta(days=6)
        weekly.append({"week": week_start.isoformat(),
                        "total": sum(by_date.get(week_start + timedelta(days=j), 0) for j in range(7))})

    monthly = []
    for m in range(11, -1, -1):
        yr, mo = today.year, today.month - m
        while mo <= 0:
            mo += 12
            yr -= 1
        start_m = date(yr, mo, 1)
        end_m   = date(yr + (mo == 12), mo % 12 + 1, 1) - timedelta(days=1)
        monthly.append({"month": f"{yr}-{mo:02d}",
                         "total": sum(by_date.get(start_m + timedelta(days=j), 0)
                                      for j in range((end_m - start_m).days + 1))})

    dow_sum = [0] * 7
    dow_cnt = [0] * 7
    for d, cnt in by_date.items():
        dow_sum[d.weekday()] += cnt
        dow_cnt[d.weekday()] += 1
    by_dow = [round(dow_sum[i] / dow_cnt[i], 1) if dow_cnt[i] else 0 for i in range(7)]

    dist = [0] * 16
    d = first_day
    while d <= today:
        dist[min(by_date.get(d, 0), 15)] += 1
        d += timedelta(days=1)

    return {
        "habit_name":   habit_name,
        "heatmap":      heatmap,
        "streaks":      {"current": current_streak, "longest": longest_streak},
        "best_day":     {"date": best_date.isoformat(), "count": by_date[best_date]},
        "periods":      periods,
        "daily":        daily,
        "weekly":       weekly,
        "monthly":      monthly,
        "by_dow":       by_dow,
        "by_hour":      by_hour,
        "distribution": dist,
    }


def _empty_analytics(habit_name: str = "Habit") -> dict:
    return {
        "habit_name":   habit_name,
        "heatmap":      {},
        "streaks":      {"current": 0, "longest": 0},
        "best_day":     {"date": None, "count": 0},
        "periods":      {k: {"total": 0, "avg": 0.0, "days_active": 0, "change_pct": None}
                         for k in ("week", "month", "year", "all")},
        "daily":        [],
        "weekly":       [],
        "monthly":      [],
        "by_dow":       [0.0] * 7,
        "by_hour":      [0] * 24,
        "distribution": [0] * 12,
    }
