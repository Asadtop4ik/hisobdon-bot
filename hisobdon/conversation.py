"""Persistent, transport-independent Uzbek conversation state machine."""

import json
import secrets
from dataclasses import dataclass, field
from datetime import date, timedelta
from .ledger import Ledger, RuleError, LIQUID, INCOME, valid_day
from .money import money
from .parser import parse, parse_amount

LABELS = {
    "income": "Kirim",
    "expense": "Chiqim",
    "transfer": "O‘z hisoblarim orasida",
    "exchange": "Valyuta almashtirish",
    "lend": "Qarz berish",
    "borrow": "Qarz olish",
    "repay_lent": "Bergan qarzim qaytdi",
    "repay_borrowed": "Olgan qarzimni qaytarish",
    "invest": "Investitsiyaga qo‘shish",
    "withdraw": "Investitsiyadan olish",
    "invest_income": "Investitsiya daromadi",
    "interest_income": "Foiz daromadi",
    "interest_expense": "Foiz xarajati",
}
ACCOUNT_LABELS = {
    "cash": "Naqd",
    "card": "Karta",
    "debt_lent": "Menga qaytariladigan qarz",
    "debt_borrowed": "Men qaytaradigan qarz",
    "investment": "Investitsiya",
    "reserve": "Zaxira (uydagi naqd)",
}
ENTITY = {
    "lend": "debt_lent",
    "repay_lent": "debt_lent",
    "borrow": "debt_borrowed",
    "repay_borrowed": "debt_borrowed",
    "invest": "investment",
    "withdraw": "investment",
}


@dataclass
class Reply:
    text: str
    rows: list = field(default_factory=list)
    files: list = field(default_factory=list)
    export_range: tuple | None = None


def rows(options, n=2):
    return [options[i : i + n] for i in range(0, len(options), n)]


