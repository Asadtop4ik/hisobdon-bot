from datetime import datetime
from zoneinfo import ZoneInfo
from hisobdon.db import Store
from hisobdon.ledger import Ledger
from hisobdon.scheduler import due_jobs, mark_sent, mark_failed

TZ = ZoneInfo("Asia/Tashkent")


def test_due_jobs_full_week_month_and_restart_dedup(tmp_path):
    s = Store(tmp_path / "db")
    s.set("activated_on", "2026-09-27")
    now = datetime(2026, 10, 1, 9, 1, tzinfo=TZ)
    jobs = due_jobs(s, now)
    monthly = next(j for j in jobs if j["kind"] == "monthly")
    assert (monthly["start"], monthly["end"]) == ("2026-09-01", "2026-10-01")
    weekly = next(j for j in jobs if j["kind"] == "weekly")
    assert (weekly["start"], weekly["end"]) == ("2026-09-21", "2026-09-28")
    mark_sent(s, monthly["id"], now)
    assert not any(j["id"] == monthly["id"] for j in due_jobs(s, now))


def test_daily_at_22_and_only_latest_missed(tmp_path):
    s = Store(tmp_path / "db")
    s.set("activated_on", "2026-10-20")
    jobs = due_jobs(s, datetime(2026, 10, 27, 21, 59, tzinfo=TZ))
    daily = [j for j in jobs if j["kind"] == "daily"]
    assert len(daily) == 1 and daily[0]["start"] == "2026-10-26"
    jobs = due_jobs(s, datetime(2026, 10, 27, 22, 0, tzinfo=TZ))
    assert [j["start"] for j in jobs if j["kind"] == "daily"] == ["2026-10-27"]


def test_paid_debt_reminder_not_sent_and_failed_job_retries(tmp_path):
    s = Store(tmp_path / "db")
    s.set("activated_on", "2026-10-27")
    ledger = Ledger(s)
    a = ledger.create_account("Cash", "USD", 10000, "2026-10-01")
    d = ledger.create_account("Debt", "USD", 1000, "2026-10-01", "debt_borrowed", "2026-10-27")
    now = datetime(2026, 10, 27, 9, 0, tzinfo=TZ)
    job = next(j for j in due_jobs(s, now) if j["kind"] == "debt")
    mark_failed(s, job["id"], now, "network")
    assert not due_jobs(s, now)
    ledger.post(dict(kind="repay_borrowed", account=a, target=d, amount=1000, date="2026-10-27"), "r")
    assert not any(j["kind"] == "debt" for j in due_jobs(s, datetime(2026, 10, 27, 9, 10, tzinfo=TZ)))
