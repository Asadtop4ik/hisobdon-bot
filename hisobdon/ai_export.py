"""Lossless financial dossier with a scoped summary and a complete archive."""

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from openpyxl import Workbook
from .ledger import INCOME, EXPENSE, LIQUID

ROWS_PER_PART = 3000
RECORD_BYTES_PER_PART = 2 * 1024 * 1024
FILE_LIMIT = 40 * 1024 * 1024
TABLES = (
    "accounts",
    "operations",
    "movements",
    "valuations",
    "rates",
    "categories",
    "aliases",
    "messages",
    "drafts",
    "audit",
)
TECHNICAL_TABLES = {"settings", "jobs", "updates", "responses", "deliveries", "sqlite_sequence"}
SHEETS = {
    "accounts": "Hisoblar",
    "operations": "Tranzaksiyalar",
    "movements": "Pul harakatlari",
    "valuations": "Baholashlar",
    "rates": "Valyuta",
    "categories": "Kategoriyalar",
    "aliases": "Kalit so‘zlar",
    "messages": "Asl xabarlar",
    "drafts": "Qoralamalar",
    "audit": "Tuzatishlar",
}


def financial_snapshot(store, start, end, generated):
    from .reports import totals, valued_accounts

    tables = {name: store.all(f"SELECT * FROM {name} ORDER BY rowid") for name in TABLES}
    # Preserve stable financial message IDs, not Telegram routing identifiers.
    tables["messages"] = [
        {k: r[k] for k in ("id", "text", "received_at", "status")} for r in tables["messages"]
    ]
    for table, column in [("operations", "payload"), ("drafts", "data"), ("audit", "detail")]:
        for row in tables[table]:
            row[column] = json.loads(row[column])
    current = valued_accounts(store)
    period_end = valued_accounts(store, end)
    actual_tables = {r["name"] for r in store.all("SELECT name FROM sqlite_master WHERE type='table'")}
    first = min((a["opened_on"] for a in tables["accounts"]), default=None)
    metadata = {
        "format": "hisobdon-financial-archive-v1",
        "generated_at": generated,
        "timezone": "Asia/Tashkent",
        "requested_period": {"start": start, "end_exclusive": end},
        "archive_scope": "ALL financial records in the same snapshot, including records outside the requested period",
        "tracking_started_on": first,
        "money": {
            "scale": 100,
            "UZS": "tiyin",
            "USD": "sent",
            "binary_float": False,
            "fields": "opening, amount, balance, used_value, fee, received and *_minor are integer hundredths; rate is decimal UZS per USD",
        },
        "joins": {
            "movements.operation_id": "operations.id",
            "movements.account_id": "accounts.id",
            "operations.message_id": "messages.id",
            "operations.payload.source_message_ids": "messages.id",
            "operations.replaces": "operations.id (previous version)",
            "valuations.account_id": "accounts.id",
            "operations.payload.target": "accounts.id (transfer/debt/investment counterpart)",
        },
        "counting_rules": [
            "Only status=active operations affect balances; cancelled/replaced versions are history, not extra cashflow.",
            "Balance is opening plus signed movements of active operations. Debt_borrowed is subtracted from net worth.",
            "Opening balance, principal transfers, loan principal and investment contributions are not income/expense.",
            "Transfer/exchange fee is an expense in source currency; amounts in different currencies cannot be summed.",
            "Valuations are estimates, not cash income. Retained investment profit withdrawn later is not income again.",
            "is_reserve=1 is emergency savings: part of net worth, excluded from daily spendable balance.",
            "Account purpose/archive labels reflect snapshot settings; audit contains marker changes, not automatic historical classifications.",
            "Split expense payload.allocations sums to operation.amount. Count that expense once; movements debit its participating accounts.",
            "Current balances and period-end balances refer to different dates. Never combine them.",
            "Global metadata/analysis is repeated in parts for readability: use once. Each canonical table row occurs in one part only.",
        ],
        "table_counts": {name: len(records) for name, records in tables.items()},
        "excluded_tables": sorted(actual_tables & TECHNICAL_TABLES),
        "excluded_reason": "Transport/delivery queues and runtime settings are not financial records; runtime secrets and host paths are not read; user-authored messages remain verbatim.",
        "unmapped_tables": sorted(actual_tables - set(TABLES) - TECHNICAL_TABLES),
    }
    accounts_by_id = {a["id"]: a for a in tables["accounts"]}
    active = {o["id"]: o for o in tables["operations"] if o["status"] == "active"}
    monthly = defaultdict(
        lambda: {"income_minor": 0, "expense_minor": 0, "cash_movement_minor": 0, "operations": 0}
    )
    for op in active.values():
        bucket = monthly[(op["day"][:7], op["currency"])]
        bucket["operations"] += 1
        if op["kind"] in INCOME:
            bucket["income_minor"] += op["amount"]
        if op["kind"] in EXPENSE:
            bucket["expense_minor"] += op["amount"]
        bucket["expense_minor"] += op["payload"].get("fee", 0)
    for m in tables["movements"]:
        op = active.get(m["operation_id"])
        account = accounts_by_id[m["account_id"]]
        if op and account["kind"] in LIQUID:
            monthly[(op["day"][:7], account["currency"])]["cash_movement_minor"] += m["amount"]
    monthly_rows = [
        {
            "month": month,
            "currency": currency,
            **figures,
            "coverage": "recorded data only; absent months are not proof of zero spending",
        }
        for (month, currency), figures in sorted(monthly.items())
    ]
    analysis = {
        "period_totals": totals(store, start, end),
        "period_end_balances": period_end,
        "current_balances": current,
        "monthly_recorded_cashflow": monthly_rows,
        "quality": {
            "pending_drafts": sum(not d["data"].get("done") for d in tables["drafts"]),
            "cancelled_operations": sum(o["status"] != "active" for o in tables["operations"]),
            "negative_account_ids": [a["id"] for a in current if a["balance"] < 0],
            "opening_history_limitation": "Opening values do not reconstruct older transactions or historical investment returns.",
            "completeness_limitation": "Only manually recorded data is known. Income stability, household commitments and goals may be missing; ask the owner.",
        },
    }
    return {"metadata": metadata, "analysis": analysis, "tables": tables}


