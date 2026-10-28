# Hisobdon

Bitta egaga mo‘ljallangan Telegram moliya boti. UZS/USD hisoblar, kirim-chiqim, o‘tkazma, valyuta almashtirish, qarzlar, investitsiyalar, Excel va AI uchun TXT eksporti. AI API talab qilinmaydi.

## Foydalanish

1. `/start` → **Hisoblar → Hisob qo‘shish**: karta/naqd nomi, valyuta, boshlang‘ich qoldiq va sana.
2. `bugun ovqat abetga 40ming so‘m` deb yozing. Bot yetishmagan ma’lumotni so‘raydi; hisob tugmasi oddiy kirim/chiqimni saqlaydi.
3. **Yozuv** menyusida qarz, investitsiya, o‘tkazma va konvertatsiya bor. Eski qarz yoki mavjud investitsiyani hisobning boshlang‘ich qoldig‘i sifatida oching; yangi pul harakatini alohida yozing.
4. `/history` orqali yozuvni tuzating yoki bekor qiling. Telegram matnini tahrirlash moliyaviy hisobni o‘zgartirmaydi.
5. `/export` → Excel va barcha asl xabarlar hamda AI prompti bo‘lgan TXT. Ikkalasini AI chatga yuklang. Prompt TXT boshida.

Bot faqat `OWNER_ID` bilan shaxsiy chatda ishlaydi. Karta raqami, PIN yoki CVV kiritilmaydi. Bir xabar — bir operatsiya. **Yozuv yarim qolsa `/drafts`**, istalgan oynadan `/start` orqali menyuga qayting.

## Hisob qoidalari

Pul integer tiyin/sentda saqlanadi. Boshlang‘ich qoldiq, o‘tkazma, qarz asosiy qismi va investitsiyaga qo‘yish daromad/iste’mol xarajati emas. Foiz va yangi daromad alohida yoziladi. Valyutalar qo‘shilmaydi; umumiy qiymat uchun qo‘lda sanali USD/UZS kursi kiritish mumkin. Investitsiya baholashi cashflow emas.

Toshkent vaqti: har kuni **22:00**, dushanba **09:00**, oyning 1-kuni **09:00**; qarz muddati kuni **09:00**. Hisobotda haqiqiy yaratilgan vaqt ko‘rsatiladi. Kechikkan yuborishdagi hisobot shu vaqtdagi ma’lumotga asoslanadi. Kunlik shifrlangan backup **03:00** dan keyin va ilk ishga tushishda egasiga yuboriladi. Telegram’da botga avval `/start` yuborish zarur.

## Lokal tekshirish

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

`uv.lock` va hash bilan mahkamlangan requirements fayllari repoda. Kutubxonalarni yangilaganda lock va ikkala requirements faylini yangilang.

## Server

`compose.yml`, `runtime.env` (0600), `.env` ichida `RELEASE_SHA`, va `data/` (0700, UID 1000) bitta deployment katalogida turadi. Build kontekstiga maxfiy fayllar kirmaydi. Ommaviy port ochilmaydi; Telegram’ga tashqi HTTPS zarur. Bir token bilan faqat bitta nusxa ishlasin.

```sh
docker build --target runtime --build-arg APP_VERSION=COMMIT_SHA -t hisobdon:COMMIT_SHA .
docker compose up -d
docker compose exec -T bot python -m hisobdon health
docker compose logs --tail=30
```

`BOT_TOKEN`, musbat `OWNER_ID`, Fernet `BACKUP_KEY` majburiy. Token va egasi ID’sini GitHub, issue yoki logga yozmang. `data/` doimiy volume; container yangilanishi uni o‘chirmaydi.

## Backup va tiklash

Backup SQLite online snapshot API’si bilan olinadi, `integrity_check`dan o‘tkazilib, Fernet bilan shifrlanadi. Kunlik nusxa Telegram egasiga yuboriladi. Serverda oxirgi 14 kunlik va 6 oylik nusxalar saqlanadi. **Tiklash kalitini Telegram backup bilan bir joyda saqlamang.** Kalitning offline nusxasi kerak; kalitsiz zaxirani ochib bo‘lmaydi.

Kalit yaratish (qiymat ekranga chiqmaydi):

```sh
uv run python -m hisobdon new-key --destination /private/path/recovery.key
```

Tiklash: `BACKUP_KEY`ni maxfiy environment orqali bering, botni to‘xtating va yangi, mavjud bo‘lmagan faylga tiklang:

```sh
python -m hisobdon restore --file backup.db.fernet --destination /data/restored.sqlite3
```

Tiklangan DB tekshirilgach, eski bazani alohida arxivlab, asosiy nomga o‘tkazing. `.sqlite3-wal`/`.sqlite3-shm` fayllari bilan ishlashda barcha yozuvchi jarayonlar to‘xtagan bo‘lsin. Oddiy `cp` bilan ishlab turgan SQLite bazasini backup qilmang.

Deploy/migratsiyadan oldin yangi backup oling. Kod rollbacki oldingi image SHA bilan; mos kelmaydigan schema bo‘lsa backupdan tiklash talab etiladi. Tiklash backupdan keyingi yozuvlarni qaytarmaydi.

## Tuzilma

