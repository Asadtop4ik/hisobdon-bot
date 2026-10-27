# Hisobdon shaxsiy moliya boti loyihasi

Sana: 2026-10-27. Holat: kelishilgan talablar asosidagi loyiha dizayni, yakuniy ko‘rib chiqish uchun.

Hisobdon foydalanuvchining Telegram orqali kiritgan moliyaviy yozuvlarini saqlaydi, karta va naqd pullar qoldig‘ini, qarzlarni va investitsiyalarni hisoblaydi. Hisobotlar dastur orqali hisoblanadi. Oylik ma’lumot va tayyor promptni foydalanuvchi o‘zi tanlagan AI chatiga yuklab, tahlil qildiradi. Botning ishlashi AI API’ga bog‘liq emas.

## Kelishilgan qarorlar

- Bot bitta foydalanuvchining shaxsiy moliyasi uchun.
- Karta va naqd hisoblar oldindan kiritiladi. Operatsiyada kerakli hisob tugmadan tanlanadi.
- Asosiy kiritish usuli erkin matn: «bugun ovqat abetga 40ming so‘m». Bot aniqlay olmagan tur va kategoriyani tugmalar orqali so‘raydi.
- Valyutalar: UZS va USD.
- Kompaniya nomi bilan investitsiya hisoblari ochiladi; boshlang‘ich qiymatlar faqat foydalanuvchi bazasida saqlanadi.
- Olingan va berilgan qarzlar hisobga olinadi.
- Toshkent vaqtida kunlik xabar 22:00, haftalik xabar dushanba 09:00, oylik hisobot oyning 1-kuni 09:00, muddati belgilangan qarz eslatmasi muddat kuni 09:00.
- Tanlangan stack: Python, aiogram 3, SQLite, openpyxl, Docker Compose. Deploy maqsadi: `ssh netcup` orqali kiriladigan server.

Quyidagi nomlar va foydalanuvchi alohida belgilamagan tafsilotlar muallif taklifidir: bot nomi **Hisobdon**, private GitHub repo **hisobdon-bot**. Telegram username BotFather’da mavjudligiga qarab tanlanadi; hozir bandligi tekshirilmagan.

## Natija va ishga tushirish mezoni

Birinchi foydalaniladigan relizda foydalanuvchi hisoblarini boshlang‘ich qoldiqlari bilan ochishi, haqiqiy xarajatni matn va tugmalar bilan saqlashi, xatoni tuzatishi va qoldiqni ko‘rishi kerak. To‘liq birinchi relizga qarzlar, investitsiyalar, ikki valyuta, bildirishnomalar, Excel va TXT eksportlari ham kiradi.

«Bugundan yozishni boshlash» maqsadi uchun avval asosiy kiritish va qoldiqni ishlaydigan holatga chiqarish mumkin; qolgan imkoniyatlar tekshirilmaguncha to‘liq loyiha tayyor deb hisoblanmaydi. Yetkazish vaqti server, bot tokeni va boshlang‘ich ma’lumotlar tayyorligiga bog‘liq.

## Ko‘rib chiqilgan yondashuvlar

**A — bitta bot xizmati va SQLite. Tanlangan.** Baza bot bilan bir serverning doimiy diskida turadi. Bitta shaxsiy foydalanuvchi uchun xizmatlarni boshqarish sodda. Bir vaqtning o‘zida bitta bot nusxasi ishlaydi. Bir nechta server yoki ko‘p yozuvchi xizmat zarur bo‘lsa, PostgreSQL’ga ko‘chirish alohida ish bo‘ladi.

**B — bot va alohida PostgreSQL xizmati. Tanlanmagan.** Parallel xizmatlar ko‘payganda foydali, ammo hozir alohida baza xizmati va uning ekspluatatsiyasi zarur bo‘lmaydi.

## Hisoblar va dastlabki sozlash

Har bir hisobda nom, turi (karta yoki naqd), valyuta, boshlang‘ich qoldiq va hisob boshlanish vaqti bo‘ladi. Misollar: «Asosiy Humo / UZS», «Dollar karta / USD», «Naqd so‘m / UZS», «Naqd dollar / USD».

