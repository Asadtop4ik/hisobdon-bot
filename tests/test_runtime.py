from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from hisobdon.db import Store
from hisobdon.ledger import Ledger
from hisobdon.runtime import Config, allowed, cache_updates, apply_update, text_chunks

NOW = datetime(2026, 10, 27, 14, tzinfo=ZoneInfo("Asia/Tashkent"))


def update(uid, chat_type="private", text="/start", update_id=1):
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": int(NOW.timestamp()),
            "from": {"id": uid, "is_bot": False, "first_name": "User"},
            "chat": {"id": uid, "type": chat_type},
            "text": text,
        },
    }


def test_owner_auth_before_persistence(tmp_path):
    s = Store(tmp_path / "db")
    assert allowed(update(100), 100)
    assert not allowed(update(200), 100)
    assert not allowed(update(100, "group"), 100)
    cache_updates(s, [update(200), update(100, "group", update_id=2)], 100)
    assert not s.all("SELECT * FROM updates")
    assert s.get("telegram_offset") == 3


def test_durable_update_replay_does_not_duplicate_drafts(tmp_path):
    s = Store(tmp_path / "db")
    ledger = Ledger(s)
    ledger.create_account("Cash", "UZS", 10000000, "2026-10-01")
    u = update(100, text="ovqat 40000")
    cache_updates(s, [u], 100)
    replies = apply_update(s, u, 100, NOW)
    again = apply_update(s, u, 100, NOW)
    assert replies == again
    assert len(s.all("SELECT * FROM drafts")) == 1
    assert len(s.all("SELECT * FROM messages")) == 1
    callback = replies[0]["rows"][0][0][1]
    cb = {
        "update_id": 2,
        "callback_query": {
            "id": "q",
            "from": {"id": 100},
            "message": {"chat": {"id": 100, "type": "private"}},
            "data": callback,
        },
    }
    cache_updates(s, [cb], 100)
    apply_update(s, cb, 100, NOW)
    apply_update(s, cb, 100, NOW)
    assert ledger.balances()[0]["balance"] == 6000000


def test_unicode_messages_fit_telegram_limit():
    original = "💳" * 5000
    chunks = text_chunks(original)
    assert "".join(chunks) == original
    assert all(len(c.encode("utf-16-le")) // 2 <= 3800 for c in chunks)


def test_configuration_requires_owner_and_secret(tmp_path):
    with pytest.raises(ValueError):
        Config.from_env({})
    with pytest.raises(ValueError):
        Config.from_env({"BOT_TOKEN": "123:abc", "OWNER_ID": "0"})