- `db.py`, `ledger.py`, `money.py`: doimiy saqlash, atomik pul harakatlari va tekshiruvlar.
- `parser.py`, `conversation.py`: matn va restartdan keyin davom etuvchi tugmali dialog.
- `reports.py`, `scheduler.py`, `backup.py`: eksport, jadval va tiklash.
- `runtime.py`: owner tekshiruvi, durable inbox/outbox, aiogram polling.

Tasdiqlangan umumiy dizayn va bajarish rejasi `docs/superpowers/` ichida. Shaxsiy boshlang‘ich ma’lumotlar hujjatlarda bo‘lmaydi.

## Qarzning bir qismini yoki hammasini qaytarish

`/debts` orqali qarzni oching. **Qaytarilgan pulni kiritish** (siz bergan qarz) yoki **Qarzni qaytarish** (siz olgan qarz) tugmasini bosing. **To‘liq** qolgan summani oladi; **Qisman qaytarish** summani kiritishni so‘raydi. Keyin pul tushgan yoki pul ketgan karta/naqd hisobni tanlab saqlang.

Kirim kategoriya oynasida **Qarz qaytdi**, chiqim oynasida **Qarzni qaytardim** yo‘li ham bor. Bu oddiy daromad/xarajat emas: pul hisobini va tegishli qarz qoldig‘ini birga yangilaydi. Qoldiq 0 bo‘lganda qarz **Yopilgan qarzlar** ro‘yxatida qoladi; tarix o‘chirilmaydi. Qaytarishni bekor qilsangiz, qarz qayta ochiladi.

## Qora kun uchun zaxira

**Hisoblar → Hisob qo‘shish → Zaxira (uydagi naqd)** orqali UZS va USD uchun alohida hisob oching. Aniq boshlang‘ich qoldiqni o‘zingiz kiriting. Mavjud karta/naqd hisob oynasida **Zaxira deb belgilash** va **Kundalik hisob qilish** bor.

Zaxira sof moliyaviy holatga kiradi, **Sarflash mumkin** qoldig‘iga kirmaydi. Zaruratda **Yozuv → O‘z hisoblarim orasida** orqali oddiy hisobga o‘tkazing, keyin xarajat yozing. O‘tkazishning o‘zi xarajat emas.

## Bitta xarajatni bir nechta hisobdan to‘lash

Xarajat summasi/kategoriyasidan keyin **Bo‘lib to‘lash — naqd + karta** ni tanlang. Har bir hisobdan to‘langan summani kiriting; oxirgisida **Qolgan** tugmasi bor. Masalan, 60 000 UZS xarajat = 17 000 naqd + 43 000 karta. Jami xarajat bir marta sanaladi. Qismlar bitta valyutada bo‘lishi kerak; zaxira bevosita ishlatilmaydi.

## To‘liq AI paketi

Har bir qo‘lda/oylik eksport bir izchil snapshotdan **Excel + promptli TXT + canonical JSON + manifest.json** tayyorlaydi. Tanlangan davr xulosasi alohida, moliyaviy arxiv esa barcha davrlarni qamraydi: hisoblar va boshlang‘ich qoldiqlar, barcha operatsiya versiyalari, signed pul harakatlari, baholash/kurs tarixi, kategoriyalar/kalit so‘zlar, asl xabarlar, qoralamalar va audit.

Joriy holat bilan davr oxiri ajratilgan. `manifest.json` satrlar soni va fayl hashlarini ko‘rsatadi; barcha raqamlangan qismlarni birga o‘qing. TXT va JSON bir xil canonical yozuvlarni saqlaydi; ularni Excel bilan takror qo‘shmang. Excel katagi limitiga sig‘magan uzun matnning to‘liq qiymati TXT/JSON’da saqlanadi.

Texnik inbox/outbox, scheduler holati, server maxfiy sozlamalari va Telegram marshrutlash ID’lari AI paketiga kirmaydi. Asl foydalanuvchi matnlari o‘z holicha kiradi. To‘liq moliyaviy arxiv tiklash uchun SQLite backup o‘rnini bosmaydi.

Reserve migration: DB schema v2 adds `is_reserve`, preserves existing balances, and refuses unknown newer versions. Before upgrading, take an encrypted backup. After reserve accounts exist, do not roll back to pre-reserve code that ignores their purpose; restore a reviewed pre-upgrade backup only with awareness of later-record loss, or fix forward.

## Xarajat sanasini tanlash

Sana yozilmagan xarajatda bot **Bugun / Kecha / Boshqa sana** deb so‘raydi. Matnda aniq sana yoki «bugun/kecha» bo‘lsa, o‘sha sana saqlanadi. Hisob/kategoriya tanlash va tasdiqlash oynasidagi **Sanani o‘zgartirish** orqali qoralamani qayta yozmasdan sanani almashtiring. Boshqa sana `YYYY-MM-DD` yoki `DD.MM.YYYY` shaklida kiritiladi; kelajak sanasi qabul qilinmaydi.

## To‘liq nom va qoldiqlar

Hisob/qarz/investitsiya tanlovlari bitta ustunda ko‘rsatiladi. To‘liq nom va qoldiq xabar matnida ham raqamlangan ro‘yxat sifatida beriladi; tugma raqami shu ro‘yxatga mos. Telegram ekraniga juda uzun tugma sig‘masa, to‘liq qiymatni yuqoridagi xabardan o‘qing. Uzoq kategoriya nomlari ham xabar matnida ko‘rsatiladi.