class Engine:
    def __init__(self, store, owner_id=0, export_dir=None):
        self.s = store
        self.ledger = Ledger(store)
        self.owner_id = owner_id
        self.export_dir = export_dir
        self.current_message_id = None

    def menu(self):
        return [
            Reply(
                "Hisobdon • Shaxsiy moliya\nXarajatni yozing: «bugun ovqat 40ming so‘m».\nBoshlash uchun hisoblaringiz va qoldiqlaringizni kiriting.",
                [
                    [("➕ Yozuv", "m:add"), ("💳 Hisoblar", "m:accounts")],
                    [("💰 Qoldiqlar", "m:balance"), ("🤝 Qarzlar", "m:debts")],
                    [("📈 Investitsiyalar", "m:investments"), ("🕓 Tarix", "h:0")],
                    [("📊 Hisobot", "m:reports"), ("📁 Eksport", "m:export")],
                    [("📝 Qoralamalar", "m:drafts"), ("⚙️ Sozlamalar", "m:settings")],
                    [("❓ Yordam", "m:help")],
                ],
            )
        ]

    def new(self, data):
        did = secrets.token_hex(4)
        data["rev"] = 0
        if data["mode"] == "operation" and self.current_message_id is not None:
            sources = data.setdefault("data", {}).setdefault("source_message_ids", [])
            if self.current_message_id not in sources:
                sources.append(self.current_message_id)
        self.s.save_draft(did, data)
        return did

    def ask(self, did, d, step, text, options=(), input_type=None):
        d.update(step=step, rev=d.get("rev", 0) + 1, input=input_type)
        d["options"] = {str(i): val for i, (_, val) in enumerate(options)}
        self.s.save_draft(did, d)
        if input_type:
            self.s.set("active_input", did)
        elif self.s.get("active_input") == did:
            self.s.set("active_input", None)
        buttons = [(label, f"d:{did}:{d['rev']}:{i}") for i, (label, _) in enumerate(options)]
        return [Reply(text, rows(buttons) + [[("Qoralamani bekor qilish", f"z:{did}"), ("Menyu", "m:menu")]])]

    def message(self, text, message_id, now):
        mid = self.s.record_message(self.owner_id, message_id, text, now.isoformat())
        self.current_message_id = mid
        text = text.strip()
        if text.startswith("/"):
            self.s.set("active_input", None)
            command = text.split()[0].split("@")[0][1:]
            if command == "cancel":
                return self.action("drafts", now)
            aliases = {
                "start": "menu",
                "help": "help",
                "accounts": "accounts",
                "balance": "balance",
                "add": "add",
                "debts": "debts",
                "investments": "investments",
                "history": "history",
                "export": "export",
                "today": "today",
                "week": "week",
                "month": "month",
                "settings": "settings",
                "drafts": "drafts",
            }
            return self.action(aliases.get(command, "menu"), now)
        active = self.s.get("active_input")
        d = self.s.draft(active) if active else None
        if d and d.get("input") and not d.get("done"):
            if d["mode"] == "operation":
                sources = d["data"].setdefault("source_message_ids", [])
                if mid not in sources:
                    sources.append(mid)
                self.s.save_draft(active, d)
            try:
                value = self.input_value(text, d["input"])
                self.s.conn.execute("UPDATE messages SET status='answer' WHERE id=?", (mid,))
                return self.accept(active, d, value, now)
            except (ValueError, ArithmeticError) as exc:
                return [Reply(str(exc) or "Qiymatni qayta kiriting.", [[("Menyu", "m:menu")]])]
        parsed = parse(text, now)
        if parsed.get("error"):
            self.s.conn.execute("UPDATE messages SET status='needs_clarification' WHERE id=?", (mid,))
            return [
                Reply(
                    parsed["error"] + "\nAsl xabar saqlandi. Qayta yozing yoki tugmalar bilan kiriting.",
                    [[("➕ Tugmalar bilan", "m:add")]],
                )
            ]
        if not parsed.get("category"):
            for alias in self.s.all("SELECT * FROM aliases"):
                if alias["word"].casefold() in text.casefold().split():
                    cat = self.s.one("SELECT kind FROM categories WHERE name=?", (alias["category"],))
                    if cat:
                        parsed.update(category=alias["category"], kind=cat["kind"])
        did = self.new({"mode": "operation", "data": {**parsed, "message_id": mid}})
        return self.advance(did, self.s.draft(did), now)

    @staticmethod
    def input_value(text, kind):
        if kind in {"amount", "opening", "fee", "valuation"}:
            amount = parse_amount(text)
            if amount < 0 or (kind == "amount" and amount == 0):
                raise ValueError("Musbat summa kiriting (qoldiq/komissiya uchun 0 mumkin).")
            return amount
        if kind in {"date", "due"}:
            day = date.fromisoformat(text).isoformat()
            if kind == "date":
                valid_day(day)
            return day
        if not text or len(text) > 1000:
            raise ValueError("Matn 1–1000 belgi bo‘lsin.")
        return text

    def callback(self, payload, now):
        self.current_message_id = None
        try:
            parts = payload.split(":")
            cmd = parts[0]
            if cmd == "m":
                self.s.set("active_input", None)
                return self.action(parts[1], now)
            if cmd == "d":
                _, did, rev, opt = parts
                d = self.s.draft(did)
                if not d or d.get("done") or d.get("rev") != int(rev) or opt not in d.get("options", {}):
                    return [
                        Reply("Bu tugma allaqachon ishlatilgan. /drafts yoki /history orqali davom eting.")
                    ]
                return self.accept(did, d, d["options"][opt], now)
            if cmd == "z":
                d = self.s.draft(parts[1])
                if d and not d.get("done"):
                    d["done"] = True
                    self.s.save_draft(parts[1], d)
                if self.s.get("active_input") == parts[1]:
                    self.s.set("active_input", None)
                return [Reply("Qoralama bekor qilindi. Qoldiq o‘zgarmadi.", [[("Menyu", "m:menu")]])]
            if cmd == "resume":
                d = self.s.draft(parts[1])
                if not d or d.get("done"):
                    return self.action("drafts", now)
                return self.advance(parts[1], d, now)
            if cmd == "h":
                return self.history(int(parts[1]))
            if cmd == "x":
                return [
                    Reply(
                        f"#{parts[1]} yozuvni bekor qilasizmi?",
                        [[("Ha, bekor qilish", f"xc:{parts[1]}"), ("Yo‘q", "h:0")]],
                    )
                ]
            if cmd == "xc":
                self.ledger.cancel(int(parts[1]))
                return [Reply("Yozuv bekor qilindi. Qoldiq qayta hisoblandi.", [[("Tarix", "h:0")]])]
            if cmd == "e":
                op = self.s.one("SELECT * FROM operations WHERE id=? AND status='active'", (int(parts[1]),))
                if not op:
                    raise RuleError("Yozuv faol emas.")
                data = json.loads(op["payload"])
                data["replaces"] = op["id"]
                did = self.new({"mode": "operation", "data": data, "editing": True})
                return self.edit_menu(did, self.s.draft(did))
            if cmd == "a":
                return self.account_detail(int(parts[1]))
            if cmd == "reserve":
                if parts[2] not in {"0", "1"}:
                    raise RuleError("Zaxira belgisi noto‘g‘ri.")
                self.ledger.set_reserve(int(parts[1]), parts[2] == "1")
                return self.account_detail(int(parts[1]))
            if cmd == "repay":
                debt = self.ledger.account(int(parts[1]))
                if debt["kind"] not in {"debt_lent", "debt_borrowed"} or debt["archived"]:
                    raise RuleError("Faol qarzni tanlang.")
                if self.ledger.balance(debt["id"]) <= 0:
                    return self.account_detail(debt["id"])
                did = self.new(
                    {
                        "mode": "operation",
                        "debt_first": True,
                        "data": {
                            "kind": "repay_lent" if debt["kind"] == "debt_lent" else "repay_borrowed",
                            "target": debt["id"],
                            "currency": debt["currency"],
                            "date": now.date().isoformat(),
                        },
                    }
                )
                return self.advance(did, self.s.draft(did), now)
            if cmd == "archive":
                a = self.ledger.account(int(parts[1]))
                if self.ledger.balance(a["id"]) != 0:
                    raise RuleError("Arxivlash uchun qoldiq 0 bo‘lsin.")
                self.s.conn.execute("UPDATE accounts SET archived=1 WHERE id=?", (a["id"],))
                self.s.audit("archive", a["id"], {})
                return [Reply("Hisob arxivlandi.", [[("Hisoblar", "m:accounts")]])]
            if cmd in {"opening", "value", "due"}:
                did = self.new({"mode": cmd, "account": int(parts[1]), "data": {}})
                return self.advance(did, self.s.draft(did), now)
            if cmd == "op":
                did = self.new(
                    {"mode": "operation", "data": {"kind": parts[1], "date": now.date().isoformat()}}
                )
                return self.advance(did, self.s.draft(did), now)
        except (ValueError, KeyError, IndexError) as exc:
            return [Reply(str(exc) or "Tugma eskirgan. Menyudan qayta boshlang.", [[("Menyu", "m:menu")]])]
        return self.menu()

    def accept(self, did, d, value, now):
        step = d["step"]
        data = d.setdefault("data", {})
        if (
            step == "account"
            and isinstance(value, dict)
            and value.get("split")
            and data.get("kind") == "expense"
        ):
            data["allocations"] = []
            return self.advance(did, d, now)
        if step == "split_account":
            if value == "restart":
                data["allocations"] = []
                data.pop("account", None)
                d.pop("split_account", None)
            else:
                d["split_account"] = value
            return self.advance(did, d, now)
        if step == "split_amount":
            remaining = data["amount"] - sum(p["amount"] for p in data["allocations"])
            if type(value) is not int or not 0 < value <= remaining:
                raise RuleError("Bu qism qolgan to‘lov summasidan oshmasin.")
            account = self.ledger.account(d["split_account"])
            data["allocations"].append({"account": account["id"], "amount": value})
            data["currency"] = account["currency"]
            d.pop("split_account", None)
            return self.advance(did, d, now)
        if (
            step == "category"
            and isinstance(value, dict)
            and value.get("operation") in {"repay_lent", "repay_borrowed"}
        ):
            data["kind"] = value["operation"]
            data.pop("category", None)
            data.pop("allocations", None)
            data.pop("account", None)
            data.pop("target", None)
            d.pop("split_account", None)
            d["debt_first"] = True
            return self.advance(did, d, now)
        if step == "amount" and value == "partial":
            return self.ask(did, d, "amount", "Qaytarilgan qismining summasini yozing:", input_type="amount")
        if step == "edit_field":
            if value == "save":
                d["editing"] = False
                return self.save_operation(did, d)
            data.pop(value, None)
            if value in {"account", "amount"} and "allocations" in data:
                data["allocations"] = []
                data.pop("account", None)
                d.pop("split_account", None)
            if value == "account" and data.get("kind") not in {"repay_lent", "repay_borrowed"}:
                data.pop("target", None)
            if value == "note":
                return self.ask(did, d, "note", "Yangi izohni yozing:", input_type="text")
            d["editing"] = False
            d["return_edit"] = True
            return self.advance(did, d, now)
        if step in {"date", "opened_on", "due"} and value == "custom":
            return self.ask(
                did,
                d,
                step,
                "Sanani YYYY-MM-DD shaklida yozing:",
                input_type="due" if step == "due" else "date",
            )
        if step == "category" and value == "new":
            return self.ask(did, d, "new_category", "Yangi kategoriya nomini yozing:", input_type="name")
        if step == "new_category":
            name = str(value).strip()[:60]
            self.s.conn.execute(
                "INSERT OR IGNORE INTO categories VALUES (?,?)",
                (name, "income" if data.get("kind") in INCOME else "expense"),
            )
            data["category"] = name
        elif step == "confirm":
            if value == "save":
                return self.finish(did, d, now)
        elif step == "negative":
            data["allow_negative"] = True
            return self.save_operation(did, d)
        else:
            data[step] = value
        d.pop("step", None)
        self.s.save_draft(did, d)
        return self.advance(did, d, now)

    def advance(self, did, d, now):
        data = d.setdefault("data", {})
        mode = d["mode"]
        today = now.date().isoformat()
        if mode == "account":
            if "kind" not in data:
                return self.ask(
                    did, d, "kind", "Qanday hisob ochamiz?", [(v, k) for k, v in ACCOUNT_LABELS.items()]
                )
            if "name" not in data:
                return self.ask(did, d, "name", "Hisob / kompaniya / odam nomini yozing:", input_type="name")
            if "currency" not in data:
                return self.ask(did, d, "currency", "Hisob valyutasi:", [("UZS", "UZS"), ("USD", "USD")])
            if "opening" not in data:
                return self.ask(
                    did,
                    d,
                    "opening",
                    "Boshlang‘ich qoldiqni yozing. Eski qarz uchun qolgan qarz; yangi qarz uchun 0. Bu kirim/chiqim bo‘lmaydi.",
                    input_type="opening",
                )
            if "opened_on" not in data:
                return self.ask(
                    did,
                    d,
                    "opened_on",
                    "Qoldiq qaysi sana boshiga tegishli?",
                    [("Bugun", today), ("Boshqa sana", "custom")],
                )
            if data["kind"].startswith("debt_") and "due" not in data:
                return self.ask(
                    did,
                    d,
                    "due",
                    "Qarzni qaytarish muddati:",
                    [("Muddatsiz", None), ("Sana kiritish", "custom")],
                )
            return self.ask(
                did,
                d,
                "confirm",
                f"{data['name']} • {ACCOUNT_LABELS[data['kind']]}\n{money(data['opening'], data['currency'])}\nBoshlanish: {data['opened_on']}\nSaqlaysizmi?",
                [("Saqlash", "save")],
            )
        if mode in {"opening", "value", "due", "rate", "category", "alias", "export_custom"}:
            return self.advance_setting(did, d, now)
        if mode == "operation":
            kind = data.get("kind")
            if not kind:
                return self.ask(did, d, "kind", "Bu qanday operatsiya?", [(v, k) for k, v in LABELS.items()])
            if d.get("debt_first") and kind in {"repay_lent", "repay_borrowed"} and not data.get("target"):
                debts = [
                    a
                    for a in self.ledger.balances()
                    if not a["archived"]
                    and a["kind"] == ENTITY[kind]
                    and a["balance"] > 0
                    and (not data.get("currency") or a["currency"] == data["currency"])
                ]
                if not debts:
                    return [
                        Reply(
                            "Mos ochiq qarz topilmadi. Avval qarzni boshlang‘ich qoldiq bilan kiriting.",
                            [[("Qarzlar", "m:debts"), ("Qoralamalar", "m:drafts")]],
                        )
                    ]
                return self.ask(
                    did,
                    d,
                    "target",
                    "Qaysi qarz qaytarildi?",
                    [(f"{a['name']} · {money(a['balance'], a['currency'])}", a["id"]) for a in debts],
                )
            if d.get("debt_first") and data.get("target"):
                data["currency"] = self.ledger.account(data["target"])["currency"]
            if not data.get("amount"):
                if kind in {"repay_lent", "repay_borrowed"} and data.get("target"):
                    debt = self.ledger.account(data["target"])
                    balance = self.ledger.balance(debt["id"])
                    if data.get("replaces"):
                        original = self.s.one(
                            "SELECT * FROM operations WHERE id=? AND status='active'", (data["replaces"],)
                        )
                        if (
                            original
                            and original["kind"] == kind
                            and json.loads(original["payload"]).get("target") == debt["id"]
                        ):
                            balance += original["amount"]
                    if balance <= 0:
                        return [
                            Reply("Bu qarz yopilgan. Yangi qaytarish yozilmaydi.", [[("Qarzlar", "m:debts")]])
                        ]
                    return self.ask(
                        did,
                        d,
                        "amount",
                        f"{debt['name']}\nQolgan qarz: {money(balance, debt['currency'])}\nQancha qaytarildi?",
                        [
                            (f"To‘liq — {money(balance, debt['currency'])}", balance),
                            ("Qisman qaytarish", "partial"),
                        ],
                        input_type="amount",
                    )
                return self.ask(
                    did, d, "amount", "Summani yozing (masalan: 40000 yoki 12.50):", input_type="amount"
                )
            if not data.get("date"):
                return self.ask(
                    did,
                    d,
                    "date",
                    "Operatsiya sanasi:",
                    [
                        ("Bugun", today),
                        ("Kecha", (now.date() - timedelta(days=1)).isoformat()),
                        ("Boshqa sana", "custom"),
                    ],
                )
            if kind in {"income", "expense"} and not data.get("category"):
                cats = self.s.all("SELECT name FROM categories WHERE kind=? ORDER BY rowid", (kind,))
                repayment = (
                    ("Qarz qaytdi", {"operation": "repay_lent"})
                    if kind == "income"
                    else ("Qarzni qaytardim", {"operation": "repay_borrowed"})
                )
                return self.ask(
                    did,
                    d,
                    "category",
                    f"{LABELS[kind]} • {money(data['amount'], data.get('currency', ''))}\nKategoriyani tanlang:",
                    [repayment] + [(c["name"], c["name"]) for c in cats] + [("Yangi kategoriya", "new")],
                )
            if kind == "expense" and "allocations" in data:
                split_reply = self.advance_split(did, d)
                if split_reply is not None:
                    return split_reply
            if not data.get("account"):
                kinds = {"investment"} if kind == "invest_income" else LIQUID
                accounts = [
                    a
                    for a in self.ledger.balances()
                    if not a["archived"]
                    and a["kind"] in kinds
                    and (not a["is_reserve"] or kind in {"transfer", "exchange"})
                    and (not data.get("currency") or a["currency"] == data["currency"])
                ]
                if not accounts:
                    return [
                        Reply(
                            "Mos hisob hali yo‘q. Avval hisob oching, keyin /drafts orqali davom eting.",
                            [[("Hisob qo‘shish", "m:newaccount"), ("Qoralamalar", "m:drafts")]],
                        )
                    ]
                account_question = (
                    "Pul qayerga tushdi — karta yoki naqd?"
                    if kind == "repay_lent"
                    else "Pul qaysi hisobdan qaytarildi — karta yoki naqd?"
                    if kind == "repay_borrowed"
                    else "Hisobni tanlang:"
                )
                return self.ask(
                    did,
                    d,
                    "account",
                    f"{LABELS[kind]} • {money(data['amount'], data.get('currency', ''))} • {data.get('category', '')}\nSana: {data['date']}\n{account_question}",
                    [(f"{a['name']} · {money(a['balance'], a['currency'])}", a["id"]) for a in accounts]
                    + ([("Bo‘lib to‘lash — naqd + karta", {"split": True})] if kind == "expense" else []),
                )
            a = self.ledger.account(data["account"])
            data["currency"] = a["currency"]
            if kind in {"transfer", "exchange", *ENTITY} and not data.get("target"):
                target_kind = ENTITY.get(kind)
                accounts = [
                    b
                    for b in self.ledger.balances()
                    if not b["archived"]
                    and b["id"] != a["id"]
                    and ((b["kind"] == target_kind) if target_kind else b["kind"] in LIQUID)
                    and (kind not in {"repay_lent", "repay_borrowed"} or b["balance"] > 0)
                    and (
                        (b["currency"] != a["currency"])
                        if kind == "exchange"
                        else b["currency"] == a["currency"]
                    )
                ]
                if not accounts:
                    return [
                        Reply(
                            "Mos qabul qiluvchi/qarz/investitsiya hisobi yo‘q. Hisob ochib /drafts’dan davom eting.",
                            [[("Hisob qo‘shish", "m:newaccount")]],
                        )
                    ]
                return self.ask(
                    did,
                    d,
                    "target",
                    "Tegishli hisob yoki qarzni tanlang:",
                    [(f"{b['name']} · {money(b['balance'], b['currency'])}", b["id"]) for b in accounts],
                )
            if kind == "invest_income" and "target" not in data:
                accounts = [
                    b
                    for b in self.ledger.balances()
                    if not b["archived"]
                    and b["kind"] in LIQUID
                    and b["currency"] == a["currency"]
                    and not b["is_reserve"]
                ]
                return self.ask(
                    did,
                    d,
                    "target",
                    "Daromad qayerda qoladi?",
                    [("Investitsiya ichida", 0)] + [(b["name"], b["id"]) for b in accounts],
                )
            if kind == "exchange" and not data.get("received"):
                currency = self.ledger.account(data["target"])["currency"]
                return self.ask(did, d, "received", f"Qancha {currency} olindi?", input_type="amount")
            if kind in {"transfer", "exchange"} and "fee" not in data:
                return self.ask(
                    did,
                    d,
                    "fee",
                    f"Manba hisobdan komissiya ({a['currency']}). 0 bo‘lsa tugmani bosing yoki summani yozing:",
                    [("Komissiyasiz", 0)],
                    input_type="fee",
                )
            if d.pop("return_edit", False) or d.get("editing"):
                d["editing"] = True
                return self.edit_menu(did, d)
            if kind not in {"income", "expense"} or data.get("replaces") or "allocations" in data:
                return self.ask(
                    did, d, "confirm", self.preview(data) + "\nSaqlaysizmi?", [("Saqlash", "save")]
                )
            return self.save_operation(did, d)
        return self.menu()

    def advance_split(self, did, d):
        data = d["data"]
        parts = data["allocations"]
        remaining = data["amount"] - sum(p["amount"] for p in parts)
        if remaining == 0 and parts:
            data["account"] = parts[0]["account"]
            return None
        if remaining <= 0:
            raise RuleError("To‘lov qismlari jami summadan oshdi.")
        if d.get("split_account"):
            account = self.ledger.account(d["split_account"])
            return self.ask(
                did,
                d,
                "split_amount",
                f"{account['name']}: qancha to‘landi?\nQolgan: {money(remaining, account['currency'])}",
                [(f"Qolgan {money(remaining, account['currency'])}", remaining)],
                input_type="amount",
            )
        used = {p["account"] for p in parts}
        accounts = [
            a
            for a in self.ledger.balances()
            if a["kind"] in LIQUID
            and not a["is_reserve"]
            and not a["archived"]
            and a["id"] not in used
            and (not data.get("currency") or a["currency"] == data["currency"])
        ]
        options = [(f"{a['name']} · {money(a['balance'], a['currency'])}", a["id"]) for a in accounts]
        if parts:
            options.append(("Qismlarni boshidan kiritish", "restart"))
        text = f"Bo‘lib to‘lash\nJami: {money(data['amount'], data.get('currency', ''))}\nQolgan: {money(remaining, data.get('currency', ''))}\nKeyingi to‘lov hisobini tanlang:"
        if not accounts:
            text += "\nBoshqa mos hisob yo‘q. Qismlarni qayta kiriting yoki /accounts orqali hisob qo‘shing."
        return self.ask(did, d, "split_account", text, options)

    def edit_menu(self, did, d):
        fields = [("Summa", "amount"), ("Sana", "date"), ("Hisob", "account"), ("Izoh", "note")]
        if d["data"]["kind"] in {"income", "expense"}:
            fields.append(("Kategoriya", "category"))
        if d["data"]["kind"] == "exchange":
            fields.append(("Olingan summa", "received"))
        if d["data"]["kind"] in {"transfer", "exchange"}:
            fields.append(("Komissiya", "fee"))
        return self.ask(
            did,
            d,
            "edit_field",
            self.preview(d["data"]) + "\nQaysi maydonni o‘zgartiramiz?",
            fields + [("O‘zgarishni saqlash", "save")],
        )

    def preview(self, data):
        a = self.ledger.account(data["account"])
        text = f"{LABELS.get(data['kind'], data['kind'])}: {money(data['amount'], a['currency'])}\nHisob: {a['name']}\nSana: {data['date']}"
        if data.get("target"):
            b = self.ledger.account(data["target"])
            text += f"\nTegishli hisob: {b['name']}"
            if data.get("received"):
                text += f" · {money(data['received'], b['currency'])}"
        if data.get("category"):
            text += f"\nKategoriya: {data['category']}"
        if data.get("allocations"):
            text += "\nTo‘lov qismlari:"
            for part in data["allocations"]:
                account = self.ledger.account(part["account"])
                text += f"\n  {account['name']}: {money(part['amount'], account['currency'])}"
        if data.get("fee"):
            text += f"\nKomissiya: {money(data['fee'], a['currency'])}"
        if data.get("note"):
            text += "\nIzoh: " + data["note"][:500]
        return text

    def save_operation(self, did, d):
        data = d["data"]
        try:
            if data.get("replaces"):
                op = self.ledger.replace(data["replaces"], data, "draft:" + did)
            else:
                op = self.ledger.post(data, "draft:" + did)
        except RuleError as exc:
            if str(exc).startswith("Qoldiq yetarli emas."):
                return self.ask(did, d, "negative", str(exc), [("Manfiy qoldiqni tasdiqlash", True)])
            self.s.save_draft(did, d)
            return [Reply(str(exc), [[("Qoralamalar", "m:drafts"), ("Menyu", "m:menu")]])]
        self.done(did, d)
        a = self.ledger.account(data["account"])
        balance_result = f"Qoldiq: {money(self.ledger.balance(a['id']), a['currency'])}"
        if data.get("allocations"):
            balance_result = "Hisoblar qoldig‘i:"
            for part in data["allocations"]:
                account = self.ledger.account(part["account"])
                balance_result += (
                    f"\n  {account['name']}: {money(self.ledger.balance(account['id']), account['currency'])}"
                )
        debt_result = ""
        extra_buttons = []
        if data["kind"] in {"repay_lent", "repay_borrowed"}:
            debt = self.ledger.account(data["target"])
            remaining = self.ledger.balance(debt["id"])
            debt_result = (
                f"\nQolgan qarz: {money(remaining, debt['currency'])}"
                if remaining
                else "\nQarz to‘liq yopildi. Tarix saqlandi."
            )
            extra_buttons = [[("Qarzni ko‘rish", f"a:{debt['id']}"), ("Qarzlar", "m:debts")]]
        return [
            Reply(
                f"Saqlandi #{op}\n{self.preview(data)}\n{balance_result}{debt_result}",
                [[("Tuzatish", f"e:{op}"), ("Bekor qilish", f"x:{op}")]]
                + extra_buttons
                + [[("Menyu", "m:menu")]],
            )
        ]

    def done(self, did, d):
        d["done"] = True
        self.s.save_draft(did, d)
        if self.s.get("active_input") == did:
            self.s.set("active_input", None)

    def finish(self, did, d, now):
        data = d["data"]
        mode = d["mode"]
        with self.s.transaction():
            if mode == "operation":
                return self.save_operation(did, d)
            if mode == "account":
                aid = self.ledger.create_account(
                    data["name"],
                    data["currency"],
                    data["opening"],
                    data["opened_on"],
                    "cash" if data["kind"] == "reserve" else data["kind"],
                    data.get("due"),
                    is_reserve=data["kind"] == "reserve",
                )
                self.done(did, d)
                return self.account_detail(aid)
            return self.finish_setting(did, d, now)

    def accounts(self, kinds, closed=False):
        acc = [a for a in self.ledger.balances() if a["kind"] in kinds and not a["archived"]]
        debts = kinds == {"debt_lent", "debt_borrowed"}
        if debts:
            acc = [a for a in acc if (a["balance"] == 0 if closed else a["balance"] > 0)]
        title = ("Yopilgan qarzlar" if closed else "Ochiq qarzlar") if debts else "Hisoblar"
        text = (
            title
            + "\n"
            + (
                "\n".join(f"{a['name']}: {money(a['balance'], a['currency'])}" for a in acc)
                or "Hozircha yo‘q."
            )
        )
        extra = (
            [[("Ochiq qarzlar", "m:debts") if closed else ("Yopilgan qarzlar", "m:debts_closed")]]
            if debts
            else []
        )
        return [
            Reply(
                text or "Hisob yo‘q.",
                rows([(a["name"], f"a:{a['id']}") for a in acc])
                + extra
                + [[("Hisob qo‘shish", "m:newaccount"), ("Menyu", "m:menu")]],
            )
        ]

    def account_detail(self, aid):
        a = self.ledger.account(aid)
        buttons = [("Boshlang‘ich qoldiqni tuzatish", f"opening:{aid}")]
        status = ""
        if a["kind"] in LIQUID:
            status = "\nMaqsad: " + (
                "Zaxira — kundalik sarfga kirmaydi" if a["is_reserve"] else "Kundalik hisob"
            )
            if not a["archived"]:
                buttons.append(
                    (
                        "Kundalik hisob qilish" if a["is_reserve"] else "Zaxira deb belgilash",
                        f"reserve:{aid}:{0 if a['is_reserve'] else 1}",
                    )
                )
        if a["kind"] == "investment":
            buttons.append(("Joriy qiymatni kiritish", f"value:{aid}"))
        if a["kind"].startswith("debt_"):
            remaining = self.ledger.balance(aid)
            status = "\nHolat: " + ("Yopilgan — tarix saqlanadi" if remaining == 0 else "Ochiq")
            if remaining > 0 and not a["archived"]:
                label = "Qaytarilgan pulni kiritish" if a["kind"] == "debt_lent" else "Qarzni qaytarish"
                buttons.insert(0, (label, f"repay:{aid}"))
            buttons.append(("Muddatni belgilash", f"due:{aid}"))
        buttons.append(("Arxivlash", f"archive:{aid}"))
        return [
            Reply(
                f"{a['name']} • {ACCOUNT_LABELS[a['kind']]}\nQoldiq: {money(self.ledger.balance(aid), a['currency'])}\nBoshlang‘ich: {money(a['opening'], a['currency'])} / {a['opened_on']}\nMuddat: {a['due'] or '—'}{status}",
                rows(buttons) + [[("Menyu", "m:menu")]],
            )
        ]

    def history(self, offset=0):
        ops = self.s.all("SELECT * FROM operations ORDER BY id DESC LIMIT 8 OFFSET ?", (max(0, offset),))
        replies = []
        for op in ops:
            data = json.loads(op["payload"])
            replies.append(
                Reply(
                    f"#{op['id']} • {op['status']}\n{self.preview(data)}",
                    [[("Tuzatish", f"e:{op['id']}"), ("Bekor qilish", f"x:{op['id']}")]]
                    if op["status"] == "active"
                    else [],
                )
            )
        replies.append(
            Reply("Tarix", [[("Keyingi", f"h:{offset + 8}"), ("Boshi", "h:0")], [("Menyu", "m:menu")]])
        )
        return replies

    def action(self, name, now):
        if name in {"menu", "start"}:
            return self.menu()
        if name == "help":
            return [
                Reply(
                    "Misol: bugun ovqat abetga 40ming so‘m.\nBot yetishmagan ma’lumotni so‘raydi. Har safar kartani/naqd hisobni tanlaysiz.\n\nAvval hisoblarni oching: nom, UZS/USD, boshlang‘ich qoldiq va sana. Eski qarz/investitsiya shu yerda ochiladi. Yangi qarz olish/berish uchun «Yozuv» menyusini ishlating.\n\n/start — menyu\n/accounts — hisoblar\n/add — barcha operatsiyalar\n/balance — qoldiqlar\n/history — tuzatish/bekor qilish\n/drafts — qoralamalar\n/today /week /month — hisobot\n/export — Excel + AI prompt va xabarlar\n/settings — kurs, kategoriyalar, eslatmalar\n\nBir xabar — bir operatsiya. Telegram xabarini tahrirlash hisobni o‘zgartirmaydi: botdagi Tuzatish tugmasidan foydalaning. Foiz va asosiy qarzni alohida yozing.",
                    [[("Menyu", "m:menu")]],
                )
            ]
        if name == "accounts":
            return self.accounts(LIQUID)
        if name == "debts":
            return self.accounts({"debt_lent", "debt_borrowed"})
        if name == "debts_closed":
            return self.accounts({"debt_lent", "debt_borrowed"}, closed=True)
        if name == "investments":
            return self.accounts({"investment"})
        if name in {"newaccount", "add"}:
            did = self.new(
                {
                    "mode": "account" if name == "newaccount" else "operation",
                    "data": {} if name == "newaccount" else {"date": now.date().isoformat()},
                }
            )
            return self.advance(did, self.s.draft(did), now)
        if name == "balance":
            from .reports import balance_text

            return [Reply(balance_text(self.s), [[("Menyu", "m:menu")]])]
        if name == "history":
            return self.history()
        if name == "drafts":
            ds = [
                (r["id"], json.loads(r["data"]))
                for r in self.s.all("SELECT * FROM drafts ORDER BY updated_at DESC")
            ]
            opts = [
                (f"{d['data'].get('note', d['mode'])[:35]}", f"resume:{did}")
                for did, d in ds
                if not d.get("done")
            ]
            return [
                Reply("Tugallanmagan qoralamalar: " + str(len(opts)), rows(opts, 1) + [[("Menyu", "m:menu")]])
            ]
        if name == "reports":
            return [
                Reply(
                    "Hisobot davri:",
                    [
                        [("Bugun", "m:today"), ("Shu hafta", "m:week")],
                        [("Shu oy", "m:month"), ("Eksport", "m:export")],
                    ],
                )
            ]
        if name in {"today", "week", "month"}:
            from .reports import report

            start = now.date()
            if name == "week":
                start -= timedelta(days=start.weekday())
            if name == "month":
                start = start.replace(day=1)
            return [
                Reply(
                    report(
                        self.s,
                        start.isoformat(),
                        (now.date() + timedelta(days=1)).isoformat(),
                        now.isoformat(),
                    ),
                    [[("Menyu", "m:menu")]],
                )
            ]
        if name == "export":
            return [
                Reply(
                    "Excel va AI uchun TXT eksport:",
                    [
                        [("Shu oy", "m:export_month"), ("Oldingi oy", "m:export_previous")],
                        [("Barcha davr", "m:export_all"), ("Boshqa davr", "m:export_custom")],
                    ],
                )
            ]
        if name.startswith("export_"):
            if name == "export_custom":
                did = self.new({"mode": name, "data": {}})
                return self.advance(did, self.s.draft(did), now)
            start = now.date().replace(day=1)
            end = now.date() + timedelta(days=1)
            if name == "export_previous":
                end = start
                start = (start - timedelta(days=1)).replace(day=1)
            if name == "export_all":
                first = self.s.one("SELECT MIN(opened_on) AS day FROM accounts")["day"]
                first_message = self.s.one("SELECT MIN(received_at) AS at FROM messages")["at"]
                start = date.fromisoformat(
                    min(first or now.date().isoformat(), (first_message or now.isoformat())[:10])
                )
            return self.make_export(start.isoformat(), end.isoformat())
        if name == "settings":
            enabled = self.s.get("notifications", True)
            return [
                Reply(
                    f"Vaqt: Asia/Tashkent\nKunlik 22:00 • Dushanba 09:00 • Oy 1-kuni 09:00\nBildirishnomalar: {'yoqilgan' if enabled else 'o‘chirilgan'}",
                    [
                        [("Kurs kiritish", "m:rate"), ("Kategoriya qo‘shish", "m:category")],
                        [("Kalit so‘z bog‘lash", "m:alias"), ("Bildirishnomani almashtirish", "m:toggle")],
                        [("Diagnostika", "m:status"), ("Menyu", "m:menu")],
                    ],
                )
            ]
        if name == "toggle":
            self.s.set("notifications", not self.s.get("notifications", True))
            return self.action("settings", now)
        if name in {"rate", "category", "alias"}:
            did = self.new({"mode": name, "data": {}})
            return self.advance(did, self.s.draft(did), now)
        if name == "status":
            pending = self.s.one("SELECT COUNT(*) AS n FROM jobs WHERE status!='sent'")["n"]
            return [
                Reply(
                    f"Kutilayotgan vazifalar: {pending}\nOxirgi backup: {self.s.get('last_backup', 'hali yo‘q')}\nVersiya: {self.s.get('version', 'local')}\nQoralamalar /drafts orqali."
                )
            ]
        return self.menu()

    def advance_setting(self, did, d, now):
        mode = d["mode"]
        data = d["data"]
        today = now.date().isoformat()
        if mode in {"opening", "value"}:
            field = "opening" if mode == "opening" else "valuation"
            if field not in data:
                return self.ask(did, d, field, "Yangi qiymatni yozing:", input_type=field)
            if "date" not in data:
                return self.ask(
                    did, d, "date", "Qiymat sanasi:", [("Bugun", today), ("Boshqa sana", "custom")]
                )
        elif mode == "due":
            if "due" not in data:
                return self.ask(
                    did, d, "due", "Qaytarish muddati:", [("Muddatsiz", None), ("Sana kiritish", "custom")]
                )
        elif mode == "rate":
            if "rate" not in data:
                return self.ask(did, d, "rate", "1 USD necha UZS? Masalan: 12800", input_type="text")
            if "date" not in data:
                return self.ask(did, d, "date", "Kurs sanasi:", [("Bugun", today), ("Boshqa sana", "custom")])
        elif mode == "category":
            if "kind" not in data:
                return self.ask(
                    did, d, "kind", "Kategoriya turi:", [("Chiqim", "expense"), ("Kirim", "income")]
                )
            if "name" not in data:
                return self.ask(did, d, "name", "Kategoriya nomi:", input_type="name")
        elif mode == "alias":
            if "word" not in data:
                return self.ask(did, d, "word", "Bitta kalit so‘z yozing:", input_type="text")
            if "category" not in data:
                return self.ask(
                    did,
                    d,
                    "category",
                    "Qaysi kategoriya?",
                    [(c["name"], c["name"]) for c in self.s.all("SELECT name FROM categories")],
                )
        elif mode == "export_custom":
            if "start" not in data:
                return self.ask(did, d, "start", "Boshlanish sanasi YYYY-MM-DD:", input_type="date")
            if "end" not in data:
                return self.ask(
                    did, d, "end", "Oxirgi sana YYYY-MM-DD (shu kun ham kiradi):", input_type="date"
                )
        return self.ask(
            did,
            d,
            "confirm",
            "Ma’lumot:\n" + "\n".join(f"{k}: {v}" for k, v in data.items()),
            [("Saqlash", "save")],
        )

    def finish_setting(self, did, d, now):
        data = d["data"]
        mode = d["mode"]
        if mode == "opening":
            self.ledger.update_opening(d["account"], data["opening"], data["date"])
        elif mode == "value":
            self.ledger.value(d["account"], data["valuation"], data["date"])
        elif mode == "due":
            self.s.conn.execute("UPDATE accounts SET due=? WHERE id=?", (data["due"], d["account"]))
            self.s.audit("due_update", d["account"], data)
        elif mode == "rate":
            self.ledger.rate(data["rate"].replace(",", "."), data["date"])
        elif mode == "category":
            if len(data["name"]) > 60:
                raise RuleError("Kategoriya nomi 60 belgidan oshmasin.")
            self.s.conn.execute("INSERT OR IGNORE INTO categories VALUES (?,?)", (data["name"], data["kind"]))
        elif mode == "alias":
            if len(data["word"].split()) != 1:
                raise RuleError("Bitta so‘z kiriting.")
            self.s.conn.execute(
                "INSERT INTO aliases VALUES (?,?) ON CONFLICT(word) DO UPDATE SET category=excluded.category",
                (data["word"].casefold(), data["category"]),
            )
        elif mode == "export_custom":
            end = (date.fromisoformat(data["end"]) + timedelta(days=1)).isoformat()
            if data["start"] >= end:
                raise RuleError("Boshlanish oxirgi sanadan oldin bo‘lsin.")
            self.done(did, d)
            return self.make_export(data["start"], end)
        self.done(did, d)
        return [Reply("Saqlandi.", [[("Menyu", "m:menu")]])]

    def make_export(self, start, end):
        # Transport generates the snapshot after the conversation transaction commits.
        return [
            Reply(
                f"Davr xulosasi: {start} — {(date.fromisoformat(end) - timedelta(days=1)).isoformat()}\nExcel + tayyor promptli TXT + JSON: barcha davrlarning to‘liq moliyaviy arxivi. Barcha qismlarni birga yuklang; bir xil yozuvlarni fayllar orasida takror hisoblamang.",
                export_range=(start, end),
            )
        ]
