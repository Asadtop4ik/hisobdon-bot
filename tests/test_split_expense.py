from datetime import datetime
from zoneinfo import ZoneInfo
import json
import pytest
from hisobdon.db import Store
from hisobdon.ledger import Ledger, RuleError
from hisobdon.conversation import Engine
from hisobdon.reports import totals

NOW = datetime(2026, 10, 27, 17, tzinfo=ZoneInfo("Asia/Tashkent"))


def click(engine, replies, label):
    choices = [(label_, data) for reply in replies for row in reply.rows for label_, data in row]
    options = [data for label_, data in choices if label in label_]
    assert options, f"{label} missing: {[label_ for label_, _ in choices]}"
    return engine.callback(options[0], NOW), options[0]


def setup(tmp_path):
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    cash = ledger.create_account("Naqd", "UZS", 1700000, "2026-10-01")
    card = ledger.create_account("Karta", "UZS", 10000000, "2026-10-01", "card")
    return s, ledger, Engine(s), cash, card


def test_split_expense_counts_once_and_cancel_restores_both(tmp_path):
    s, ledger, _, cash, card = setup(tmp_path)
    data = dict(
        kind="expense",
        account=cash,
        amount=6000000,
        date="2026-10-27",
        category="Ovqat",
        allocations=[{"account": cash, "amount": 1700000}, {"account": card, "amount": 4300000}],
    )
    op = ledger.post(data, "split")
    assert ledger.balance(cash) == 0 and ledger.balance(card) == 5700000
    assert totals(s, "2026-10-01", "2026-11-01")["UZS"]["expense"] == 6000000
    assert len(s.all("SELECT * FROM operations")) == 1
    ledger.cancel(op)
    assert ledger.balance(cash) == 1700000 and ledger.balance(card) == 10000000


def test_split_validation_is_atomic_and_currency_and_reserve_safe(tmp_path):
    s, ledger, _, cash, card = setup(tmp_path)
    ledger.update_opening(cash, 10000000, "2026-10-01")
    usd = ledger.create_account("Dollar", "USD", 10000, "2026-10-01")
    reserve = ledger.create_account("Reserve", "UZS", 10000000, "2026-10-01", is_reserve=True)
    base = dict(kind="expense", account=cash, amount=6000000, date="2026-10-27")
    cases = [
        [{"account": cash, "amount": 1700000}, {"account": card, "amount": 4200000}],
        [{"account": cash, "amount": 1700000}, {"account": usd, "amount": 4300000}],
        [{"account": cash, "amount": 1700000}, {"account": reserve, "amount": 4300000}],
        [{"account": cash, "amount": 1700000}, {"account": cash, "amount": 4300000}],
    ]
    for i, parts in enumerate(cases):
        with pytest.raises(RuleError):
            ledger.post({**base, "allocations": parts}, "bad" + str(i))
    assert ledger.balance(cash) == 10000000 and ledger.balance(card) == 10000000
    assert not s.all("SELECT * FROM operations")


def test_split_payment_ui_survives_restart_and_edit(tmp_path):
    s, ledger, e, cash, card = setup(tmp_path)
    replies = e.message("ovqat 60 ming som", 1, NOW)
    replies, _ = click(e, replies, "Bugun")
    replies, _ = click(e, replies, "Bo‘lib to‘lash")
    replies, _ = click(e, replies, "Naqd")
    replies = e.message("17000", 2, NOW)
    assert "43 000" in replies[0].text
    s.close()
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    e = Engine(s)
    replies, _ = click(e, replies, "Karta")
    replies, _ = click(e, replies, "Qolgan")
    replies, save = click(e, replies, "Saqlash")
    e.callback(save, NOW)
    assert ledger.balance(cash) == 0 and ledger.balance(card) == 5700000
    assert len(s.all("SELECT * FROM operations")) == 1
    op = s.one("SELECT * FROM operations")
    assert len(json.loads(op["payload"])["allocations"]) == 2
    replies, _ = click(e, replies, "Tuzatish")
    replies, _ = click(e, replies, "Summa")
    replies = e.message("50000", 3, NOW)
    replies, _ = click(e, replies, "Naqd")
    replies = e.message("10000", 4, NOW)
    replies, _ = click(e, replies, "Karta")
    replies, _ = click(e, replies, "Qolgan")
    replies, _ = click(e, replies, "O‘zgarishni saqlash")
    assert ledger.balance(cash) == 700000 and ledger.balance(card) == 6000000
    assert totals(s, "2026-10-01", "2026-11-01")["UZS"]["expense"] == 5000000
