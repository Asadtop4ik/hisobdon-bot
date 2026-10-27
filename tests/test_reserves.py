import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from hisobdon.db import Store
from hisobdon.ledger import Ledger, RuleError
from hisobdon.conversation import Engine
from hisobdon.reports import balance_text, totals

NOW = datetime(2026, 10, 27, 16, tzinfo=ZoneInfo("Asia/Tashkent"))


def click(engine, replies, label):
    options = [(text, data) for reply in replies for row in reply.rows for text, data in row]
    matching = [data for text, data in options if label in text]
    assert matching, f"{label} missing: {[text for text, _ in options]}"
    return engine.callback(matching[0], NOW)


def test_reserve_is_net_worth_not_daily_spending_and_releases_by_transfer(tmp_path):
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    cash = ledger.create_account("Wallet", "USD", 10000, "2026-01-01")
    reserve = ledger.create_account("Home reserve", "USD", 50000, "2026-01-01", is_reserve=True)
    text = balance_text(s)
    assert "Sarflash mumkin: 0 UZS • 100 USD" in text
    assert "Zaxira: 0 UZS • 500 USD" in text
    assert "Sof moliyaviy holat: 0 UZS • 600 USD" in text
    with pytest.raises(RuleError):
        ledger.post(dict(kind="expense", account=reserve, amount=10000, date="2026-01-02"), "direct")
    ledger.post(
        dict(kind="transfer", account=reserve, target=cash, amount=10000, date="2026-01-02"), "release"
    )
    assert ledger.balance(cash) == 20000 and ledger.balance(reserve) == 40000
    assert totals(s, "2026-01-01", "2026-02-01")["USD"]["expense"] == 0
    ledger.post(dict(kind="expense", account=cash, amount=10000, date="2026-01-03"), "spend")
    assert totals(s, "2026-01-01", "2026-02-01")["USD"]["expense"] == 10000


def test_existing_v1_database_migrates_without_changing_balances(tmp_path):
    path = tmp_path / "db"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE accounts(id INTEGER PRIMARY KEY,name TEXT NOT NULL,currency TEXT NOT NULL,kind TEXT NOT NULL,opening INTEGER NOT NULL,opened_on TEXT NOT NULL,due TEXT,archived INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL); PRAGMA user_version=1;"
    )
    conn.execute(
        "INSERT INTO accounts VALUES (1,'Existing','UZS','cash',123456,'2026-01-01',NULL,0,'2026-01-01')"
    )
    conn.commit()
    conn.close()
    s = Store(path)
    assert Ledger(s).balance(1) == 123456
    assert Ledger(s).account(1)["is_reserve"] == 0
    Ledger(s).set_reserve(1, True)
    s.close()
    s = Store(path)
    assert Ledger(s).balance(1) == 123456 and Ledger(s).account(1)["is_reserve"] == 1
    assert s.one("PRAGMA user_version")["user_version"] == 2


def test_reserve_creation_and_existing_account_marker_ui(tmp_path):
    s = Store(tmp_path / "db")
    e = Engine(s)
    replies = e.message("/accounts", 1, NOW)
    replies = click(e, replies, "Hisob qo‘shish")
    replies = click(e, replies, "Zaxira")
    replies = e.message("Uy zaxirasi", 2, NOW)
    replies = click(e, replies, "USD")
    replies = e.message("500", 3, NOW)
    replies = click(e, replies, "Bugun")
    replies = click(e, replies, "Saqlash")
    assert Ledger(s).account(1)["is_reserve"] == 1
    assert "Zaxira" in replies[0].text
    replies = click(e, replies, "Kundalik hisob qilish")
    assert Ledger(s).account(1)["is_reserve"] == 0
    replies = click(e, replies, "Zaxira deb belgilash")
    assert Ledger(s).account(1)["is_reserve"] == 1
    Ledger(s).create_account("Oddiy", "USD", 5000, "2026-10-01")
    replies = e.message("ovqat 10 dollar", 4, NOW)
    labels = [label for reply in replies for row in reply.rows for label, _ in row]
    assert not any("Uy zaxirasi" in label for label in labels)
    assert any("Oddiy" in label for label in labels)


def test_future_schema_is_not_downgraded_and_reserve_cannot_overdraw(tmp_path):
    future = tmp_path / "future.db"
    c = sqlite3.connect(future)
    c.execute("PRAGMA user_version=3")
    c.close()
    with pytest.raises(ValueError):
        Store(future)
    c = sqlite3.connect(future)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 3
    c.close()
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    reserve = ledger.create_account("Reserve", "USD", 100, "2026-01-01", is_reserve=True)
    cash = ledger.create_account("Cash", "USD", 0, "2026-01-01")
    with pytest.raises(RuleError):
        ledger.post(
            dict(
                kind="transfer",
                account=reserve,
                target=cash,
                amount=200,
                date="2026-01-02",
                allow_negative=True,
            ),
            "bad",
        )
    assert ledger.balance(reserve) == 100 and ledger.balance(cash) == 0


@pytest.mark.parametrize("split", [False, True])
def test_marking_reserve_preserves_metadata_corrections_without_new_spending(tmp_path, split):
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    a = ledger.create_account("Cash", "UZS", 10000000, "2026-01-01")
    b = ledger.create_account("Card", "UZS", 10000000, "2026-01-01", "card")
    data = dict(kind="expense", account=a, amount=6000000, date="2026-01-02", category="Ovqat")
    if split:
        data["allocations"] = [{"account": a, "amount": 1700000}, {"account": b, "amount": 4300000}]
    op = ledger.post(data, "expense")
    reserved = b if split else a
    ledger.set_reserve(reserved, True)
    before = [ledger.balance(a), ledger.balance(b)]
    new = ledger.replace(op, {**data, "note": "corrected note", "category": "Boshqa"}, "metadata")
    assert [ledger.balance(a), ledger.balance(b)] == before
    assert s.one("SELECT note FROM operations WHERE id=?", (new,))["note"] == "corrected note"
    with pytest.raises(RuleError):
        ledger.post(data, "new-spending")
    changed = {**data, "amount": 7000000}
    if split:
        changed["allocations"] = [{"account": a, "amount": 1700000}, {"account": b, "amount": 5300000}]
    with pytest.raises(RuleError):
        ledger.replace(new, changed, "more-spending")
    assert [ledger.balance(a), ledger.balance(b)] == before