Karta raqami, PIN va CVV talab qilinmaydi. Bir xil valyutadagi bir nechta hisob mumkin. Operatsiyasi bor hisob o‘chirilmaydi, arxivlanadi; tarix va hisobotlarda qoladi.

Boshlang‘ich qoldiq kirim emas. Hisob boshlanishidan oldingi davr bo‘yicha to‘liq tarix borligi da’vo qilinmaydi. Dastlab shu vaqtdan oldingi operatsiyalarni kiritish bloklanadi va foydalanuvchiga boshlang‘ich sanani/qoldiqni qayta ko‘rib chiqish taklif qilinadi. Boshlang‘ich qiymatni tuzatish tarixda saqlanadi.

Taxminiy investitsiya qiymati kod yoki DB’ga aniq raqam sifatida kiritilmaydi. Sozlashda foydalanuvchi joriy qoldiqni, uning sanasini va ma’lum bo‘lsa asosiy mablag‘/daromad tarkibini kiritadi. Tarkibi noma’lum bo‘lsa «boshlang‘ich qoldiq, tarkibi noma’lum» deb saqlanadi; oldingi davr foydasi hisoblab chiqarilmaydi.

## Matndan tranzaksiya kiritish

1. Ruxsat etilgan foydalanuvchining asl xabari va Telegram identifikatorlari DB’da saqlanadi.
2. Qoidalar summa, valyuta, sana, operatsiya turi, kategoriya va izohni ajratishga urinadi.
3. «40ming», «40 ming», «40 000», «40k» kabi aniq shakllar normallashtiriladi. «Ovqat», «abet», «tushlik» kabi lug‘at so‘zlari kategoriyaga moslanadi.
4. Yetishmagan yoki qarama-qarshi ma’lumotlar bitta-bittadan tugma yoki matn bilan so‘raladi. Tasodifiy taxmin asosida pul harakati saqlanmaydi.
5. Karta yoki naqd hisob tanlanadigan xabarda ajratilgan summa, tur, kategoriya va sana ko‘rinadi. «Tuzatish» va «Bekor qilish» mavjud.
6. Oddiy kirim/chiqimda barcha maydonlar aniq bo‘lsa, hisobni tanlash yozuvni saqlaydi. Saqlangan javobda yozuv ID’si, mazmuni, hisobning yangilangan qoldig‘i va tuzatish/bekor qilish tugmalari chiqadi.

Valyuta matnda bo‘lmasa, tanlangan hisob valyutasi olinadi va yakuniy javobda ko‘rsatiladi. Matnda valyuta berilgan bo‘lsa, mos hisoblar ko‘rsatiladi. Boshqa valyutadagi hisobdan sarf faqat ikkala summa aniq bo‘lgan alohida konvertatsiya orqali yoziladi.

Sana bo‘lmasa xabar qabul qilingan Toshkent sanasi olinadi. «Bugun» va «kecha» xabar vaqti asosida aniqlanadi. Noaniq sana yoki bir xabarda bir nechta operatsiya bo‘lsa, foydalanuvchidan aniqlashtirish yoki alohida xabarlarga ajratish so‘raladi. V1 bitta xabarni bitta operatsiyaga aylantiradi.

Summalar musbat kiritiladi, yo‘nalishni operatsiya turi belgilaydi. Oddiy sarf mavjud qoldiqdan oshsa, bot qoldiqni tekshirishni so‘raydi; foydalanuvchi alohida tasdiqlasa manfiy qoldiq mumkin. Bu yozilmagan kirimni yashirin yaratishga olib kelmaydi.

Har bir xabarning alohida qoralamasi bo‘ladi. Yangi xabar avvalgi qoralamani almashtirmaydi. Qoralamalar qayta ishga tushganda qoladi va ularning tugmalari aynan o‘z yozuviga bog‘lanadi. Qoralama qoldiqqa ta’sir qilmaydi.

