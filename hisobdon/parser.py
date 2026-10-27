import re
from datetime import timedelta, date
from decimal import Decimal
from .money import minor

WORDS = {
    "Ovqat": ["ovqat", "abet", "tushlik", "nonushta", "kechki ovqat", "kafe", "restoran"],
    "Oziq-ovqat": ["bozor", "mahsulot", "oziq", "supermarket"],
    "Transport": ["taksi", "taxi", "benzin", "metro", "avtobus", "yo‘l kira"],
    "Kommunal": ["elektr", "gaz", "kommunal", "svet"],
    "Aloqa": ["internet", "telefon", "aloqa"],
    "Sog‘liq": ["dori", "shifokor", "klinika", "apteka"],
    "Ta’lim": ["kurs", "kitob", "ta’lim"],
    "Ish haqi": ["oylik", "maosh", "ish haqi"],
    "Sovg‘a": ["sovg‘a", "sovg'a", "sovga"],
}
INCOME_CATS = {"Ish haqi", "Sovg‘a"}
AMOUNT = re.compile(
    r"(?<![\w])(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:[.,]\d+)?\s*(?:million|mln|ming|k\b)?", re.I
)


def parse_amount(text):
    text = text.strip().lower()
    multiplier = 1
    for suffix, factor in [("million", 1000000), ("mln", 1000000), ("ming", 1000), ("k", 1000)]:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
            multiplier = factor
            break
    return minor(str(Decimal(text.replace(" ", "").replace("\u00a0", "").replace(",", ".")) * multiplier))


def parse(text, now):
    t = text.lower().replace("’", "‘").replace("'", "‘")
    day = now.date()
    result = {"date": day.isoformat(), "note": text}
    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", t)
    relative = set(re.findall(r"\b(bugun|kecha|ertaga|indinga)\b", t))
    if len(relative) > 1 or (dates and relative):
        return {**result, "error": "Bir nechta sana ko‘rsatildi. Bitta aniq sanani yozing."}
    if relative & {"ertaga", "indinga"}:
        return {**result, "error": "Kelajak sanasiga operatsiya yozilmaydi. Haqiqiy sanani aniqlashtiring."}
    if re.search(
        r"\b(ertangi|kechagi|o‘tgan|oldingi|avvalgi|dushanba|seshanba|chorshanba|payshanba|juma|shanba|yakshanba)\b",
        t,
    ):
        return {**result, "error": "Sanani YYYY-MM-DD shaklida aniq yozing."}
    if dates:
        try:
            if len(dates) != 1:
                raise ValueError
            day = date.fromisoformat(dates[0])
            t = t.replace(dates[0], "")
        except ValueError:
            result["error"] = "Sanani YYYY-MM-DD shaklida aniqlashtiring."
    elif "kecha" in relative:
        day -= timedelta(days=1)
    result["date"] = day.isoformat()
    if day > now.date():
        result["error"] = "Kelajak sanasi mumkin emas."
    if re.search(r"\b(eur|euro|evro|rub|rubl|usdt|btc)\b|€|₽", t):
        result["error"] = "Hozir UZS va USD qo‘llanadi. Valyutani aniqlashtiring."
    usd = bool(re.search(r"\b(usd|dollar)\b|\$", t))
    uzs = bool(re.search(r"\b(uzs|so‘m|som|sum)\b", t))
    if usd and uzs:
        result["error"] = "Ikki valyuta uchun menyudan Valyuta almashtirishni tanlang."
    elif usd or uzs:
        result["currency"] = "USD" if usd else "UZS"
    nums = [m.group().strip() for m in AMOUNT.finditer(t)]
    if len(nums) == 1:
        try:
            n = parse_amount(nums[0])
            if n <= 0:
                raise ValueError
            result["amount"] = n
        except (ValueError, ArithmeticError):
            result["error"] = "Summa aniq emas. Masalan: 40000 yoki 12.50."
    elif len(nums) > 1:
        result["error"] = "Bitta xabarda bitta operatsiya yozing. Bir nechta summa topildi."
    matches = [
        cat
        for cat, words in WORDS.items()
        if any(re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", t) for w in words)
    ]
    if len(matches) == 1:
        result["category"] = matches[0]
        result["kind"] = "income" if matches[0] in INCOME_CATS else "expense"
    if re.search(r"\b(qarz|investitsiya|invest|o‘tkazma|almashtir)\w*", t):
        result.pop("kind", None)
        result.pop("category", None)
    elif re.search(r"\b(kirim|daromad|tushdi|topdim)\b", t) or text.lstrip().startswith("+"):
        result["kind"] = "income"
        if result.get("category") not in INCOME_CATS:
            result.pop("category", None)
    elif re.search(r"\b(chiqim|xarajat|sarfladim|to‘ladim)\b", t) or text.lstrip().startswith("-"):
        result["kind"] = "expense"
    return result
