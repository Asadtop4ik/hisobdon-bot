import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from hisobdon.db import Store
from hisobdon.ledger import Ledger
from hisobdon.conversation import Engine

NOW = datetime(2026, 10, 27, 14, 0, tzinfo=ZoneInfo("Asia/Tashkent"))


def pick(engine, replies, label):
    options = [(text, data) for reply in replies for row in reply.rows for text, data in row]
    callback = next(data for text, data in options if label in text)
    return engine.callback(callback, NOW), callback


def test_expense_with_account_button_and_duplicate(tmp_path):
    s = Store(tmp_path / "db")
    a = Ledger(s).create_account("Humo", "UZS", 10000000, "2026-10-01", "card")
    engine = Engine(s)
    replies = engine.message("bugun ovqat abetga 40ming so‘m", 1, NOW)
    replies, callback = pick(engine, replies, "Humo")
    assert "Saqlandi" in replies[0].text
    assert Ledger(s).balance(a) == 6000000
    engine.callback(callback, NOW)
    assert Ledger(s).balance(a) == 6000000
    replies, _ = pick(engine, replies, "Bekor qilish")
    replies, _ = pick(engine, replies, "Ha, bekor")
    assert Ledger(s).balance(a) == 10000000


def test_account_creation_survives_restart(tmp_path):
    path = tmp_path / "db"
    s = Store(path)
    e = Engine(s)
    replies = e.message("/accounts", 1, NOW)
    replies, _ = pick(e, replies, "Hisob qo‘shish")
    replies, _ = pick(e, replies, "Naqd")
    replies = e.message("Hamyon", 2, NOW)
    replies, _ = pick(e, replies, "USD")
    s.close()
    s = Store(path)
    e = Engine(s)
    replies = e.message("100", 3, NOW)
    replies, _ = pick(e, replies, "Bugun")
    replies, _ = pick(e, replies, "Saqlash")
    assert Ledger(s).balances()[0]["balance"] == 10000
    assert Ledger(s).balances()[0]["currency"] == "USD"


def test_unknown_input_requires_type_and_category(tmp_path):
    s = Store(tmp_path / "db")
    e = Engine(s)
    Ledger(s).create_account("Naqd", "UZS", 10000000, "2026-10-01")
    replies = e.message("40000", 1, NOW)
    replies, _ = pick(e, replies, "Chiqim")
    replies, _ = pick(e, replies, "Ovqat")
    replies, _ = pick(e, replies, "Naqd")
    assert Ledger(s).balances()[0]["balance"] == 6000000


@pytest.mark.parametrize(
    "kind,entity_kind,amount,expected_cash,expected_entity",
    [
        ("lend", "debt_lent", "20", 8000, 7000),
        ("borrow", "debt_borrowed", "20", 12000, 7000),
        ("repay_lent", "debt_lent", "20", 12000, 3000),
        ("repay_borrowed", "debt_borrowed", "20", 8000, 3000),
        ("invest", "investment", "20", 8000, 7000),
        ("withdraw", "investment", "20", 12000, 3000),
    ],
)
def test_complex_operation_end_to_end(tmp_path, kind, entity_kind, amount, expected_cash, expected_entity):
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    e = Engine(s)
    cash = ledger.create_account("Hamyon", "USD", 10000, "2026-10-01")
    ent = ledger.create_account("Tegishli", "USD", 5000, "2026-10-01", entity_kind)
    replies = e.callback("op:" + kind, NOW)
    replies = e.message(amount, 1, NOW)
    replies, _ = pick(e, replies, "Hamyon")
    replies, _ = pick(e, replies, "Tegishli")
    replies, _ = pick(e, replies, "Saqlash")
    assert "Saqlandi" in replies[0].text
    assert ledger.balance(cash) == expected_cash
    assert ledger.balance(ent) == expected_entity


def test_exchange_with_commission_and_retained_profit(tmp_path):
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    e = Engine(s)
    uzs = ledger.create_account("So‘m", "UZS", 200000000, "2026-10-01")
    usd = ledger.create_account("Dollar", "USD", 0, "2026-10-01")
    e.callback("op:exchange", NOW)
    replies = e.message("1280000", 1, NOW)
    replies, _ = pick(e, replies, "So‘m")
    replies, _ = pick(e, replies, "Dollar")
    replies = e.message("100", 2, NOW)
    replies = e.message("1000", 3, NOW)
    replies, _ = pick(e, replies, "Saqlash")
    assert ledger.balance(uzs) == 71900000
    assert ledger.balance(usd) == 10000
    inv = ledger.create_account("Invest", "USD", 10000, "2026-10-01", "investment")
    e.callback("op:invest_income", NOW)
    replies = e.message("10", 4, NOW)
    replies, _ = pick(e, replies, "Invest")
    replies, _ = pick(e, replies, "ichida")
    replies, _ = pick(e, replies, "Saqlash")
    assert ledger.balance(inv) == 11000


def test_export_request_is_deferred_outside_write_transaction(tmp_path):
    s = Store(tmp_path / "db")
    e = Engine(s)
    with s.transaction():
        replies = e.callback("m:export_month", NOW)
    assert replies[0].export_range == ("2026-10-01", "2026-10-28")