Kategoriya lug‘ati boshlang‘ich to‘plam va foydalanuvchi kategoriyalaridan iborat. Dastlabki taklif: ovqat, oziq-ovqat, transport, uy, kommunal, aloqa/internet, sog‘liq, xarid, ta’lim, ko‘ngilochar, komissiya, boshqa; kirim uchun ish haqi, xizmat/biznes, sovg‘a va boshqa. Yangi kategoriya qo‘shish mumkin. Tasodifiy bitta tuzatish barcha kelajak xabarlarini yashirin qayta tasniflamaydi; yangi kalit so‘z bog‘lanishi alohida tasdiqlanadi.

## Operatsiyalar va qoldiq qoidalari

| Operatsiya | Pul hisoblariga ta’sir | Hisobotdagi ma’nosi |
|---|---|---|
| Kirim | Tanlangan hisob ko‘payadi | Daromad |
| Chiqim | Tanlangan hisob kamayadi | Xarajat |
| O‘z hisoblari orasida o‘tkazma | Bir hisob kamayadi, boshqasi ko‘payadi | Daromad/xarajat emas |
| Valyuta almashtirish | Berilgan va olingan summalar o‘z valyutalarida yoziladi | Daromad/xarajat emas; komissiya alohida |
| Qarz olish | Pul va qarz majburiyati ko‘payadi | Daromad emas |
| Qarz berish | Pul kamayadi, olinadigan qarz ko‘payadi | Iste’mol xarajati emas |
| Asosiy qarzni qaytarish | Pul va qarz qoldig‘i tegishli yo‘nalishda o‘zgaradi | Daromad/xarajat emas |
| Investitsiyaga kiritish | Pul kamayadi, investitsiya qoldig‘i ko‘payadi | Iste’mol xarajati emas |
| Investitsiya asosiy mablag‘ini olish | Investitsiya kamayadi, pul ko‘payadi | Yangi daromad emas |
| Foiz yoki investitsiya daromadi | Pulga yoki investitsiya hisobiga qo‘shiladi | Alohida daromad |

Barcha pul qiymatlari integer kichik birliklarda (UZS uchun tiyin, USD uchun sent; ikkisi ham 100 birlik) saqlanadi. Hisoblashda binary float ishlatilmaydi. Matnni o‘girish va ko‘rsatishda Decimal va aniq yaxlitlash qoidasi qo‘llanadi. Ikki kasrdan ortiq pul qiymati jim yaxlitlanmaydi, aniqlashtiriladi.

Bir operatsiyaning barcha pul harakatlari, qarz/investitsiya o‘zgarishlari va audit yozuvi bitta DB tranzaksiyasida saqlanadi. Operatsiya qisman yozilib qolmaydi. Qoldiq boshlang‘ich qoldiq va amaldagi harakatlardan tiklanadigan bo‘ladi.

Saqlangan yozuvni tuzatish yangi versiya va oldingi ta’sirni qaytaruvchi yozuv orqali bajariladi. Bekor qilish tarixni o‘chirmaydi. Telegram’dagi xabarni tahrirlash yoki o‘chirish moliyaviy hisobni avtomatik o‘zgartirmaydi; botning «Tuzatish» amali ishlatiladi. Bir xil Telegram update yoki tugma qayta kelishi pulni ikki marta yozmaydi.

## UZS va USD

Har bir valyutaning qoldiq va jami alohida ko‘rsatiladi. USD va UZS bevosita qo‘shilmaydi.

Konvertatsiyada manba hisob, chiqayotgan summa, qabul qiluvchi hisob, kelayotgan summa, sana va ixtiyoriy komissiya kiritiladi. Haqiqiy kurs shu ikki summadan chiqariladi. Manba va qabul hisobi turlicha valyutada bo‘lishi kerak. Bir valyutadagi o‘tkazmada asosiy summa teng, komissiya alohida xarajat bo‘ladi.

Asosiy hisobotlar kurssiz ishlaydi. Foydalanuvchi umumiy boylikni UZS’da ko‘rmoqchi bo‘lsa, qo‘lda kiritilgan USD/UZS kursi va sana ishlatiladi. Bu faqat ko‘rsatish uchun baholash; tarixiy operatsiyalar o‘zgarmaydi. Kurs yo‘q bo‘lsa, birlashtirilgan jami ko‘rsatilmaydi. Avtomatik valyuta kursi xizmati V1 uchun zarur emas.