def partition_tables(tables):
    part = {name: [] for name in TABLES}
    rows = 0
    size = 0
    for name, records in tables.items():
        for record in records:
            record_size = len(json.dumps(record, ensure_ascii=False).encode())
            if rows and (rows >= ROWS_PER_PART or size + record_size > RECORD_BYTES_PER_PART):
                yield part
                part = {name: [] for name in TABLES}
                rows = 0
                size = 0
            part[name].append(record)
            rows += 1
            size += record_size
    if rows or not any(tables.values()):
        yield part


def write_complete_export(store, start, end, out):
    from .reports import TZ, PROMPT, report, balance_text, _safe_sheet

    generated = datetime.now(TZ).isoformat()
    archive = financial_snapshot(store, start, end, generated)
    parts = list(partition_tables(archive["tables"]))
    summary = report(store, start, end, generated)
    current_summary = balance_text(store)
    files = []
    instructions = [
        {
            "qoida": "Qamrov",
            "izoh": "Barcha davrlarning to‘liq moliyaviy arxivi; Davr xulosasi faqat tanlangan davrga tegishli. Joriy holat — eksport vaqtidagi qoldiq.",
        },
        {
            "qoida": "Pul birligi",
            "izoh": "Pul maydonlari integer tiyin/sent. 100 ga bo‘ling; UZS va USD alohida. Kurs rate oddiy UZS/USD.",
        },
        {
            "qoida": "Hisoblash",
            "izoh": "Faqat active operatsiyalar. Tarix/tuzatishlarni takror hisoblamang. Zaxira kundalik sarflash mumkin bo‘lgan pul emas.",
        },
        {
            "qoida": "Fayllar",
            "izoh": "Barcha raqamlangan qismlarni birga yuklang; metadata/jamlar qismlarda takrorlanadi, ularni qayta qo‘shmang. manifest.json fayllar va satr sonlarini ko‘rsatadi.",
        },
        {
            "qoida": "Excel cheklovi",
            "izoh": "32 767 belgidan uzun katak davomining to‘liq qiymati JSON/TXT arxivida. Hech bir canonical yozuv JSON/TXTdan tushirilmaydi.",
        },
    ]
    for i, tables in enumerate(parts, 1):
        metadata = {
            **archive["metadata"],
            "part_index": i,
            "part_count": len(parts),
            "part_table_counts": {name: len(records) for name, records in tables.items()},
        }
        bundle = {"metadata": metadata, "analysis": archive["analysis"], "tables": tables}
        stem = f"hisobdon-{start}-full-{i:03d}"
        json_path = out / (stem + ".json")
        json_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        text_path = out / (stem + "-context.txt")
        with text_path.open("w", encoding="utf-8") as f:
            f.write(PROMPT + "\n\nTO‘LIQ MOLIYAVIY ARXIV — qism " + str(i) + " / " + str(len(parts)) + "\n")
            f.write("METADATA\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
            f.write("TANLANGAN DAVR XULOSASI\n" + summary + "\n\nJORIY HOLAT\n" + current_summary + "\n")
            f.write(
                "TAHLIL UCHUN HISOBLANGAN MA’LUMOT\n"
                + json.dumps(archive["analysis"], ensure_ascii=False, indent=2)
                + "\n"
            )
            for name, records in tables.items():
                f.write("\nJADVAL: " + name + " — to‘liq tarixning shu qismdagi yozuvlari\n")
                for record in records:
                    f.write(json.dumps({"table": name, "record": record}, ensure_ascii=False) + "\n")
        wb = Workbook()
        wb.remove(wb.active)
        _safe_sheet(wb, "Yo‘riqnoma", instructions)
        _safe_sheet(wb, "Davr xulosasi", [{"hisobot": line} for line in summary.splitlines()])
        _safe_sheet(wb, "Joriy holat", archive["analysis"]["current_balances"])
        _safe_sheet(wb, "Davr oxiri", archive["analysis"]["period_end_balances"])
        _safe_sheet(wb, "Oylik yozuvlar", archive["analysis"]["monthly_recorded_cashflow"])
        for name, records in tables.items():
            _safe_sheet(wb, SHEETS[name], records)
        xlsx_path = out / (stem + ".xlsx")
        wb.save(xlsx_path)
        for path in (xlsx_path, text_path, json_path):
            if path.stat().st_size > FILE_LIMIT:
                raise ValueError(
                    "Bitta arxiv qismi fayl limitidan oshdi; hech bir yozuv tashlab yuborilmadi."
                )
        files.extend([xlsx_path, text_path, json_path])
    manifest = {
        "format": "hisobdon-manifest-v1",
        "generated_at": generated,
        "requested_period": archive["metadata"]["requested_period"],
        "archive_scope": "full financial snapshot",
        "parts": len(parts),
        "table_counts": archive["metadata"]["table_counts"],
        "files": [
            {"name": p.name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in files
        ],
        "reading_order": "Read prompt in context TXT, verify all parts, then use JSON canonical records and Excel summaries. Same records in TXT/JSON/Excel are different representations, never extra transactions.",
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return files + [manifest_path]
