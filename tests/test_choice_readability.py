from datetime import datetime
from zoneinfo import ZoneInfo

from hisobdon.conversation import Engine
from hisobdon.db import Store
from hisobdon.ledger import Ledger
from hisobdon.money import money

NOW = datetime(2026, 10, 28, 11, tzinfo=ZoneInfo("Asia/Tashkent"))


def test_long_account_names_and_complete_balances_are_in_message_and_single_column(tmp_path):
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    engine = Engine(s)
    first = "Kundalik xarajatlar uchun asosiy bank kartasi — birinchi hisob"
    second = "Kundalik xarajatlar uchun asosiy bank kartasi — ikkinchi hisob"
    a = ledger.create_account(first, "UZS", 123456789, "2026-10-01", "card")
    b = ledger.create_account(second, "UZS", 987654321, "2026-10-01", "card")
    replies = engine.message("bugun 30500 taksi", 1, NOW)
    reply = replies[0]
    assert first in reply.text and second in reply.text
    assert money(123456789, "UZS") in reply.text and money(987654321, "UZS") in reply.text
    assert all(len(row) == 1 for row in reply.rows)
    callback = next(data for row in reply.rows for label, data in row if second in label)
    engine.callback(callback, NOW)
    assert ledger.balance(a) == 123456789
    assert ledger.balance(b) == 984604321


def test_debt_and_investment_lists_show_full_names_balances_and_single_rows(tmp_path):
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    engine = Engine(s)
    name = "Uzoq nomli hamkor bilan investitsiya va jamg‘arma hisobi"
    ledger.create_account(name, "USD", 12345678, "2026-10-01", "investment")
    reply = engine.message("/investments", 1, NOW)[0]
    assert name in reply.text and money(12345678, "USD") in reply.text
    matches = [row for row in reply.rows if any(name in label for label, _ in row)]
    assert len(matches) == 1 and len(matches[0]) == 1
    assert money(12345678, "USD") in matches[0][0][0]


def test_long_category_name_remains_readable_when_telegram_clips_button(tmp_path):
    s = Store(tmp_path / "db")
    engine = Engine(s)
    label = "Uy uchun ta’mirlash va xo‘jalik mahsulotlari xarajatlari"
    s.conn.execute("INSERT INTO categories VALUES (?,?)", (label, "expense"))
    replies = engine.message("bugun 40000 chiqim", 1, NOW)
    assert label in replies[0].text
    row = next(row for row in replies[0].rows if any(label in text for text, _ in row))
    assert len(row) == 1
