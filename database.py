import os
import random
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DB_PATH = os.getenv("DB_PATH", "/data/habit_tracker.db" if os.path.isdir("/data") else "habit_tracker.db")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                logged_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
            )
        """)
        conn.commit()


def log_habit():
    with _conn() as conn:
        conn.execute("INSERT INTO logs DEFAULT VALUES")
        conn.commit()


def seed_fake_data(tz_name: str = "UTC"):
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    hour_weights = [0, 0, 0, 0, 0, 1, 2, 5, 8, 4, 3, 3,
                    6, 4, 3, 3, 4, 5, 8, 7, 4, 2, 1, 0]
    records = []
    for days_ago in range(400, -1, -1):
        day = (now - timedelta(days=days_ago)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # Last 14 days always have logs to maintain a current streak
        if days_ago > 14 and random.random() < 0.15:
            continue
        for _ in range(random.randint(3, 9)):
            hour = random.choices(range(24), weights=hour_weights)[0]
            dt = day.replace(
                hour=hour,
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
            )
            records.append((dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),))

    with _conn() as conn:
        conn.execute("DELETE FROM logs")
        conn.executemany("INSERT INTO logs (logged_at) VALUES (?)", records)
        conn.commit()


def get_analytics(tz_name: str = "UTC") -> dict:
    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()

    with _conn() as conn:
        rows = conn.execute("SELECT logged_at FROM logs ORDER BY logged_at").fetchall()

    # ── aggregate by local date and hour ──────────────────
    by_date: dict[date, int] = defaultdict(int)
    by_hour = [0] * 24

    for row in rows:
        dt_utc = datetime.strptime(row["logged_at"], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        dt_local = dt_utc.astimezone(tz)
        by_date[dt_local.date()] += 1
        by_hour[dt_local.hour] += 1

    if not by_date:
        return _empty_analytics()

    first_day = min(by_date)

    # ── streaks ───────────────────────────────────────────
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

    # ── best day ──────────────────────────────────────────
    best_date = max(by_date, key=lambda x: by_date[x])

    # ── period stats ──────────────────────────────────────
    def period_stats(n_days: int) -> dict:
        cur = sum(by_date.get(today - timedelta(days=i), 0) for i in range(n_days))
        prev = sum(by_date.get(today - timedelta(days=n_days + i), 0) for i in range(n_days))
        active = sum(1 for i in range(n_days) if by_date.get(today - timedelta(days=i), 0) > 0)
        change = round((cur - prev) / prev * 100, 1) if prev else None
        return {"total": cur, "avg": round(cur / n_days, 1), "days_active": active, "change_pct": change}

    all_days = (today - first_day).days + 1
    all_total = sum(by_date.values())

    periods = {
        "week":  period_stats(7),
        "month": period_stats(30),
        "year":  period_stats(365),
        "all": {
            "total": all_total,
            "avg": round(all_total / all_days, 1),
            "days_active": len(by_date),
            "change_pct": None,
        },
    }

    # ── heatmap (last 365 days) ───────────────────────────
    heatmap = {
        (today - timedelta(days=i)).isoformat(): by_date.get(today - timedelta(days=i), 0)
        for i in range(364, -1, -1)
    }

    # ── daily trend (last 365 days) ───────────────────────
    daily = [
        {
            "date": (today - timedelta(days=364 - i)).isoformat(),
            "count": by_date.get(today - timedelta(days=364 - i), 0),
        }
        for i in range(365)
    ]

    # ── weekly totals (last 12 weeks) ─────────────────────
    weekly = []
    for w in range(11, -1, -1):
        week_end = today - timedelta(weeks=w)
        week_start = week_end - timedelta(days=6)
        total = sum(by_date.get(week_start + timedelta(days=j), 0) for j in range(7))
        weekly.append({"week": week_start.isoformat(), "total": total})

    # ── monthly totals (last 12 months) ───────────────────
    monthly = []
    for m in range(11, -1, -1):
        yr, mo = today.year, today.month - m
        while mo <= 0:
            mo += 12
            yr -= 1
        start_m = date(yr, mo, 1)
        next_mo = mo % 12 + 1
        next_yr = yr + (mo == 12)
        end_m = date(next_yr, next_mo, 1) - timedelta(days=1)
        total = sum(
            by_date.get(start_m + timedelta(days=j), 0)
            for j in range((end_m - start_m).days + 1)
        )
        monthly.append({"month": f"{yr}-{mo:02d}", "total": total})

    # ── by day of week (Mon=0, Sun=6) ─────────────────────
    dow_sum = [0] * 7
    dow_cnt = [0] * 7
    for d, cnt in by_date.items():
        dow_sum[d.weekday()] += cnt
        dow_cnt[d.weekday()] += 1
    by_dow = [
        round(dow_sum[i] / dow_cnt[i], 1) if dow_cnt[i] else 0
        for i in range(7)
    ]

    # ── distribution (0–10, 11+) ──────────────────────────
    dist = [0] * 12
    d = first_day
    while d <= today:
        dist[min(by_date.get(d, 0), 11)] += 1
        d += timedelta(days=1)

    return {
        "habit_name":   os.getenv("HABIT_NAME", "Habit"),
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


def _empty_analytics() -> dict:
    return {
        "habit_name":   os.getenv("HABIT_NAME", "Habit"),
        "heatmap":      {},
        "streaks":      {"current": 0, "longest": 0},
        "best_day":     {"date": None, "count": 0},
        "periods":      {
            k: {"total": 0, "avg": 0.0, "days_active": 0, "change_pct": None}
            for k in ("week", "month", "year", "all")
        },
        "daily":        [],
        "weekly":       [],
        "monthly":      [],
        "by_dow":       [0.0] * 7,
        "by_hour":      [0] * 24,
        "distribution": [0] * 12,
    }
