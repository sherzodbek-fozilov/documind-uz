"""Contract templates for SYNTHETIC documents.

All parties, people, addresses and amounts are filled in from invented values by
``make_synthetic_docs.py``. uz-Cyrl documents are produced by transliterating the uz-Latn
templates (see ``documind.translit``), which is recorded in docs/data.md.

Placeholders: {city} {date} {num} {party_a} {party_b} {person_a} {person_b} {amount}
{term} {penalty} {max_penalty} {pay_days} {notice_days} {address} {area} {deposit}
{goods} {quantity} {delivery_days} {warranty} {service} {report_day} {hours}
"""

MARK = {
    "uz": "SINTETIK NAMUNA. Barcha nomlar, shaxslar va raqamlar oʻylab topilgan.",
    "ru": "СИНТЕТИЧЕСКИЙ ОБРАЗЕЦ. Все названия, лица и суммы вымышлены.",
}

# Each section: (uz heading, ru heading, [uz clauses], [ru clauses])
COMMON_TAIL = [
    ("Taraflarning javobgarligi", "Ответственность сторон",
     ["Toʻlov muddati kechiktirilgan har bir kun uchun {party_b} kechiktirilgan summaning "
      "{penalty} foizi miqdorida penya toʻlaydi, biroq penyaning umumiy miqdori kechiktirilgan "
      "summaning {max_penalty} foizidan oshmasligi kerak.",
      "Majburiyatlarini bajarmagan yoki lozim darajada bajarmagan taraf ikkinchi tarafga "
      "yetkazilgan haqiqiy zararni Oʻzbekiston Respublikasi qonunchiligiga muvofiq qoplaydi.",
      "Penya toʻlanishi taraflarni ushbu shartnoma boʻyicha majburiyatlarni bajarishdan ozod "
      "qilmaydi."],
     ["За каждый день просрочки оплаты {party_b} уплачивает пеню в размере {penalty} процента "
      "от просроченной суммы, но не более {max_penalty} процентов от просроченной суммы.",
      "Сторона, не исполнившая или ненадлежащим образом исполнившая свои обязательства, "
      "возмещает другой стороне причинённый реальный ущерб в соответствии с "
      "законодательством Республики Узбекистан.",
      "Уплата пени не освобождает стороны от исполнения обязательств по настоящему договору."]),
    ("Fors-major holatlari", "Форс-мажор",
     ["Taraflar yengib boʻlmaydigan kuch holatlari (zilzila, suv toshqini, yongʻin, harbiy "
      "harakatlar, davlat organlarining qarorlari) natijasida majburiyatlarni bajarmaganlik "
      "uchun javobgar boʻlmaydi.",
      "Bunday holatlar yuz bergan taraf ikkinchi tarafni {notice_days} kun ichida yozma "
      "ravishda xabardor qilishi shart.",
      "Fors-major holatlari ikki oydan ortiq davom etsa, har bir taraf shartnomani bir "
      "tomonlama bekor qilishga haqli."],
     ["Стороны освобождаются от ответственности за неисполнение обязательств, вызванное "
      "обстоятельствами непреодолимой силы (землетрясение, наводнение, пожар, военные "
      "действия, решения государственных органов).",
      "Сторона, для которой наступили такие обстоятельства, обязана письменно уведомить "
      "другую сторону в течение {notice_days} дней.",
      "Если обстоятельства непреодолимой силы длятся более двух месяцев, каждая сторона "
      "вправе расторгнуть договор в одностороннем порядке."]),
    ("Nizolarni hal qilish tartibi", "Порядок разрешения споров",
     ["Shartnoma yuzasidan kelib chiqadigan nizolar taraflar oʻrtasida muzokaralar yoʻli "
      "bilan hal qilinadi.",
      "Talabnoma yuborilgan kundan boshlab {notice_days} kun ichida kelishuvga erishilmasa, "
      "nizo {city} shahridagi iqtisodiy sudda koʻrib chiqiladi."],
     ["Споры, вытекающие из договора, решаются сторонами путём переговоров.",
      "Если согласие не достигнуто в течение {notice_days} дней с даты направления претензии, "
      "спор рассматривается в экономическом суде города {city}."]),
    ("Shartnomaning amal qilish muddati", "Срок действия договора",
     ["Shartnoma taraflar imzolagan kundan boshlab kuchga kiradi va {term} oy davomida amal "
      "qiladi.",
      "Shartnoma taraflarning yozma kelishuviga koʻra muddatidan oldin bekor qilinishi "
      "mumkin. Bekor qilish niyati haqida ikkinchi taraf kamida {notice_days} kun oldin "
      "ogohlantiriladi.",
      "Shartnoma ikki nusxada tuzildi, har ikkala nusxa bir xil yuridik kuchga ega."],
     ["Договор вступает в силу с даты подписания сторонами и действует в течение {term} "
      "месяцев.",
      "Договор может быть расторгнут досрочно по письменному соглашению сторон. О намерении "
      "расторгнуть договор другая сторона уведомляется не менее чем за {notice_days} дней.",
      "Договор составлен в двух экземплярах, имеющих одинаковую юридическую силу."]),
    ("Taraflarning rekvizitlari", "Реквизиты сторон",
     ["{party_a}: manzil {address}. Direktor {person_a}.",
      "{party_b}: manzil {city} shahri. Direktor {person_b}."],
     ["{party_a}: адрес {address}. Директор {person_a}.",
      "{party_b}: адрес г. {city}. Директор {person_b}."]),
]