## Qarzlar

Qarz kartochkasi: odam nomi, yo‘nalish (men olgan/men bergan), valyuta, boshlanish sanasi, asl summa, qolgan asosiy qarz, ixtiyoriy muddat va izoh. Bir odam bilan bir nechta qarz bo‘lsa, qaytarishda aynan qaysi qarz tanlanadi.

Eski qarzni tizimga kiritish «boshlang‘ich qarz» amalidir: uning qolgan qismi yoziladi, mavjud karta/naqd qoldig‘i qaytadan o‘zgartirilmaydi. Yangi qarzda tegishli pul hisobi ham o‘zgaradi. Bu ikki amal interfeysda farqlanadi.

Qisman qaytarish mumkin; qoldiqdan ortiq asosiy qarz qaytarilishi bloklanadi. Foiz to‘lovi/olimi alohida xarajat/daromad. Avtomatik foiz hisoblash yo‘q. V1’da qarz o‘z valyutasida yuradi; boshqa valyutada to‘lashdan oldin alohida konvertatsiya yoziladi.

Muddat kuni 09:00 da qolgan qarz haqida eslatiladi. Muddat kiritilmasa eslatma yo‘q. Qarz yopilsa, keyingi eslatma yuborilmaydi. Bot faqat egasiga eslatadi, qarzdorga xabar yubormaydi.

## Investitsiyalar

Har kompaniya uchun nom, valyuta, boshlang‘ich qoldiq/sana, kiritishlar, qaytarishlar, tan olingan daromad va izohlar saqlanadi. Tizim kompaniyaga xos API yoki foiz stavkasiga bog‘lanmaydi.

Daromad pul hisobiga tushishi yoki investitsiya ichida qolishi mumkin. Ichkarida qolgan daromad bir marta daromad sifatida qayd etiladi. Keyinchalik uni kartaga ko‘chirish daromadni ikkinchi marta oshirmaydi. Olingan umumiy summaning bir qismi asosiy mablag‘, bir qismi yangi foyda bo‘lsa, foydalanuvchi ularni ajratadi; noaniq tarkib taxmin qilinmaydi.

Kompaniya bildirgan joriy qiymat sanali baholash sifatida yozilishi mumkin. Baholash pul harakati yoki avtomatik daromad emas. Hisobotda hisoblangan qoldiq va oxirgi baholash alohida ko‘rsatiladi; umumiy boylikda shu hisob uchun faqat bittasi ishlatiladi, qaysi biri olingani yoziladi. Baholashdan keyin harakat bo‘lsa, eski baholash «eskirgan» deb belgilanadi va jami uchun hisoblangan qoldiq ishlatiladi.

Ilgari qo‘yilgan mablag‘lar va sanalar to‘liq bo‘lmasa, yillik daromadlilik yoki tarixiy foyda taxmin qilinmaydi.

## Hisobotlar va bildirishnomalar

| Hisobot | Toshkent vaqti | Davr |
|---|---|---|
| Kunlik | Har kuni 22:00 | Bugun 00:00 dan 22:00 gacha kiritilgan holat |
| Haftalik | Dushanba 09:00 | Oldingi dushanba 00:00 dan joriy dushanba 00:00 gacha |
| Oylik | Oyning 1-kuni 09:00 | Oldingi kalendar oy |
| Qarz eslatmasi | Muddat kuni 09:00 | Qaytarilmagan qoldiq |

Davrlar Asia/Tashkent bo‘yicha, oxirgi chegara kirmaydigan shaklda hisoblanadi. Kunlik xabar «22:00 holatiga» deb belgilanadi. Kechroq kiritilgan operatsiya tegishli sana bo‘yicha haftalik/oylik hisobot va qayta eksportga kiradi. Asl xabar vaqti, operatsiya sanasi va DB’ga yozilgan vaqt alohida saqlanadi.

Kunlik/haftalik xabarda UZS va USD bo‘yicha daromad, xarajat va asosiy kategoriyalar, shu vaqtdagi pul qoldiqlari hamda tugallanmagan qoralamalar soni bo‘ladi. O‘tkazma, qarz asosiy qismi va investitsiya kiritishlari oddiy kirim-chiqim jamiga qo‘shilmaydi, alohida bo‘limda ko‘rinadi. Operatsiyasiz kunda «bugun yozuv yo‘q» deyiladi; bu real xarajat bo‘lmaganining isboti deb talqin qilinmaydi.

