import argparse
import asyncio
import json
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path
from .backup import backup, restore, new_key
from .db import Store
from .runtime import Config, run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", nargs="?", default="run", choices=["run", "health", "backup", "restore", "new-key"]
    )
    parser.add_argument("--file")
    parser.add_argument("--destination")
    args = parser.parse_args()
    if args.command == "new-key":
        if not args.destination:
            parser.error("--destination is required; key is never printed")
        fd = os.open(args.destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(new_key())
        return
    if args.command == "health":
        try:
            data = Path(os.environ.get("DATA_DIR", "/data"))
            if time.time() - json.loads((data / "heartbeat").read_text())["time"] > 180:
                raise ValueError("Stale worker")
            con = sqlite3.connect(f"file:{data}/hisobdon.sqlite3?mode=ro", uri=True)
            con.execute("SELECT 1 FROM settings LIMIT 1")
            con.close()
            print("healthy")
        except Exception:
            sys.exit(1)
        return
    if args.command == "restore":
        if not args.file or not args.destination:
            parser.error("--file and --destination are required")
        restore(args.file, args.destination, os.environ["BACKUP_KEY"].encode())
        print("Restore integrity verified")
        return
    cfg = Config.from_env()
    if args.command == "backup":
        s = Store(cfg.data / "hisobdon.sqlite3")
        try:
            print(backup(s, cfg.data / "backups", cfg.backup_key))
        finally:
            s.close()
        return
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("aiogram").setLevel(logging.CRITICAL)
    asyncio.run(run(cfg))


if __name__ == "__main__":
    main()