TEMPLATES = {
    "ijara": {
        "title": ("NOTURAR JOYNI IJARAGA BERISH SHARTNOMASI", "ДОГОВОР АРЕНДЫ НЕЖИЛОГО ПОМЕЩЕНИЯ"),
        "intro": ("{city} shahri, {date}. Shartnoma № {num}. {party_a} (keyingi oʻrinlarda "
                  "Ijaraga beruvchi) direktor {person_a} nomidan va {party_b} (keyingi "
                  "oʻrinlarda Ijarachi) direktor {person_b} nomidan quyidagilar haqida ushbu "
                  "shartnomani tuzdilar.",
                  "г. {city}, {date}. Договор № {num}. {party_a} (далее Арендодатель) в лице "
                  "директора {person_a} и {party_b} (далее Арендатор) в лице директора "
                  "{person_b} заключили настоящий договор о нижеследующем."),
        "sections": [
            ("Shartnoma predmeti", "Предмет договора",
             ["Ijaraga beruvchi Ijarachiga {address} manzilida joylashgan, umumiy maydoni "
              "{area} kvadrat metr boʻlgan noturar joyni vaqtincha egalik qilish va foydalanish "
              "uchun beradi.",
              "Joy Ijarachi tomonidan ofis sifatida foydalanish uchun beriladi.",
              "Joy qabul qilish-topshirish dalolatnomasi asosida topshiriladi."],
             ["Арендодатель передаёт Арендатору во временное владение и пользование нежилое "
              "помещение общей площадью {area} квадратных метров, расположенное по адресу "
              "{address}.",
              "Помещение передаётся Арендатору для использования в качестве офиса.",
              "Помещение передаётся по акту приёма-передачи."]),
            ("Ijara haqi va toʻlov tartibi", "Арендная плата и порядок расчётов",
             ["Oylik ijara haqi {amount} soʻmni tashkil etadi.",
              "Ijarachi ijara haqini har oyning {pay_days}-sanasigacha Ijaraga beruvchining "
              "hisob raqamiga oʻtkazadi.",
              "Ijarachi shartnoma imzolangandan keyin {notice_days} kun ichida {deposit} soʻm "
              "miqdorida kafolat puli toʻlaydi.",
              "Kommunal xizmatlar haqi ijara haqiga kirmaydi va Ijarachi tomonidan alohida "
              "toʻlanadi."],
             ["Ежемесячная арендная плата составляет {amount} сумов.",
              "Арендатор перечисляет арендную плату на расчётный счёт Арендодателя до "
              "{pay_days}-го числа каждого месяца.",
              "В течение {notice_days} дней после подписания договора Арендатор вносит "
              "обеспечительный платёж в размере {deposit} сумов.",
              "Коммунальные платежи не входят в арендную плату и оплачиваются Арендатором "
              "отдельно."]),
            ("Taraflarning huquq va majburiyatlari", "Права и обязанности сторон",
             ["Ijarachi joydan uning maqsadiga muvofiq foydalanishi va uni soz holatda "
              "saqlashi shart.",
              "Ijarachi Ijaraga beruvchining yozma roziligisiz joyni qayta ijaraga berishga "
              "haqli emas.",
              "Ijaraga beruvchi joyni kapital taʼmirlashni oʻz hisobidan amalga oshiradi.",
              "Joriy taʼmirlash Ijarachi hisobidan amalga oshiriladi."],
             ["Арендатор обязан использовать помещение по назначению и содержать его в "
              "исправном состоянии.",
              "Арендатор не вправе сдавать помещение в субаренду без письменного согласия "
              "Арендодателя.",
              "Капитальный ремонт помещения производится Арендодателем за свой счёт.",
              "Текущий ремонт производится за счёт Арендатора."]),
        ],
    },
    "xizmat": {
        "title": ("XIZMAT KOʻRSATISH SHARTNOMASI", "ДОГОВОР ВОЗМЕЗДНОГО ОКАЗАНИЯ УСЛУГ"),
        "intro": ("{city} shahri, {date}. Shartnoma № {num}. {party_a} (keyingi oʻrinlarda "
                  "Ijrochi) direktor {person_a} nomidan va {party_b} (keyingi oʻrinlarda "
                  "Buyurtmachi) direktor {person_b} nomidan ushbu shartnomani tuzdilar.",
                  "г. {city}, {date}. Договор № {num}. {party_a} (далее Исполнитель) в лице "
                  "директора {person_a} и {party_b} (далее Заказчик) в лице директора "
                  "{person_b} заключили настоящий договор."),
        "sections": [
            ("Shartnoma predmeti", "Предмет договора",
             ["Ijrochi Buyurtmachining topshirigʻiga koʻra {service} xizmatlarini koʻrsatadi, "
              "Buyurtmachi esa ushbu xizmatlar haqini toʻlaydi.",
              "Xizmatlar ish kunlari soat {hours} oraligʻida koʻrsatiladi.",
              "Ijrochi har oyning {report_day}-sanasigacha bajarilgan ishlar dalolatnomasini "
              "taqdim etadi."],
             ["Исполнитель по заданию Заказчика оказывает услуги: {service}, а Заказчик "
              "оплачивает эти услуги.",
              "Услуги оказываются в рабочие дни с {hours}.",
              "Исполнитель до {report_day}-го числа каждого месяца представляет акт "
              "выполненных работ."]),
            ("Xizmatlar narxi va toʻlov tartibi", "Стоимость услуг и порядок оплаты",
             ["Xizmatlarning oylik narxi {amount} soʻmni tashkil etadi.",
              "Buyurtmachi dalolatnoma imzolangan kundan boshlab {pay_days} bank kuni ichida "
              "toʻlovni amalga oshiradi.",
              "Narx taraflarning yozma kelishuvisiz oʻzgartirilmaydi."],
             ["Ежемесячная стоимость услуг составляет {amount} сумов.",
              "Заказчик производит оплату в течение {pay_days} банковских дней с даты "
              "подписания акта.",
              "Цена не может быть изменена без письменного соглашения сторон."]),
            ("Taraflarning huquq va majburiyatlari", "Права и обязанности сторон",
             ["Ijrochi xizmatlarni sifatli va oʻz vaqtida koʻrsatishi shart.",
              "Buyurtmachi Ijrochiga xizmat koʻrsatish uchun zarur boʻlgan maʼlumotlarni "
              "{notice_days} kun ichida taqdim etadi.",
              "Ijrochi Buyurtmachining roziligisiz uchinchi shaxslarni jalb qilishga haqli emas.",
              "Taraflar shartnoma doirasida olingan maxfiy maʼlumotlarni oshkor qilmaslik "
              "majburiyatini oladi."],
             ["Исполнитель обязан оказывать услуги качественно и в срок.",
              "Заказчик в течение {notice_days} дней предоставляет Исполнителю информацию, "
              "необходимую для оказания услуг.",
              "Исполнитель не вправе привлекать третьих лиц без согласия Заказчика.",
              "Стороны обязуются не разглашать конфиденциальную информацию, полученную в "
              "рамках договора."]),
        ],
    },
    "oldi_sotdi": {
        "title": ("MAHSULOT YETKAZIB BERISH SHARTNOMASI", "ДОГОВОР ПОСТАВКИ ТОВАРА"),
        "intro": ("{city} shahri, {date}. Shartnoma № {num}. {party_a} (keyingi oʻrinlarda "
                  "Yetkazib beruvchi) direktor {person_a} nomidan va {party_b} (keyingi "
                  "oʻrinlarda Xaridor) direktor {person_b} nomidan ushbu shartnomani tuzdilar.",
                  "г. {city}, {date}. Договор № {num}. {party_a} (далее Поставщик) в лице "
                  "директора {person_a} и {party_b} (далее Покупатель) в лице директора "
                  "{person_b} заключили настоящий договор."),
        "sections": [
            ("Shartnoma predmeti", "Предмет договора",
             ["Yetkazib beruvchi Xaridorga {goods}ni {quantity} dona miqdorida yetkazib "
              "beradi, Xaridor esa uni qabul qiladi va haqini toʻlaydi.",
              "Mahsulot sifati amaldagi standartlarga va sertifikatlarga mos boʻlishi kerak."],
             ["Поставщик поставляет Покупателю товар ({goods}) в количестве {quantity} штук, "
              "а Покупатель принимает и оплачивает его.",
              "Качество товара должно соответствовать действующим стандартам и сертификатам."]),
            ("Narx va toʻlov shartlari", "Цена и условия оплаты",
             ["Shartnomaning umumiy summasi {amount} soʻmni tashkil etadi.",
              "Xaridor shartnoma summasining 30 foizini {pay_days} bank kuni ichida oldindan "
              "toʻlaydi, qolgan qismini mahsulot qabul qilingandan keyin toʻlaydi.",
              "Mahsulotni tashish xarajatlari Yetkazib beruvchi zimmasida."],
             ["Общая сумма договора составляет {amount} сумов.",
              "Покупатель вносит предоплату в размере 30 процентов суммы договора в течение "
              "{pay_days} банковских дней, остаток оплачивается после приёмки товара.",
              "Расходы по доставке товара несёт Поставщик."]),
            ("Yetkazib berish va qabul qilish", "Поставка и приёмка",
             ["Mahsulot oldindan toʻlov kelib tushgan kundan boshlab {delivery_days} kun ichida "
              "Xaridorning omboriga yetkazib beriladi.",
              "Mahsulot miqdori va sifati boʻyicha qabul qilish yuk xati asosida amalga "
              "oshiriladi.",
              "Yetkazib beruvchi mahsulotga {warranty} oy kafolat beradi. Kafolat muddatida "
              "aniqlangan nuqsonlar Yetkazib beruvchi hisobidan bartaraf etiladi."],
             ["Товар доставляется на склад Покупателя в течение {delivery_days} дней с даты "
              "поступления предоплаты.",
              "Приёмка товара по количеству и качеству производится на основании накладной.",
              "Поставщик предоставляет гарантию на товар сроком {warranty} месяцев. Недостатки, "
              "выявленные в течение гарантийного срока, устраняются за счёт Поставщика."]),
        ],
    },
}