Hisobotlarda hisob boshlangan sana, eksport yaratilgan vaqt va qamrov cheklovi bo‘ladi. Masalan, 27-oktabrda boshlangan hisob butun oktabr tarixi sifatida ko‘rsatilmaydi. Sana bo‘yicha orqaga yozilgan/tuzatilgan ma’lumot yangi eksportda aks etadi; avval yuborilgan fayl o‘zgarmaydi.

Vazifalar DB’da davr, turi, holati va urinishlari bilan saqlanadi. Bot qayta yoqilganda muddati o‘tgan oylik/haftalik ishlar bajariladi; yig‘ilib qolgan kunlik xabarlardan faqat eng so‘nggisi yuboriladi. Vazifalar tizim faollashgan kundan boshlab yaratiladi. O‘tib ketgan, hali ochiq qarz uchun bir marta kechikkan eslatma yuboriladi.

Telegram’ga yuborishda xatolar qayta uriniladi. Oddiy qayta urinishlarda DB’dagi noyob davr kaliti takror vazifa yaratmaydi. Telegram yuborishni qabul qilganidan keyin tarmoq uzilsa, xabar yetkazilganini har doim aniqlab bo‘lmaydi; mutlaq «faqat bir marta yetkazish» kafolati berilmaydi. Xabar/faylda davr va hisobot ID’si ko‘rinadi. DB hisoblari baribir takrorlanmaydi.

## Excel va AI uchun eksport

Oylik paket Telegram’da alohida fayllar sifatida yuboriladi:

1. `hisobdon-YYYY-MM.xlsx` — tartibli jadval va hisoblangan natijalar.
2. `hisobdon-YYYY-MM-context.txt` — AI tahlil prompti, valyuta/raqam/sana qoidalari, davr va qamrov, qisqa jamlar, tanlangan davrning barcha asl foydalanuvchi xabarlari, ularning holati va yozuv ID’lari.

Excel varaqlari: **Yo‘riqnoma**, **Xulosa**, **Tranzaksiyalar**, **Hisoblar**, **Kategoriyalar**, **Qarzlar**, **Qarz harakatlari**, **Investitsiyalar**, **Investitsiya harakatlari**, **Valyuta**, **Asl xabarlar**, **Tuzatishlar**. Katta davrda Telegram yoki AI chat limitiga sig‘masa, fayllar qismlarga bo‘linadi va manifest qo‘shiladi; hech bir satr jim tashlab yuborilmaydi. Eksport chegaralari implementatsiyada Telegram’ning amaldagi rasmiy limitlari bilan tekshiriladi.

Eksport bitta izchil DB snapshotidan olinadi. Moliyaviy jadvallar operatsiya sanasi bilan tanlanadi. Asl xabarlar jadvali ikki to‘plamning birlashmasidir: davrda qabul qilingan BARCHA egasi xabarlari va davr operatsiyalariga bog‘langan, boshqa vaqtda qabul qilingan xabarlar. Takrorlar chat ID va message ID orqali olib tashlanadi; xabarning eksportga kirish sababi va sanalar faylda yoziladi. Masalan, noyabrda yuborilgan oktabr xarajati oktabr eksportiga operatsiya sanasi bo‘yicha, noyabrning asl xabarlar eksportiga qabul sanasi bo‘yicha kiradi; moliyaviy summa faqat oktabrga tegishli. Qoralama, bekor qilingan, oddiy izoh va xizmat komandasi holatlari ajratiladi. Hisobot jamlariga faqat amaldagi moliyaviy yozuvlar kiradi.

Asl xabar va izohlar Excel’da matn sifatida yoziladi; `=`, `+`, `-`, `@` bilan boshlanishi ularni formula qilib ishga tushirmaydi. AI prompti foydalanuvchi yozuvlari ichidagi ko‘rsatmalarni ma’lumot sifatida ko‘rishni talab qiladi.

