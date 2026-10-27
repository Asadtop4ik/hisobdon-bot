import pytest
from hisobdon.db import Store
from hisobdon.ledger import Ledger, RuleError
from hisobdon.money import minor


@pytest.fixture
def ledger(tmp_path):
    return Ledger(Store(tmp_path / "test.db"))


def test_money_is_exact_and_rejects_fractional_cents():
    assert minor("40000") == 4000000
    assert minor("0.29") == 29
    with pytest.raises(ValueError):
        minor("1.001")
    with pytest.raises(ValueError):
        minor("NaN")


def test_posting_deduplicates_and_cancel_restores(ledger):
    a = ledger.create_account("Naqd", "UZS", 10000000, "2026-01-01")
    op = ledger.post(
        dict(kind="expense", account=a, amount=4000000, date="2026-01-02", category="Ovqat"), "a"
    )
    assert ledger.post(dict(kind="expense", account=a, amount=4000000, date="2026-01-02"), "a") == op
    assert ledger.balance(a) == 6000000
    ledger.cancel(op)
    ledger.cancel(op)
    assert ledger.balance(a) == 10000000
    assert len(ledger.store.all("SELECT * FROM operations")) == 1


def test_transfer_failure_is_atomic(ledger):
    a = ledger.create_account("UZS", "UZS", 100000, "2026-01-01")
    b = ledger.create_account("USD", "USD", 0, "2026-01-01")
    with pytest.raises(RuleError):
        ledger.post(dict(kind="transfer", account=a, target=b, amount=50000, date="2026-01-02"), "bad")
    assert ledger.balance(a) == 100000
    assert ledger.store.all("SELECT * FROM operations") == []
    ledger.post(
        dict(kind="exchange", account=a, target=b, amount=50000, received=40, date="2026-01-02"), "fx"
    )
    assert ledger.balance(a) == 50000
    assert ledger.balance(b) == 40


def test_old_debt_and_partial_repayment(ledger):
    cash = ledger.create_account("Cash", "USD", 10000, "2026-01-01")
    debt = ledger.create_account("Person", "USD", 5000, "2026-01-01", "debt_borrowed")
    op = ledger.post(
        dict(kind="repay_borrowed", account=cash, target=debt, amount=2000, date="2026-01-02"), "r"
    )
    assert ledger.balance(cash) == 8000
    assert ledger.balance(debt) == 3000
    with pytest.raises(RuleError):
        ledger.post(
            dict(kind="repay_borrowed", account=cash, target=debt, amount=4000, date="2026-01-03"), "over"
        )
    ledger.cancel(op)
    assert ledger.balance(debt) == 5000


def test_cannot_cancel_lending_after_repayment(ledger):
    cash = ledger.create_account("Cash", "USD", 10000, "2026-01-01")
    debt = ledger.create_account("Person", "USD", 0, "2026-01-01", "debt_lent")
    loan = ledger.post(dict(kind="lend", account=cash, target=debt, amount=5000, date="2026-01-02"), "l")
    ledger.post(dict(kind="repay_lent", account=cash, target=debt, amount=1000, date="2026-01-03"), "r")
    with pytest.raises(RuleError):
        ledger.cancel(loan)
    assert ledger.balance(debt) == 4000


def test_investment_retained_income_withdrawal(ledger):
    cash = ledger.create_account("Cash", "UZS", 100000, "2026-01-01")
    inv = ledger.create_account("Company", "UZS", 500000, "2026-01-01", "investment")
    ledger.post(dict(kind="invest_income", account=inv, amount=10000, date="2026-01-02"), "profit")
    ledger.post(dict(kind="withdraw", account=cash, target=inv, amount=10000, date="2026-01-03"), "withdraw")
    assert ledger.balance(inv) == 500000
    assert ledger.balance(cash) == 110000
    assert ledger.balance(inv, "2026-01-03") == 510000


def test_replacement_rolls_back_if_invalid(ledger):
    a = ledger.create_account("Cash", "USD", 10000, "2026-01-01")
    op = ledger.post(dict(kind="expense", account=a, amount=1000, date="2026-01-02"), "old")
    with pytest.raises(RuleError):
        ledger.replace(op, dict(kind="expense", account=a, amount=20000, date="2026-01-02"), "new")
    assert ledger.balance(a) == 9000
    ledger.replace(op, dict(kind="expense", account=a, amount=2000, date="2026-01-02"), "new2")
    assert ledger.balance(a) == 8000


def test_message_and_draft_persist_without_double_entry(tmp_path):
    path = tmp_path / "persist.db"
    s = Store(path)
    mid = s.record_message(1, 10, "hello", "2026-01-01T00:00:00+00:00")
    assert s.record_message(1, 10, "hello", "2026-01-01T00:00:00+00:00") == mid
    s.save_draft("d1", {"step": "amount", "message_id": mid})
    s.close()
    s = Store(path)
    assert s.draft("d1")["step"] == "amount"
    assert len(s.all("SELECT * FROM messages")) == 1


def test_nested_failed_post_rolls_back_even_when_caller_handles_error(ledger):
    cash = ledger.create_account("Cash", "USD", 10000, "2026-01-01")
    debt = ledger.create_account("Loan", "USD", 1000, "2026-01-01", "debt_borrowed")
    with ledger.store.transaction():
        try:
            ledger.post(
                dict(kind="repay_borrowed", account=cash, target=debt, amount=2000, date="2026-01-02"), "bad"
            )
        except RuleError:
            pass
    assert ledger.balance(cash) == 10000
    assert ledger.balance(debt) == 1000
    assert not ledger.store.all("SELECT * FROM operations")


def test_transfer_fee_is_atomic_and_cancellable(ledger):
    a = ledger.create_account("A", "UZS", 100000, "2026-01-01")
    b = ledger.create_account("B", "UZS", 0, "2026-01-01")
    op = ledger.post(
        dict(kind="transfer", account=a, target=b, amount=50000, fee=1000, date="2026-01-02"), "fee"
    )
    assert ledger.balance(a) == 49000
    assert ledger.balance(b) == 50000
    ledger.cancel(op)
    assert ledger.balance(a) == 100000