# Invented values only. Company names are made-up words; person names are initials plus
# invented surnames.
COMPANIES = ["Yashil Vodiy", "Oq Tosh Savdo", "Ufq Servis", "Samo Qurilish", "Nurli Yoʻl",
             "Bogʻbon Agro", "Tiniq Suv", "Kumush Ip", "Sharq Daftar", "Yulduz Texno"]
SURNAMES = ["Namunov", "Sinovov", "Misolov", "Xayolov", "Oʻylabov", "Toʻqimov"]
INITIALS = ["A.", "B.", "D.", "J.", "K.", "M.", "N.", "O.", "S.", "U."]
CITIES = ["Toshkent", "Samarqand", "Buxoro", "Namangan", "Andijon", "Fargʻona", "Nukus"]
CITIES_RU = {"Toshkent": "Ташкент", "Samarqand": "Самарканд", "Buxoro": "Бухара",
             "Namangan": "Наманган", "Andijon": "Андижан", "Fargʻona": "Фергана",
             "Nukus": "Нукус"}
STREETS = ["Sinov koʻchasi", "Namuna koʻchasi", "Misol shoh koʻchasi"]
GOODS = [("ofis stullari", "офисные стулья"), ("noutbuklar", "ноутбуки"),
         ("printer kartrijlari", "картриджи для принтеров"), ("suv filtrlari", "фильтры для воды")]
SERVICES = [("buxgalteriya hisobini yuritish", "ведение бухгалтерского учёта"),
            ("ofisni tozalash", "уборка офиса"),
            ("kompyuter tarmogʻiga texnik xizmat koʻrsatish",
             "техническое обслуживание компьютерной сети"),
            ("yuk tashish", "грузоперевозки")]