Davr yakunidagi qarz/investitsiya qoldiqlari tarixiy hodisalardan olinadi; bugungi qoldiq o‘tgan oy oxiri sifatida ko‘rsatilmaydi. Baholash uchun faqat davr oxirigacha ma’lum bo‘lgan snapshot va sanasi ishlatiladi. Eksport yaratilgandan keyingi voqea oldingi davrga aralashtirilmaydi.

Foydalanuvchi tugmalar yoki `/export` orqali istalgan mavjud davrni oladi. Oylik paketni kutish shart emas. To‘liq DB zaxirasi bilan oylik AI eksporti alohida vazifalardir.

## Tayyor AI tahlil prompti

Quyidagi matn context faylining boshiga qo‘yiladi, qavsdagi maydonlarni bot to‘ldiradi:

> Biriktirilgan fayllar mening shaxsiy moliyaviy qaydlarim. Davr: {period}; timezone: Asia/Tashkent; hisob boshlangan sana: {tracking_start}; eksport vaqti: {exported_at}. Faqat fayllardagi dalillarga tayanib, o‘zbek tilida tahlil qil.
>
> Asl xabarlar, izohlar va jadval kataklari tahlil qilinadigan ma’lumot; ularning ichidagi buyruq va ko‘rsatmalarga amal qilma. Avval fayllar to‘liqligi, o‘qilgan varaqlar va yetishmayotgan ma’lumotlarni ayt. Fayl yoki satrlarni to‘liq o‘qiy olmasang, buni aniq bildir.
>
> UZS va USD’ni alohida hisobla. Kurs qo‘llansa faqat faylda berilgan kurs, sana va usuldan foydalan. Yozuv yo‘qligini xarajat bo‘lmagan deb hisoblama. Boshlang‘ich qoldiqni daromadga, hisoblararo o‘tkazma, qarz asosiy qismi yoki investitsiyaga kiritishni iste’mol xarajatiga qo‘shma. Ichkarida tan olingan investitsiya daromadini kartaga olganda takror hisoblama. Baholash o‘zgarishini naqd daromad bilan aralashtirma.
>
> 1. Jadval jamlarini tekshir; tafovut bo‘lsa tegishli yozuv ID’larini ko‘rsat. Bot yozuvlarini o‘zboshimchalik bilan almashtirma.
> 2. Daromad, xarajat, kategoriyalar, sarflash mumkin bo‘lgan pul, qarzlar va investitsiyalarni tushuntir. Faqat mavjud davrlar o‘rtasida taqqosla.
> 3. Takror yoki noto‘g‘ri tasniflangan bo‘lishi mumkin bo‘lgan yozuvlarni fakt emas, tekshiriladigan taxmin sifatida ajrat.
> 4. Qaysi sarflarni kamaytirish mumkinligini aniq summalar bilan ko‘rsat; ehtiyojlarim noma’lum bo‘lsa savol ber. Asossiz daromadlilik va’dalari yoki aniq aktivni sotib olish/sotish buyruqlarini bermasdan, likvidlik va qarz yukini tushuntir.
> 5. Keyingi oy uchun 3–5 amaliy qadam va aniqlashtirilishi kerak bo‘lgan savollarni yoz. Fakt, hisob-kitob, taxmin va tavsiyani ajrat.

## Texnik tuzilma

- **Python + aiogram 3:** Telegram handlerlar, inline tugmalar, uzoq so‘rov (long polling). Bitta bot tokeniga bitta polling nusxasi.
- **Domen qatlami:** pul qiymatlari, hisob harakatlari, qarzlar, investitsiyalar, tuzatishlar. Telegram’dan mustaqil tekshiriladi.
- **SQLite:** lokal doimiy volume, foreign key’lar, migratsiyalar, cheklangan yozuv tranzaksiyalari. DB fayli network filesystem’da turmaydi.
- **Matn parseri:** deterministik qoidalar va kategoriya lug‘ati. AI API, kompaniya API’si yoki bankka ulanish shart emas.
- **Hisobot qatlami:** snapshotdan hisoblash, openpyxl bilan XLSX va UTF-8 TXT yaratish.
- **Vaqt vazifalari:** shu xizmat ichidagi worker, DB’da doimiy job holati va qayta urinish. Alohida Redis/Celery zarur emas.
- **Docker Compose:** bitta bot xizmati, doimiy data volume, restart siyosati va healthcheck.

