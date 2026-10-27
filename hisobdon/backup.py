import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from cryptography.fernet import Fernet


def new_key():
    return Fernet.generate_key()


def backup(store, directory, key):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    filename = f"hisobdon-{now:%Y%m%dT%H%M%S%fZ}.db.fernet"
    with tempfile.TemporaryDirectory() as temp:
        snapshot = Path(temp) / "snapshot.db"
        store.snapshot(snapshot)
        conn = sqlite3.connect(snapshot)
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Backup integrity failed")
        finally:
            conn.close()
        encrypted = Fernet(key).encrypt(snapshot.read_bytes())
    out = directory / filename
    staging = directory / (filename + ".tmp")
    with open(staging, "xb") as f:
        os.chmod(staging, 0o600)
        f.write(encrypted)
        f.flush()
        os.fsync(f.fileno())
    os.replace(staging, out)
    store.set("last_backup", now.isoformat())
    retain(directory)
    return out


def restore(file, destination, key):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Restore destination already exists; refuse overwrite")
    raw = Fernet(key).decrypt(Path(file).read_bytes())
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=destination.parent, suffix=".restore")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        conn = sqlite3.connect(name)
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Restore integrity failed")
        finally:
            conn.close()
        os.link(name, destination)  # atomic no-clobber publication
    finally:
        os.unlink(name)


def retain(directory):
    files = sorted(Path(directory).glob("hisobdon-*.db.fernet"), reverse=True)
    days = set()
    months = set()
    keep = set()
    for p in files:
        day = p.name[9:17]
        month = day[:6]
        if day not in days and len(days) < 14:
            days.add(day)
            keep.add(p)
        if month not in months and len(months) < 6:
            months.add(month)
            keep.add(p)
    for p in files:
        if p not in keep:
            p.unlink()
