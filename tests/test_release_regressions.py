import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from hisobdon.backup import new_key
from hisobdon.conversation import Engine
from hisobdon.db import Store
from hisobdon.ledger import Ledger, RuleError
from hisobdon.parser import parse
from hisobdon.reports import raw_messages
from hisobdon.runtime import (
    Config,
    apply_update,
    cache_updates,
    drain,
    prepare_delivery,
    scheduled_work,
    runtime_schema,
)

NOW = datetime(2026, 10, 27, 14, tzinfo=ZoneInfo("Asia/Tashkent"))


def pick(engine, replies, label):
    callback = next(data for reply in replies for row in reply.rows for text, data in row if label in text)
    return engine.callback(callback, NOW)


def test_same_day_loan_note_revision_preserves_economic_order(tmp_path):
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    a = ledger.create_account("Cash", "USD", 10000, "2026-01-01")
    b = ledger.create_account("Loan", "USD", 0, "2026-01-01", "debt_lent")
    data = dict(kind="lend", account=a, target=b, amount=5000, date="2026-01-02")
    first = ledger.post(data, "first")
    ledger.post(dict(kind="repay_lent", account=a, target=b, amount=1000, date="2026-01-02"), "repay")
    second = ledger.replace(first, {**data, "note": "correct note"}, "second")
    ledger.replace(second, {**data, "note": "another correction"}, "third")
    assert ledger.balance(b) == 4000
    active = s.one("SELECT id FROM operations WHERE kind='lend' AND status='active'")["id"]
    with pytest.raises(RuleError):
        ledger.replace(active, {**data, "amount": 500}, "invalid")
    assert ledger.balance(b) == 4000


def test_backdated_wizard_and_revision_include_all_source_answers(tmp_path):
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    engine = Engine(s)
    ledger.create_account("Cash", "UZS", 10000000, "2026-09-01")
    engine.callback("op:expense", NOW)
    replies = engine.message("40000", 1, NOW)
    replies = pick(engine, replies, "Ovqat")
    replies = pick(engine, replies, "Cash")
    replies = pick(engine, replies, "Tuzatish")
    replies = pick(engine, replies, "Sana")
    replies = pick(engine, replies, "Boshqa sana")
    replies = engine.message("2026-09-28", 2, NOW)
    replies = pick(engine, replies, "O‘zgarishni saqlash")
    assert "Saqlandi" in replies[0].text
    messages = raw_messages(s, "2026-09-01", "2026-10-01")
    assert {m["text"] for m in messages} == {"40000", "2026-09-28"}


@pytest.mark.parametrize(
    "text", ["ertaga ovqat 40ming so‘m", "bugun va kecha ovqat 40ming so‘m", "2026-10-25 bugun ovqat 40ming"]
)
def test_explicit_ambiguous_or_future_date_requires_clarification(text):
    assert parse(text, NOW).get("error")


class OfflineTelegram:
    def __init__(self):
        self.documents = []

    async def send_message(self, *args, **kwargs):
        pass

    async def answer_callback_query(self, *args, **kwargs):
        pass

    async def send_document(self, owner, document, **kwargs):
        # Actual file access reproduces a disaster-recovery filesystem, without network calls.
        self.documents.append(
            document.path.read_bytes()
            if hasattr(document.path, "read_bytes")
            else open(document.path, "rb").read()
        )


@pytest.mark.asyncio
async def test_restored_pending_export_regenerates_files_and_unblocks_new_commands(tmp_path):
    original = Store(tmp_path / "original.db")
    ledger = Ledger(original)
    ledger.create_account("Cash", "UZS", 10000000, "2026-10-01")
    export_update = {
        "update_id": 1,
        "callback_query": {
            "id": "query",
            "from": {"id": 100},
            "message": {"chat": {"id": 100, "type": "private"}},
            "data": "m:export_month",
        },
    }
    cache_updates(original, [export_update], 100)
    replies = apply_update(original, export_update, 100, NOW)
    old_exports = tmp_path / "old_exports"
    prepare_delivery(original, "update:1", replies, old_exports)
    original.snapshot(tmp_path / "restored.db")
    shutil.rmtree(old_exports)
    original.close()
    restored = Store(tmp_path / "restored.db")
    next_update = {
        "update_id": 2,
        "message": {
            "message_id": 2,
            "date": int(NOW.timestamp()),
            "from": {"id": 100},
            "chat": {"id": 100, "type": "private"},
            "text": "/start",
        },
    }
    cache_updates(restored, [next_update], 100)
    cfg = Config("unused", 100, new_key(), tmp_path / "runtime")
    bot = OfflineTelegram()
    await drain(bot, restored, cfg)
    assert [r["status"] for r in restored.all("SELECT status FROM updates ORDER BY id")] == ["done", "done"]
    assert any(content.startswith(b"PK") for content in bot.documents)
    assert len(restored.all("SELECT * FROM accounts")) == 1


@pytest.mark.asyncio
async def test_missing_backup_artifact_after_restore_is_regenerated(tmp_path):
    s = Store(tmp_path / "db")
    runtime_schema(s)
    s.set("notifications", False)
    s.set("backup_day", "2026-10-27")
    s.set("backup_file", str(tmp_path / "gone.db.fernet"))
    cfg = Config("unused", 100, new_key(), tmp_path / "runtime")
    bot = OfflineTelegram()
    await scheduled_work(bot, s, cfg, NOW)
    assert s.get("backup_sent_day") == "2026-10-27"
    assert bot.documents