Python va kutubxonalarning o‘zaro mos versiyalari implementatsiya boshlanishida tanlanib lockfile’da mahkamlanadi. ORM yoki sqlite adapterining aniq tanlovi, modul nomlari va scheduler kutubxonasi builder qarori; yuqoridagi saqlanish va hisoblash shartlari o‘zgarmaydi.

Mantiqiy obyektlar: owner/settings, accounts, categories/aliases, inbound_messages, drafts, operations/revisions, account_movements, debts/debt_events, investments/investment_events, valuations, exchange_rates, scheduled_jobs/deliveries, exports va audit. Bu jadval nomlarini majburlovchi sxema emas, yo‘qolmasligi kerak bo‘lgan ma’lumotlar modeli.

## Netcup deploy va zaxira

Deploy oldidan `netcup` SSH aliasi, serverning OS/arxitekturasi, Docker imkoniyati, bo‘sh disk va mavjud xizmatlar o‘qish rejimida tekshiriladi. Hozir serverga ulanilmagan, uning sig‘imi va amaldagi konfiguratsiyasi tasdiqlanmagan.

Long polling uchun serverdan Telegram’ga tashqi HTTPS ulanish yetarli; alohida domen yoki ommaviy webhook talab qilinmaydi. Mavjud servislar o‘zgartirilmaydi. Taklif etilgan loyiha katalogi `/opt/hisobdon`, ammo amaldagi server tartibi ustun.

Deploy sozlamalari: bot tokeni, owner Telegram ID, timezone, DB/data path va backup sozlamalari. Token repo, prompt, log va hisobotga tushmaydi; maxfiy kiritish vositasi orqali olinadi. Moliyaviy matnlar odatiy loglarga yozilmaydi. Bot faqat ruxsat etilgan ID bilan shaxsiy chatda ishlaydi.

Image commit SHA bilan belgilanadi. Migratsiyadan oldin izchil backup olinadi. App rollback oldingi image bilan, mos bo‘lmagan schema rollback esa tekshirilgan backupdan tiklash bilan bajariladi; migratsiyadan keyingi yangi yozuvlarni yo‘qotish xavfi yashirilmaydi.

Kunlik SQLite online backup, butunlik tekshiruvi va davriy restore tekshiruvi bo‘ladi. Boshlang‘ich retention taklifi: 14 kunlik va 6 oylik nusxa. Backup shifrlanadi; shifrlash kaliti backup bilan bir joyda saqlanmaydi. Serverdan tashqaridagi nusxa uchun foydalanuvchining mavjud saqlash joyi deploy oldidan aniqlanadi; yangi pullik xizmat avtomatik xarid qilinmaydi. Faqat bir serverdagi nusxa server yo‘qolishidan himoya deb hisoblanmaydi. Off-server nusxa va kalit bilan tiklash tekshirilmaguncha backup talabi tugallangan emas.

Healthcheck xizmatning ichki ishlashi, DB’ga kirish va worker heartbeat’ini tekshiradi. Yetkazilmagan hisobotlar va oxirgi muvaffaqiyatli backup holati egasi uchun diagnostikada ko‘rinadi. Server butunlay ishlamay qolsa, shu botning o‘zi bu haqda xabar bera olmasligi hisobga olinadi.

## Yetkazish bosqichlari

1. **Loyiha tayyorlash:** private repo, README/AGENTS, kelishilgan dizayn, GitHub Issues va domen hujjatlari; build/test vositalari. `ask-matt` engineering oqimiga kirishda setup skill’ining repo konfiguratsiyasi bajariladi.
2. **Ishlaydigan hisob:** owner cheklovi, UZS/USD hisoblar, boshlang‘ich qoldiq, asl xabar/qoralama, parser, kategoriya, tugmalar, oddiy kirim/chiqim, tuzatish va qoldiq. Netcup’da ilk haqiqiy yozuvni tekshirish.
3. **To‘liq moliyaviy harakatlar:** o‘tkazma, konvertatsiya, komissiya, eski/yangi qarzlar, qisman qaytarish, investitsiya va daromad, baholash.
4. **Hisobotlar:** kun/hafta/oy, jadval worker’i, Excel/TXT va AI prompti, qo‘lda eksport.
5. **Ishonchli foydalanish:** takror update/restart holatlari, backup/restore, deploy healthcheck, yakuniy qabul tekshiruvlari.

