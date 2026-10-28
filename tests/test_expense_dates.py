from datetime import datetime
from zoneinfo import ZoneInfo

from hisobdon.conversation import Engine
from hisobdon.db import Store
from hisobdon.ledger import Ledger

NOW = datetime(2026, 10, 28, 10, tzinfo=ZoneInfo("Asia/Tashkent"))


def click(engine, replies, label):
    choices = [(text, data) for reply in replies for row in reply.rows for text, data in row]
    found = [data for text, data in choices if label in text]
    assert found, f"{label} missing: {[text for text, _ in choices]}"
    return engine.callback(found[0], NOW), found[0]


def setup(tmp_path):
    store = Store(tmp_path / "db")
    engine = Engine(store)
    account = Ledger(store).create_account("Karta", "UZS", 10000000, "2026-10-01", "card")
    return store, engine, account


def test_undated_expense_requires_date_then_saves_yesterday(tmp_path):
    s, e, account = setup(tmp_path)
    replies = e.message("30 500 taksi", 1, NOW)
    assert not s.all("SELECT * FROM operations")
    replies, _ = click(e, replies, "Kecha")
    assert "2026-10-27" in replies[0].text and "30 500" in replies[0].text
    replies, _ = click(e, replies, "Karta")
    assert s.one("SELECT day FROM operations")["day"] == "2026-10-27"
    assert Ledger(s).balance(account) == 6950000


def test_change_date_before_account_choice_invalidates_old_button_and_preserves_input(tmp_path):
    s, e, account = setup(tmp_path)
    replies = e.message("bugun 30 500 taksi", 1, NOW)
    old_account = next(
        data for reply in replies for row in reply.rows for label, data in row if "Karta" in label
    )
    replies, _ = click(e, replies, "Sanani o‘zgartirish")
    replies, _ = click(e, replies, "Boshqa sana")
    s.close()
    s = Store(tmp_path / "db")
    e = Engine(s)
    replies = e.message("25.10.2026", 2, NOW)
    assert "2026-10-25" in replies[0].text
    e.callback(old_account, NOW)
    assert not s.all("SELECT * FROM operations")
    replies, _ = click(e, replies, "Karta")
    op = s.one("SELECT * FROM operations")
    assert (op["day"], op["category"], op["amount"]) == ("2026-10-25", "Transport", 3050000)


def test_explicit_date_is_preserved_and_still_changeable(tmp_path):
    s, e, _ = setup(tmp_path)
    replies = e.message("kecha 30 500 taksi", 1, NOW)
    assert "2026-10-27" in replies[0].text
    replies, _ = click(e, replies, "Sanani o‘zgartirish")
    replies, _ = click(e, replies, "Bugun")
    replies, _ = click(e, replies, "Karta")
    assert s.one("SELECT day FROM operations")["day"] == "2026-10-28"


def test_future_custom_date_cannot_post_and_can_be_corrected(tmp_path):
    s, e, _ = setup(tmp_path)
    replies = e.message("30 500 taksi", 1, NOW)
    replies, _ = click(e, replies, "Boshqa sana")
    e.message("2999-01-01", 2, NOW)
    assert not s.all("SELECT * FROM operations")
    replies = e.message("2026-10-26", 3, NOW)
    replies, _ = click(e, replies, "Karta")
    assert s.one("SELECT day FROM operations")["day"] == "2026-10-26"


def test_legacy_ready_draft_requires_date_before_posting(tmp_path):
    s, e, account = setup(tmp_path)
    did = e.new(
        {
            "mode": "operation",
            "data": {
                "kind": "expense",
                "amount": 3050000,
                "date": "2026-10-28",
                "account": account,
                "category": "Transport",
            },
        }
    )
    replies = e.ask(did, s.draft(did), "confirm", "Old confirmation", [("Saqlash", "save")])
    replies, _ = click(e, replies, "Saqlash")
    assert not s.all("SELECT * FROM operations")
    replies, _ = click(e, replies, "Kecha")
    assert s.one("SELECT day FROM operations")["day"] == "2026-10-27"
