"""Durable polling and outbox. Network I/O never occurs in a ledger transaction."""

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import BotCommand, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from cryptography.fernet import Fernet

from .backup import backup
from .conversation import Engine, Reply
from .db import Store, utcnow
from .ledger import Ledger
from .money import money
from .reports import export, report
from .scheduler import due_jobs, mark_failed, mark_sent

TZ = ZoneInfo("Asia/Tashkent")
LOG = logging.getLogger("hisobdon")


@dataclass
class Config:
    token: str = field(repr=False)
    owner: int
    backup_key: bytes = field(repr=False)
    data: Path = Path("/data")
    version: str = "local"

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        token = env.get("BOT_TOKEN", "").strip()
        try:
            owner = int(env.get("OWNER_ID", "0"))
        except ValueError:
            raise ValueError("OWNER_ID must be a positive integer") from None
        if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{20,}", token) or owner <= 0:
            raise ValueError("BOT_TOKEN and positive OWNER_ID are required")
        try:
            key = env.get("BACKUP_KEY", "").encode()
            Fernet(key)
        except Exception:
            raise ValueError("Valid BACKUP_KEY is required") from None
        return cls(token, owner, key, Path(env.get("DATA_DIR", "/data")), env.get("APP_VERSION", "local"))


def allowed(update, owner):
    if "callback_query" in update:
        cb = update["callback_query"]
        user = cb.get("from", {})
        chat = cb.get("message", {}).get("chat", {})
    else:
        msg = update.get("message") or update.get("edited_message") or {}
        user = msg.get("from", {})
        chat = msg.get("chat", {})
    return user.get("id") == owner and chat.get("id") == owner and chat.get("type") == "private"


def runtime_schema(store):
    store.conn.executescript("""
    CREATE TABLE IF NOT EXISTS responses(update_id INTEGER PRIMARY KEY REFERENCES updates(id), payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS deliveries(key TEXT PRIMARY KEY, tasks TEXT NOT NULL, cursor INTEGER NOT NULL DEFAULT 0);
    """)


def cache_updates(store, updates, owner):
    runtime_schema(store)
    with store.transaction():
        for update in updates:
            if allowed(update, owner):
                store.conn.execute(
                    "INSERT OR IGNORE INTO updates(id,payload,created_at) VALUES (?,?,?)",
                    (update["update_id"], json.dumps(update, ensure_ascii=False), utcnow()),
                )
            store.set("telegram_offset", max(store.get("telegram_offset", 0), update["update_id"] + 1))


def apply_update(store, update, owner, now):
    if not allowed(update, owner):
        return []
    runtime_schema(store)
    with store.transaction():
        existing = store.one("SELECT payload FROM responses WHERE update_id=?", (update["update_id"],))
        if existing:
            return json.loads(existing["payload"])
        engine = Engine(store, owner_id=owner)
        try:
            if "callback_query" in update:
                replies = engine.callback(update["callback_query"].get("data", ""), now)
            elif "edited_message" in update:
                replies = [
                    Reply(
                        "Telegram’dagi tahrir hisobni o‘zgartirmaydi. /history → Tuzatish tugmasidan foydalaning."
                    )
                ]
            else:
                msg = update["message"]
                original_time = datetime.fromtimestamp(msg["date"], TZ)
                if "text" in msg:
                    replies = engine.message(msg["text"], msg["message_id"], original_time)
                else:
                    description = (
                        msg.get("caption")
                        or "[Matn bo‘lmagan xabar: "
                        + (
                            ",".join(
                                k
                                for k in ("voice", "photo", "document", "audio", "video", "sticker")
                                if k in msg
                            )
                            or "boshqa"
                        )
                        + "]"
                    )
                    store.record_message(owner, msg["message_id"], description, original_time.isoformat())
                    replies = [
                        Reply("Hozir moliyaviy yozuvni matn bilan yuboring. Masalan: «ovqat 40ming so‘m».")
                    ]
        except (ValueError, ArithmeticError):
            replies = [
                Reply(
                    "Ma’lumotni tekshiring. Summani yoki sanani qayta kiriting; /drafts orqali davom eting."
                )
            ]
        payload = json.loads(json.dumps([asdict(r) for r in replies], ensure_ascii=False))
        store.conn.execute(
            "INSERT INTO responses VALUES (?,?)",
            (update["update_id"], json.dumps(payload, ensure_ascii=False)),
        )
        store.conn.execute("UPDATE updates SET status='applied' WHERE id=?", (update["update_id"],))
        return payload


