from datetime import datetime
from zoneinfo import ZoneInfo

from hisobdon.conversation import Engine
from hisobdon.db import Store
from hisobdon.ledger import Ledger
from hisobdon.reports import totals

NOW = datetime(2026, 10, 27, 16, tzinfo=ZoneInfo("Asia/Tashkent"))


def click(engine, replies, label):
    options = [(text, data) for reply in replies for row in reply.rows for text, data in row]
    found = [data for text, data in options if label in text]
    assert found, f"Missing {label}: {[text for text, _ in options]}"
    return engine.callback(found[0], NOW), found[0]


def setup(tmp_path, kind="debt_lent"):
    store = Store(tmp_path / "db")
    ledger = Ledger(store)
    engine = Engine(store)
    card = ledger.create_account("Karta", "UZS", 20000000, "2026-10-01", "card")
    cash = ledger.create_account("Naqd", "UZS", 0, "2026-10-01")
    debt = ledger.create_account("Sinov qarzi", "UZS", 10000000, "2026-10-01", kind)
    return store, ledger, engine, card, cash, debt


def test_partial_then_full_return_to_card_and_cash_closes_but_keeps_history(tmp_path):
    store, ledger, engine, card, cash, debt = setup(tmp_path)
    replies = engine.message("/debts", 1, NOW)
    replies, _ = click(engine, replies, "Sinov qarzi")
    replies, _ = click(engine, replies, "Qaytarilgan pulni kiritish")
    replies, _ = click(engine, replies, "Qisman")
    replies = engine.message("40000", 2, NOW)
    assert "qayerga tushdi" in replies[0].text.lower()
    replies, _ = click(engine, replies, "Karta")
    replies, confirm = click(engine, replies, "Saqlash")
    assert ledger.balance(card) == 24000000
    assert ledger.balance(debt) == 6000000
    assert "60 000 UZS" in replies[0].text
    engine.callback(confirm, NOW)
    assert ledger.balance(card) == 24000000
    replies = engine.callback(f"a:{debt}", NOW)
    replies, _ = click(engine, replies, "Qaytarilgan pulni kiritish")
    replies, _ = click(engine, replies, "To‘liq")
    replies, _ = click(engine, replies, "Naqd")
    replies, _ = click(engine, replies, "Saqlash")
    assert ledger.balance(cash) == 6000000 and ledger.balance(debt) == 0
    assert "to‘liq yopildi" in replies[0].text
    active = engine.message("/debts", 3, NOW)
    assert not any(data == f"a:{debt}" for r in active for row in r.rows for _, data in row)
    closed, _ = click(engine, active, "Yopilgan qarzlar")
    closed, _ = click(engine, closed, "Sinov qarzi")
    assert "Yopilgan" in closed[0].text
    assert len(store.all("SELECT * FROM operations")) == 2
    assert totals(store, "2026-10-01", "2026-11-01")["UZS"]["income"] == 0
    last = store.one("SELECT MAX(id) AS id FROM operations")["id"]
    ledger.cancel(last)
    assert ledger.balance(debt) == 6000000
    active = engine.message("/debts", 4, NOW)
    assert any(data == f"a:{debt}" for r in active for row in r.rows for _, data in row)


def test_borrowed_debt_full_repayment_debits_selected_card(tmp_path):
    _, ledger, engine, card, _, debt = setup(tmp_path, "debt_borrowed")
    replies = engine.callback(f"a:{debt}", NOW)
    replies, _ = click(engine, replies, "Qarzni qaytarish")
    replies, _ = click(engine, replies, "To‘liq")
    assert "qaysi hisobdan" in replies[0].text.lower()
    replies, _ = click(engine, replies, "Karta")
    replies, _ = click(engine, replies, "Saqlash")
    assert ledger.balance(card) == 10000000 and ledger.balance(debt) == 0


def test_income_screenshot_can_switch_to_debt_return_without_counting_income(tmp_path):
    store, ledger, engine, card, _, debt = setup(tmp_path)
    replies = engine.message("40 ming so'm kirim bo'ldi", 1, NOW)
    replies, _ = click(engine, replies, "Qarz qaytdi")
    replies, _ = click(engine, replies, "Sinov qarzi")
    replies, _ = click(engine, replies, "Karta")
    replies, _ = click(engine, replies, "Saqlash")
    assert ledger.balance(card) == 24000000 and ledger.balance(debt) == 6000000
    operation = store.one("SELECT * FROM operations")
    assert operation["kind"] == "repay_lent" and operation["message_id"] is not None
    assert totals(store, "2026-10-01", "2026-11-01")["UZS"]["income"] == 0


def test_stale_full_payment_cannot_overpay_or_double_post(tmp_path):
    store, ledger, engine, card, _, debt = setup(tmp_path)
    replies = engine.callback(f"a:{debt}", NOW)
    replies, _ = click(engine, replies, "Qaytarilgan pulni kiritish")
    replies, _ = click(engine, replies, "To‘liq")
    replies, _ = click(engine, replies, "Karta")
    ledger.post(
        dict(kind="repay_lent", account=card, target=debt, amount=1000000, date="2026-10-27"), "other"
    )
    replies, _ = click(engine, replies, "Saqlash")
    assert ledger.balance(debt) == 9000000 and ledger.balance(card) == 21000000
    assert len(store.all("SELECT * FROM operations")) == 1
