import json
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo
from datetime import datetime
from .db import utcnow
from .money import MAX_AMOUNT

KINDS = {"cash", "card", "investment", "debt_lent", "debt_borrowed"}
LIQUID = {"cash", "card"}
INCOME = {"income", "invest_income", "interest_income"}
EXPENSE = {"expense", "interest_expense"}


class RuleError(ValueError):
    pass


def valid_day(value):
    try:
        parsed = date.fromisoformat(value)
        if parsed > datetime.now(ZoneInfo("Asia/Tashkent")).date():
            raise RuleError("Kelajak sanasiga operatsiya yozilmaydi.")
        return parsed.isoformat()
    except (ValueError, TypeError) as exc:
        raise RuleError("Sana YYYY-MM-DD shaklida, bugun yoki oldin bo‘lsin.") from exc


def positive(value):
    if type(value) is not int or not 0 < value <= MAX_AMOUNT:
        raise RuleError("Summa musbat va ruxsat etilgan oraliqda bo‘lsin.")
    return value


class Ledger:
    def __init__(self, store):
        self.store = store

    def create_account(self, name, currency, opening, at, kind="cash", due=None):
        at = valid_day(at)
        if kind not in KINDS or currency not in {"UZS", "USD"}:
            raise RuleError("Hisob turi yoki valyutasi noto‘g‘ri.")
        if not name.strip() or len(name) > 80:
            raise RuleError("Hisob nomi 1–80 belgi bo‘lsin.")
        if type(opening) is not int or opening < 0 or opening > MAX_AMOUNT:
            raise RuleError("Boshlang‘ich qoldiq manfiy bo‘lmasin.")
        if due:
            date.fromisoformat(due)
        with self.store.transaction():
            cur = self.store.conn.execute(
                "INSERT INTO accounts(name,currency,kind,opening,opened_on,due,created_at) VALUES (?,?,?,?,?,?,?)",
                (name.strip(), currency, kind, opening, at, due, utcnow()),
            )
            self.store.audit("account_create", cur.lastrowid, {"opening": opening, "day": at})
            return cur.lastrowid

    def account(self, account_id):
        acc = self.store.one("SELECT * FROM accounts WHERE id=?", (account_id,))
        if not acc:
            raise RuleError("Hisob topilmadi.")
        return acc

    def balance(self, account_id, as_of=None):
        acc = self.account(account_id)
        if as_of and acc["opened_on"] >= as_of:
            return 0
        sql = "SELECT COALESCE(SUM(m.amount),0) AS total FROM movements m JOIN operations o ON o.id=m.operation_id WHERE m.account_id=? AND o.status='active'"
        params = [account_id]
        if as_of:
            sql += " AND o.day<?"
            params.append(as_of)
        return acc["opening"] + self.store.one(sql, params)["total"]

    def balances(self, as_of=None):
        return [
            {**a, "balance": self.balance(a["id"], as_of)}
            for a in self.store.all("SELECT * FROM accounts ORDER BY id")
            if not as_of or a["opened_on"] < as_of
        ]

    def _validate_principals(self):
        # Validate every historical prefix, not just the present balance.
        parents = {
            r["id"]: r["replaces"] for r in self.store.all("SELECT id,replaces FROM operations ORDER BY id")
        }
        roots = {}
        for operation_id, parent in parents.items():
            roots[operation_id] = roots[parent] if parent else operation_id
        for a in self.store.all("SELECT * FROM accounts WHERE kind NOT IN ('cash','card')"):
            total = a["opening"]
            movements = self.store.all(
                "SELECT m.amount,m.id AS movement_id,o.id AS operation_id,o.day FROM movements m JOIN operations o ON o.id=m.operation_id WHERE m.account_id=? AND o.status='active'",
                (a["id"],),
            )
            for row in sorted(
                movements, key=lambda r: (r["day"], roots[r["operation_id"]], r["movement_id"])
            ):
                total += row["amount"]
                if total < 0:
                    raise RuleError(
                        "Qarz/investitsiya qoldig‘i yetarli emas yoki keyingi harakatga zid. Avval bog‘liq harakatni tuzating."
                    )

    def post(self, data, key):
        with self.store.transaction():
            exists = self.store.one("SELECT id FROM operations WHERE idem_key=?", (key,))
            if exists:
                return exists["id"]
            d = dict(data)
            amount = positive(d.get("amount"))
            day = valid_day(d.get("date"))
            a = self.account(d.get("account"))
            b = self.account(d["target"]) if d.get("target") else None
            for acc in [a] + ([b] if b else []):
                if acc["archived"] or day < acc["opened_on"]:
                    raise RuleError("Hisob arxivlangan yoki sana boshlang‘ich qoldiq sanasidan oldin.")
            if b and a["id"] == b["id"]:
                raise RuleError("Manba va qabul hisobi boshqa bo‘lsin.")
            kind = d.get("kind")
            postings = []
            if kind in {"income", "expense", "interest_income", "interest_expense"}:
                if a["kind"] not in LIQUID:
                    raise RuleError("Karta yoki naqd hisobni tanlang.")
                postings = [(a["id"], amount if kind in INCOME else -amount)]
            elif kind in {"transfer", "exchange"}:
                if not b or a["kind"] not in LIQUID or b["kind"] not in LIQUID:
                    raise RuleError("Ikkita pul hisobini tanlang.")
                if (kind == "transfer") != (a["currency"] == b["currency"]):
                    raise RuleError("Valyutalar uchun mos o‘tkazma turini tanlang.")
                received = amount if kind == "transfer" else positive(d.get("received"))
                postings = [(a["id"], -amount), (b["id"], received)]
            elif kind in {"lend", "borrow", "repay_lent", "repay_borrowed", "invest", "withdraw"}:
                expected = {
                    "lend": "debt_lent",
                    "repay_lent": "debt_lent",
                    "borrow": "debt_borrowed",
                    "repay_borrowed": "debt_borrowed",
                    "invest": "investment",
                    "withdraw": "investment",
                }[kind]
                if (
                    not b
                    or a["kind"] not in LIQUID
                    or b["kind"] != expected
                    or a["currency"] != b["currency"]
                ):
                    raise RuleError("Pul va qarz/investitsiya hisoblari turi va valyutasi mos bo‘lsin.")
                cash_sign = 1 if kind in {"borrow", "repay_lent", "withdraw"} else -1
                entity_sign = -1 if kind in {"repay_lent", "repay_borrowed", "withdraw"} else 1
                postings = [(a["id"], cash_sign * amount), (b["id"], entity_sign * amount)]
            elif kind == "invest_income":
                if a["kind"] != "investment":
                    raise RuleError("Investitsiya hisobini tanlang.")
                if b and (b["kind"] not in LIQUID or b["currency"] != a["currency"]):
                    raise RuleError("Daromad oluvchi pul hisobi mos emas.")
                postings = [((b or a)["id"], amount)]
            else:
                raise RuleError("Operatsiya turi noma’lum.")
            fee = d.get("fee", 0)
            if type(fee) is not int or fee < 0 or fee > MAX_AMOUNT:
                raise RuleError("Komissiya noto‘g‘ri.")
            if fee:
                if kind not in {"transfer", "exchange"}:
                    raise RuleError("Komissiya faqat o‘tkazmada; boshqa holatda alohida xarajat yozing.")
                postings.append((a["id"], -fee))
            totals = {}
            for account_id, delta in postings:
                totals[account_id] = totals.get(account_id, 0) + delta
            for account_id, delta in totals.items():
                acc = self.account(account_id)
                if (
                    acc["kind"] in LIQUID
                    and delta < 0
                    and self.balance(account_id) + delta < 0
                    and not d.get("allow_negative")
                ):
                    raise RuleError("Qoldiq yetarli emas. Tekshiring yoki manfiy qoldiqni tasdiqlang.")
            cur = self.store.conn.execute(
                "INSERT INTO operations(idem_key,kind,day,amount,currency,category,note,payload,message_id,replaces,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    key,
                    kind,
                    day,
                    amount,
                    a["currency"],
                    d.get("category", ""),
                    d.get("note", ""),
                    json.dumps(d, ensure_ascii=False),
                    d.get("message_id"),
                    d.get("replaces"),
                    utcnow(),
                ),
            )
            opid = cur.lastrowid
            self.store.conn.executemany(
                "INSERT INTO movements(operation_id,account_id,amount) VALUES (?,?,?)",
                [(opid, account_id, delta) for account_id, delta in postings],
            )
            self._validate_principals()
            self.store.audit("post", opid, d)
            if d.get("message_id"):
                self.store.conn.execute("UPDATE messages SET status='posted' WHERE id=?", (d["message_id"],))
            return opid

    def cancel(self, operation_id):
        with self.store.transaction():
            op = self.store.one("SELECT * FROM operations WHERE id=?", (operation_id,))
            if not op:
                raise RuleError("Yozuv topilmadi.")
            if op["status"] == "cancelled":
                return
            self.store.conn.execute("UPDATE operations SET status='cancelled' WHERE id=?", (operation_id,))
            self._validate_principals()
            self.store.audit("cancel", operation_id, {})
            if op["message_id"]:
                self.store.conn.execute(
                    "UPDATE messages SET status='cancelled' WHERE id=?", (op["message_id"],)
                )

    def replace(self, operation_id, data, key):
        with self.store.transaction():
            existing = self.store.one("SELECT id FROM operations WHERE idem_key=?", (key,))
            if existing:
                return existing["id"]
            op = self.store.one("SELECT * FROM operations WHERE id=?", (operation_id,))
            if not op or op["status"] != "active":
                raise RuleError("Yozuv allaqachon o‘zgargan yoki bekor qilingan.")
            # Validate principal history after the complete replacement, never between its two halves.
            self.store.conn.execute("UPDATE operations SET status='cancelled' WHERE id=?", (operation_id,))
            newid = self.post({**data, "replaces": operation_id}, key)
            self.store.audit("replace", operation_id, {"new_id": newid})
            return newid

    def update_opening(self, account_id, amount, day):
        valid_day(day)
        if type(amount) is not int or amount < 0 or amount > MAX_AMOUNT:
            raise RuleError("Boshlang‘ich qoldiq noto‘g‘ri.")
        with self.store.transaction():
            old = self.account(account_id)
            earlier = self.store.one(
                "SELECT MIN(o.day) AS first FROM movements m JOIN operations o ON o.id=m.operation_id WHERE m.account_id=?",
                (account_id,),
            )["first"]
            if earlier and day > earlier:
                raise RuleError("Yangi sana mavjud operatsiyadan keyin bo‘la olmaydi.")
            self.store.conn.execute(
                "UPDATE accounts SET opening=?,opened_on=? WHERE id=?", (amount, day, account_id)
            )
            self._validate_principals()
            self.store.audit("opening_update", account_id, {"old": old, "amount": amount, "day": day})

    def value(self, account_id, amount, day):
        a = self.account(account_id)
        valid_day(day)
        if (
            a["kind"] != "investment"
            or day < a["opened_on"]
            or type(amount) is not int
            or amount < 0
            or amount > MAX_AMOUNT
        ):
            raise RuleError("Baholash qiymati yoki sana noto‘g‘ri.")
        self.store.conn.execute(
            "INSERT INTO valuations(account_id,amount,day,created_at) VALUES (?,?,?,?)",
            (account_id, amount, day, utcnow()),
        )

    def rate(self, value, day):
        valid_day(day)
        try:
            rate = Decimal(value)
            if not rate.is_finite() or rate <= 0 or rate > Decimal("1000000000"):
                raise ValueError
        except Exception as exc:
            raise RuleError("Kurs musbat raqam bo‘lsin.") from exc
        self.store.conn.execute("INSERT INTO rates(rate,day) VALUES (?,?)", (str(rate), day))