def text_chunks(text, limit=3800):
    parts = []
    chunk = []
    size = 0
    for c in text:
        units = 2 if ord(c) > 0xFFFF else 1
        if size + units > limit:
            parts.append("".join(chunk))
            chunk = []
            size = 0
        chunk.append(c)
        size += units
    if chunk:
        parts.append("".join(chunk))
    return parts or [" "]


def prepare_delivery(store, key, replies, export_dir):
    existing = store.one("SELECT * FROM deliveries WHERE key=?", (key,))
    if existing:
        pending = json.loads(existing["tasks"])[existing["cursor"] :]
        if all(t["kind"] != "file" or Path(t["path"]).is_file() for t in pending):
            return existing
    tasks = (
        [
            {
                "kind": "text",
                "text": "Tiklashdan keyin hisobot fayllari mavjud bazadan qayta tayyorlandi.",
                "rows": [],
            }
        ]
        if existing
        else []
    )
    for reply in replies:
        files = reply.get("files", [])
        if reply.get("export_range"):
            start, end = reply["export_range"]
            files = [str(p) for p in export(store, start, end, export_dir)]
        pieces = text_chunks(reply["text"])
        for i, text in enumerate(pieces):
            tasks.append(
                {"kind": "text", "text": text, "rows": reply.get("rows", []) if i == len(pieces) - 1 else []}
            )
        tasks.extend({"kind": "file", "path": str(p)} for p in files)
    store.conn.execute(
        "INSERT INTO deliveries(key,tasks) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET tasks=excluded.tasks,cursor=0",
        (key, json.dumps(tasks, ensure_ascii=False)),
    )
    return store.one("SELECT * FROM deliveries WHERE key=?", (key,))


async def deliver(bot, store, owner, key, replies, export_dir):
    row = prepare_delivery(store, key, replies, export_dir)
    tasks = json.loads(row["tasks"])
    for i in range(row["cursor"], len(tasks)):
        task = tasks[i]
        if task["kind"] == "text":
            keyboard = (
                InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text=label, callback_data=data) for label, data in r]
                        for r in task["rows"]
                    ]
                )
                if task["rows"]
                else None
            )
            await bot.send_message(owner, task["text"], reply_markup=keyboard)
        else:
            await bot.send_document(owner, FSInputFile(task["path"]), request_timeout=90)
        store.conn.execute("UPDATE deliveries SET cursor=? WHERE key=?", (i + 1, key))


async def drain(bot, store, cfg):
    for row in store.all("SELECT * FROM updates WHERE status!='done' ORDER BY id LIMIT 50"):
        update = json.loads(row["payload"])
        try:
            if "callback_query" in update:
                try:
                    await bot.answer_callback_query(update["callback_query"]["id"])
                except Exception:
                    pass  # expired callbacks must not prevent persisted operations from completing
            replies = apply_update(store, update, cfg.owner, datetime.now(TZ))
            await deliver(bot, store, cfg.owner, "update:" + str(row["id"]), replies, cfg.data / "exports")
            store.conn.execute("UPDATE updates SET status='done' WHERE id=?", (row["id"],))
            store.set("owner_reachable", True)
        except Exception as exc:
            LOG.warning("Update delivery pending: %s", type(exc).__name__)
            # Maintain user-visible ordering: later prompts must not overtake a failed earlier prompt.
            break


async def polling(bot, store, cfg):
    while True:
        try:
            await drain(bot, store, cfg)
            updates = await bot.get_updates(
                offset=store.get("telegram_offset", 0),
                timeout=25,
                allowed_updates=["message", "callback_query", "edited_message"],
                request_timeout=40,
            )
            cache_updates(
                store,
                [u.model_dump(mode="json", by_alias=True, exclude_none=True) for u in updates],
                cfg.owner,
            )
            store.set("last_poll", utcnow())
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOG.warning("Polling retry: %s", type(exc).__name__)
            await asyncio.sleep(5)


