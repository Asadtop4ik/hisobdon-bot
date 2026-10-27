import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def utcnow():
    return datetime.now(timezone.utc).isoformat()


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS accounts(
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, currency TEXT NOT NULL CHECK(currency IN ('UZS','USD')),
 kind TEXT NOT NULL, opening INTEGER NOT NULL DEFAULT 0, opened_on TEXT NOT NULL,
 due TEXT, archived INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
 is_reserve INTEGER NOT NULL DEFAULT 0 CHECK(is_reserve IN (0,1)));
CREATE TABLE IF NOT EXISTS messages(
 id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, telegram_id INTEGER NOT NULL,
 text TEXT NOT NULL, received_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'received',
 UNIQUE(chat_id,telegram_id));
CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS operations(
 id INTEGER PRIMARY KEY, idem_key TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
 day TEXT NOT NULL, amount INTEGER NOT NULL, currency TEXT NOT NULL,
 category TEXT NOT NULL, note TEXT NOT NULL, payload TEXT NOT NULL,
 message_id INTEGER REFERENCES messages(id), status TEXT NOT NULL DEFAULT 'active',
 replaces INTEGER REFERENCES operations(id), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS movements(
 id INTEGER PRIMARY KEY, operation_id INTEGER NOT NULL REFERENCES operations(id),
 account_id INTEGER NOT NULL REFERENCES accounts(id), amount INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS movement_account ON movements(account_id);
CREATE INDEX IF NOT EXISTS operation_day ON operations(day);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, action TEXT NOT NULL,
 object_id INTEGER, detail TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS categories(name TEXT PRIMARY KEY, kind TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS aliases(word TEXT PRIMARY KEY, category TEXT NOT NULL REFERENCES categories(name));
CREATE TABLE IF NOT EXISTS valuations(id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
 amount INTEGER NOT NULL, day TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rates(id INTEGER PRIMARY KEY, rate TEXT NOT NULL, day TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, kind TEXT NOT NULL, start TEXT, end TEXT,
 due TEXT NOT NULL, data TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'pending',
 attempts INTEGER NOT NULL DEFAULT 0, next_try TEXT, sent_at TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS updates(id INTEGER PRIMARY KEY, payload TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
"""

EXPENSE_CATEGORIES = [
    "Ovqat",
    "Oziq-ovqat",
    "Transport",
    "Uy",
    "Kommunal",
    "Aloqa",
    "Sog‘liq",
    "Xarid",
    "Ta’lim",
    "Ko‘ngilochar",
    "Komissiya",
    "Boshqa",
]
INCOME_CATEGORIES = ["Ish haqi", "Xizmat / biznes", "Sovg‘a", "Boshqa kirim", "Investitsiya daromadi", "Foiz"]


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), isolation_level=None, timeout=15)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA synchronous=FULL")
        if self.conn.execute("PRAGMA user_version").fetchone()[0] > 2:
            self.conn.close()
            raise ValueError("Database version is newer than this application.")
        self.conn.executescript(SCHEMA)
        with self.transaction():
            columns = {r["name"] for r in self.conn.execute("PRAGMA table_info(accounts)")}
            if "is_reserve" not in columns:
                self.conn.execute(
                    "ALTER TABLE accounts ADD COLUMN is_reserve INTEGER NOT NULL DEFAULT 0 CHECK(is_reserve IN (0,1))"
                )
            self.conn.execute("PRAGMA user_version=2")
            self.conn.executemany(
                "INSERT OR IGNORE INTO categories VALUES (?,?)",
                [(c, "expense") for c in EXPENSE_CATEGORIES] + [(c, "income") for c in INCOME_CATEGORIES],
            )

    def close(self):
        self.conn.close()

    @contextmanager
    def transaction(self):
        if self.conn.in_transaction:
            name = "sp_" + uuid.uuid4().hex
            self.conn.execute(f"SAVEPOINT {name}")
            try:
                yield
                self.conn.execute(f"RELEASE {name}")
            except BaseException:
                self.conn.execute(f"ROLLBACK TO {name}")
                self.conn.execute(f"RELEASE {name}")
                raise
            return
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def all(self, sql, params=()):
        return [dict(row) for row in self.conn.execute(sql, params)]

    def one(self, sql, params=()):
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def get(self, key, default=None):
        row = self.one("SELECT value FROM settings WHERE key=?", (key,))
        return json.loads(row["value"]) if row else default

    def set(self, key, value):
        self.conn.execute(
            "INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )

    def record_message(self, chat_id, message_id, text, at):
        self.conn.execute(
            "INSERT OR IGNORE INTO messages(chat_id,telegram_id,text,received_at) VALUES (?,?,?,?)",
            (chat_id, message_id, text, at),
        )
        return self.one("SELECT id FROM messages WHERE chat_id=? AND telegram_id=?", (chat_id, message_id))[
            "id"
        ]

    def save_draft(self, draft_id, data):
        self.conn.execute(
            "INSERT INTO drafts VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at",
            (draft_id, json.dumps(data, ensure_ascii=False), utcnow()),
        )

    def draft(self, draft_id):
        row = self.one("SELECT data FROM drafts WHERE id=?", (draft_id,))
        return json.loads(row["data"]) if row else None

    def audit(self, action, object_id, detail):
        self.conn.execute(
            "INSERT INTO audit(action,object_id,detail,created_at) VALUES (?,?,?,?)",
            (action, object_id, json.dumps(detail, ensure_ascii=False), utcnow()),
        )

    def snapshot(self, destination):
        target = sqlite3.connect(str(destination))
        try:
            self.conn.backup(target)
        finally:
            target.close()
