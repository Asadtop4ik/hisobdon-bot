from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from hisobdon.db import Store
from hisobdon.ledger import Ledger
from hisobdon.conversation import Engine
from hisobdon.reports import totals

NOW = datetime(2026, 11, 2, 15, tzinfo=ZoneInfo("Asia/Tashkent"))


def click(e, replies, label):
    choices = [(t, d) for r in replies for row in r.rows for t, d in row]
    match = [d for t, d in choices if label in t]
    assert match, str(choices)
    return e.callback(match[0], NOW), match[0]


@pytest.mark.parametrize(
    "text,kind,expected",
    [("20000 qarz oldim", "debt_borrowed", 12000000), ("20000 qarz berdim", "debt_lent", 8000000)],
)
def test_inline_person_creates_debt_and_moves_cash_once(tmp_path, text, kind, expected):
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    e = Engine(s)
    cash = ledger.create_account("Karta", "UZS", 10000000, "2026-10-01", "card")
    replies = e.message(text, 1, NOW)
    replies, _ = click(e, replies, "Karta")
    assert not s.all("SELECT * FROM accounts WHERE kind LIKE 'debt_%'")
    replies = e.message("Sinov odam", 2, NOW)
    assert not s.all("SELECT * FROM accounts WHERE kind LIKE 'debt_%'")
    replies, save = click(e, replies, "Saqlash")
    e.callback(save, NOW)
    assert ledger.balance(cash) == expected
    debts = s.all("SELECT * FROM accounts WHERE kind=?", (kind,))
    assert len(debts) == 1 and ledger.balance(debts[0]["id"]) == 2000000
    assert s.one("SELECT COUNT(*) AS n FROM operations")["n"] == 1
    assert totals(s, "2026-11-01", "2026-12-01")["UZS"]["income"] == 0
    assert "Sinov odam" in e.message("/debts", 3, NOW)[0].text
    assert "Sinov odam" not in e.message("/accounts", 4, NOW)[0].text


def test_delete_account_with_money_needs_confirmation_and_preserves_history(tmp_path):
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    e = Engine(s)
    a = ledger.create_account("Remove", "USD", 10000, "2026-10-01")
    replies = e.callback(f"a:{a}", NOW)
    replies, _ = click(e, replies, "Hisobni o‘chirish")
    assert ledger.balances()[0]["balance"] == 10000
    replies, confirm = click(e, replies, "Ha, hisobni o‘chirish")
    e.callback(confirm, NOW)
    assert ledger.balances() == []
    assert s.one("SELECT COUNT(*) AS n FROM accounts")["n"] == 1
    assert s.one("SELECT * FROM audit WHERE action='account_delete'")
    assert ledger.balances("2026-11-02")[0]["balance"] == 10000


def test_account_transfer_shortcut_and_related_history(tmp_path):
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    e = Engine(s)
    a = ledger.create_account("Source", "UZS", 10000000, "2026-10-01")
    b = ledger.create_account("Destination", "UZS", 0, "2026-10-01")
    replies = e.callback(f"a:{a}", NOW)
    replies, _ = click(e, replies, "Pul o‘tkazish")
    replies = e.message("20000", 1, NOW)
    replies, _ = click(e, replies, "Destination")
    replies, _ = click(e, replies, "Komissiyasiz")
    replies, _ = click(e, replies, "Saqlash")
    assert ledger.balance(a) == 8000000 and ledger.balance(b) == 2000000
    replies = e.callback(f"a:{b}", NOW)
    replies, _ = click(e, replies, "Hisob harakatlari")
    text = "\n".join(r.text for r in replies)
    assert "Source" in text and "Destination" in text and "20 000" in text


def test_delete_stale_confirmation_does_not_remove_changed_money(tmp_path):
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    e = Engine(s)
    a = ledger.create_account("Cash", "UZS", 10000000, "2026-10-01")
    replies = e.callback(f"delete:{a}", NOW)
    ledger.post(dict(kind="income", account=a, amount=10000, date="2026-11-02"), "new")
    replies, _ = click(e, replies, "Ha, hisobni o‘chirish")
    assert ledger.balances()[0]["balance"] == 10010000
    assert not s.one("SELECT * FROM audit WHERE action='account_delete'")


def test_abandoned_new_loan_does_not_create_phantom_account(tmp_path):
    s = Store(tmp_path / "db")
    e = Engine(s)
    Ledger(s).create_account("Cash", "UZS", 0, "2026-10-01")
    replies = e.message("20000 qarz oldim", 1, NOW)
    replies, _ = click(e, replies, "Cash")
    replies = e.message("Person", 2, NOW)
    replies, _ = click(e, replies, "Qoralamani bekor qilish")
    assert len(s.all("SELECT * FROM accounts")) == 1
    assert not s.all("SELECT * FROM operations")