async def scheduled_work(bot, store, cfg, now):
    for job in due_jobs(store, now):
        try:
            if job["kind"] == "debt":
                a = Ledger(store).account(json.loads(job["data"])["account"])
                amount = Ledger(store).balance(a["id"])
                replies = [
                    asdict(
                        Reply(
                            f"Qarz eslatmasi • {a['name']}\nQolgan: {money(amount, a['currency'])}\nMuddat: {a['due']}\n{job['id']}"
                        )
                    )
                ]
            else:
                text = (
                    report(store, job["start"], job["end"], now.isoformat())
                    + f"\nHisobot ID: {job['id']}\nRejalashtirilgan vaqt: {job['due']}"
                )
                replies = [
                    asdict(
                        Reply(
                            text,
                            export_range=(job["start"], job["end"]) if job["kind"] == "monthly" else None,
                        )
                    )
                ]
            await deliver(bot, store, cfg.owner, "job:" + job["id"], replies, cfg.data / "exports")
            mark_sent(store, job["id"], now)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            mark_failed(store, job["id"], now, type(exc).__name__)
            LOG.warning("Scheduled delivery pending: %s", type(exc).__name__)

    # Separate from notification toggle: daily disaster-recovery copy at 03:00, and first startup.
    backup_day = now.date().isoformat() if now.hour >= 3 else (now.date() - timedelta(days=1)).isoformat()
    if store.get("backup_day") != backup_day or not Path(store.get("backup_file", "/nonexistent")).is_file():
        p = backup(store, cfg.data / "backups", cfg.backup_key)
        store.set("backup_file", str(p))
        store.set("backup_day", backup_day)
    if store.get("backup_sent_day") != backup_day:
        try:
            replies = [
                asdict(
                    Reply(
                        "Hisobdon • shifrlangan kunlik zaxira.\nTiklash uchun alohida saqlangan kalit kerak.\nSana: "
                        + backup_day,
                        files=[store.get("backup_file")],
                    )
                )
            ]
            await deliver(bot, store, cfg.owner, "backup:" + backup_day, replies, cfg.data / "exports")
            store.set("backup_sent_day", backup_day)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOG.warning("Backup upload pending: %s", type(exc).__name__)


def heartbeat(cfg):
    target = cfg.data / "heartbeat"
    staged = cfg.data / "heartbeat.tmp"
    staged.write_text(json.dumps({"time": time.time(), "version": cfg.version}))
    os.replace(staged, target)


async def worker(bot, store, cfg):
    while True:
        heartbeat(cfg)
        try:
            await scheduled_work(bot, store, cfg, datetime.now(TZ))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOG.warning("Worker retry: %s", type(exc).__name__)
        heartbeat(cfg)
        await asyncio.sleep(30)


async def run(cfg):
    os.umask(0o077)
    cfg.data.mkdir(parents=True, exist_ok=True)
    store = Store(cfg.data / "hisobdon.sqlite3")
    runtime_schema(store)
    store.set("version", cfg.version)
    store.set("activated_on", store.get("activated_on", datetime.now(TZ).date().isoformat()))
    bot = Bot(cfg.token)
    try:
        identity = await bot.get_me()
        LOG.info("Starting verified bot @%s, release %s", identity.username, cfg.version)
        await bot.delete_webhook(drop_pending_updates=False)
        await bot.set_my_commands(
            [
                BotCommand(command=c, description=d)
                for c, d in [
                    ("start", "Menyu"),
                    ("add", "Kirim, chiqim yoki boshqa operatsiya"),
                    ("accounts", "Karta va naqd hisoblar"),
                    ("balance", "Qoldiqlar"),
                    ("debts", "Qarzlar"),
                    ("investments", "Investitsiyalar"),
                    ("history", "Tarix va tuzatish"),
                    ("today", "Bugungi hisobot"),
                    ("week", "Haftalik hisobot"),
                    ("month", "Oylik hisobot"),
                    ("export", "Excel va AI uchun TXT"),
                    ("drafts", "Qoralamalar"),
                    ("settings", "Sozlamalar"),
                    ("help", "Yordam"),
                ]
            ]
        )
        await bot.set_my_description(
            "Hisobdon — shaxsiy kirim-chiqim, hisoblar, qarzlar va investitsiyalar. UZS/USD hisob, Excel va AI uchun hisobotlar."
        )
        await bot.set_my_short_description("Shaxsiy moliya daftari • UZS / USD")
        heartbeat(cfg)
        await asyncio.gather(polling(bot, store, cfg), worker(bot, store, cfg))
    finally:
        await bot.session.close()
        store.close()
