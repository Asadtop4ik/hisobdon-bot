import json
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from .ledger import Ledger

TZ = ZoneInfo("Asia/Tashkent")


def due_jobs(store, now):
    now = now.astimezone(TZ)
    activated = store.get("activated_on")
    if not activated:
        activated = now.date().isoformat()
        store.set("activated_on", activated)
    if not store.get("notifications", True):
        return []
    day = datetime.fromisoformat(activated).date()
    today = now.date()
    latest_daily = today if now.hour >= 22 else today - timedelta(days=1)

    def add(key, kind, start, end, due, data=None):
        if due <= now:
            store.conn.execute(
                "INSERT OR IGNORE INTO jobs(id,kind,start,end,due,data) VALUES (?,?,?,?,?,?)",
                (key, kind, start, end, due.isoformat(), json.dumps(data or {})),
            )

    while day <= today:
        if day == latest_daily:
            add(
                f"daily:{day}",
                "daily",
                day.isoformat(),
                (day + timedelta(days=1)).isoformat(),
                datetime.combine(day, time(22), TZ),
            )
        if day.weekday() == 0:
            add(
                f"weekly:{day}",
                "weekly",
                (day - timedelta(days=7)).isoformat(),
                day.isoformat(),
                datetime.combine(day, time(9), TZ),
            )
        if day.day == 1:
            start = (day - timedelta(days=1)).replace(day=1)
            add(
                f"monthly:{day}",
                "monthly",
                start.isoformat(),
                day.isoformat(),
                datetime.combine(day, time(9), TZ),
            )
        day += timedelta(days=1)
    # Drop superseded daily jobs, including failures; monthly and weekly stay retryable.
    store.conn.execute(
        "UPDATE jobs SET status='superseded' WHERE kind='daily' AND start<? AND status='pending'",
        (latest_daily.isoformat(),),
    )
    ledger = Ledger(store)
    open_debts = {}
    for a in ledger.balances():
        if a["kind"].startswith("debt_") and a["due"] and a["balance"] > 0 and not a["archived"]:
            key = f"debt:{a['id']}:{a['due']}"
            open_debts[key] = a
            add(
                key,
                "debt",
                None,
                None,
                datetime.combine(datetime.fromisoformat(a["due"]).date(), time(9), TZ),
                {"account": a["id"]},
            )
    jobs = store.all(
        "SELECT * FROM jobs WHERE status='pending' AND (next_try IS NULL OR next_try<=?) ORDER BY due,id",
        (now.isoformat(),),
    )
    result = []
    for job in jobs:
        if job["kind"] == "debt" and job["id"] not in open_debts:
            store.conn.execute("UPDATE jobs SET status='superseded' WHERE id=?", (job["id"],))
            continue
        result.append(job)
    return result


def mark_sent(store, job_id, now):
    store.conn.execute(
        "UPDATE jobs SET status='sent',sent_at=?,error=NULL WHERE id=?", (now.isoformat(), job_id)
    )


def mark_failed(store, job_id, now, error):
    row = store.one("SELECT attempts FROM jobs WHERE id=?", (job_id,))
    wait = min(3600, 30 * 2 ** min(row["attempts"], 7))
    store.conn.execute(
        "UPDATE jobs SET attempts=attempts+1,next_try=?,error=? WHERE id=?",
        ((now + timedelta(seconds=wait)).isoformat(), str(error)[:120], job_id),
    )