Bu bosqichlar hajm va bog‘liqliklarni ko‘rsatadi. Dizayn tasdiqlangach alohida implementatsiya rejasi va bajariladigan vazifalar yoziladi.

## Qabul tekshiruvlari

- «Bugun ovqat abetga 40ming so‘m» misoli 40 000 UZS bo‘ladi; hisob tanlanganda faqat bir marta saqlanadi.
- Noaniq summa/tur/kategoriya aniqlashtirilmaguncha qoldiq o‘zgarmaydi; restartdan keyin qoralama davom ettiriladi.
- Boshlang‘ich qoldiq va eski qarzni kiritish bugungi daromad yoki qo‘shimcha pul harakati yaratmaydi.
- UZS va USD, o‘tkazmalar, FX va komissiya natijalari qo‘lda hisoblangan misollar bilan mos keladi.
- Qarzning qisman qaytarilishi va investitsiya daromadini ichkarida qoldirib keyin olish ikki marta hisoblanmaydi.
- Tuzatish/bekor qilish qoldiqni to‘g‘ri tiklaydi, original xabar/audit saqlanadi.
- Oy/hafta chegaralari, 22:00 dan keyingi yozuv, orqaga sana bilan kiritish va qisman birinchi oy to‘g‘ri ko‘rinadi.
- Oylik eksport jamlari shu snapshotdagi hisobotga teng, tarixiy qoldiqlar bugungi qoldiq bilan almashtirilmagan, barcha kerakli xabarlar va holatlar bor. Keyingi oy yuborilgan oldingi oy xarajati ikkala davrning asl xabarlar qamrovida tekshiriladi, pul summasi ikki oyda takrorlanmaydi.
- Telegram retry/timeout va restart pul yozuvini takrorlamaydi; hisobot yetkazish noaniqligi operatsiya hisobiga ta’sir qilmaydi.
- Begona Telegram ID hech qanday moliyaviy ma’lumotni o‘qiy/yoza olmaydi.
- Backupdan alohida vaqtinchalik DB’ga tiklangan yozuvlar va qoldiqlar asl snapshotga teng.
- Yakuniy deployda aniq image versiyasi, migratsiya holati va xizmat sog‘lomligi tasdiqlanadi.

## Birinchi reliz chegarasi

Birinchi reliz matn va tugmalar orqali qo‘lda hisob yuritishga mo‘ljallangan. Ovozdan matn, chek OCR’i, bank integratsiyasi, avtomatik kompaniya ma’lumotlari, bozor kotirovkalari, veb kabinet va ko‘p foydalanuvchilik alohida keyingi ishlar. PDF/Word birinchi reliz uchun talab qilinmaydi: asosiy eksport Excel va TXT. Budjet limitlari va takroriy to‘lovlarni avtomatik yaratish ham alohida kengaytma.

## Ishga tushirish oldidan olinadigan ma’lumotlar

Bot tokeni maxfiy kiritish orqali; owner Telegram ID; private GitHub repo uchun egasi; mavjud Netcup ulanishi; backup manzili va kalitni saqlash usuli. Karta/naqd nomlari va aniq boshlang‘ich qoldiqlar, investitsiyaning aniq joriy qoldig‘i va eski qarzlar botning dastlabki sozlash oynasida kiritiladi. Ularni hozir chatda yig‘ish shart emas.

## Texnik manbalar

- aiogram long polling: https://docs.aiogram.dev/en/latest/dispatcher/long_polling.html
- SQLite’dan mos foydalanish: https://www.sqlite.org/whentouse.html
- SQLite online backup: https://www.sqlite.org/backup.html
- openpyxl: https://openpyxl.readthedocs.io/en/stable/
