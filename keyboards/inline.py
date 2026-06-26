from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def kb(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Qulay inline keyboard yasash: kb([('Matn','data'), ...], [...])"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row]
        for row in rows
    ])


# ── Til ──────────────────────────────────────────────────────
def lang_kb() -> InlineKeyboardMarkup:
    return kb(
        [("🇺🇿 O'zbek (Lotin)", "lang:uz")],
        [("🇺🇿 Ўзбек (Кирилл)", "lang:uz_cyr")],
        [("🇷🇺 Русский",        "lang:ru")],
    )


# ── Rol ──────────────────────────────────────────────────────
def role_kb() -> InlineKeyboardMarkup:
    return kb(
        [("🏷 Men sotaman",    "role:seller")],
        [("🔍 Men qidiraman",  "role:buyer")],
        [("👔 Men maklerman",  "role:makler")],
        [("🏗 Men quruvchiman","role:builder")],
        [("❓ Maslahat olaman","role:consult")],
    )


# ── Tranzaksiya turi ─────────────────────────────────────────
def transaction_kb() -> InlineKeyboardMarkup:
    """Sotuvchi uchun"""
    return kb(
        [("🏷 Uyimni sotaman",    "trx:sotish")],
        [("🔑 Ijaraga beraman",   "trx:arenda")],
    )


def buyer_transaction_kb() -> InlineKeyboardMarkup:
    """Xaridor uchun"""
    return kb(
        [("🏷 Sotib olishga izlayabman",  "trx:sotish")],
        [("🔑 Ijaraga izlayabman",         "trx:arenda")],
    )


def rent_for_kb() -> InlineKeyboardMarkup:
    return kb(
        [("👨‍👩‍👧 Oila",        "rf:oila")],
        [("🌍 Chet ellik",   "rf:chet_ellik")],
        [("👦 Yigitlar",     "rf:yigitlar")],
        [("👧 Qizlar",       "rf:qizlar")],
        [("✅ Farqi yo'q",   "rf:farqi_yoq")],
    )


# ── Mulk turi ────────────────────────────────────────────────
def property_type_kb(prefix: str = "pt") -> InlineKeyboardMarkup:
    return kb(
        [("🏡 Hovli",          f"{prefix}:hovli"),
         ("🏢 Kvartira",       f"{prefix}:kvartira")],
        [("🏬 Ofis / Noturar", f"{prefix}:ofis"),
         ("🌿 Yer",            f"{prefix}:yer")],
    )


# ── Dom turi ─────────────────────────────────────────────────
def dom_type_kb() -> InlineKeyboardMarkup:
    return kb(
        [("🏢 Novostroyka (Yangi qurilish)", "dt:novo")],
        [("🏚 Eski dom",                     "dt:eski")],
        [("⬅️ Ortga", "back:property_type")],
    )


# ── Viloyat ──────────────────────────────────────────────────
def viloyat_kb(viloyatlar: list[str], prefix: str = "vil",
               extra_top: str = None) -> InlineKeyboardMarkup:
    rows = []
    # Yuqorida qo'shimcha tugma (masalan "Butun O'zbekiston")
    if extra_top:
        text, data = extra_top.split("|")
        rows.append([(text, data)])
    row = []
    for v in viloyatlar:
        if v == "Toshkent shahri":
            short = "Toshkent shahar"
        elif v == "Toshkent viloyati":
            short = "Toshkent viloyati"
        else:
            short = v.replace(" viloyati", "").replace(" shahri", "")
        row.append((short, f"{prefix}:{v}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([("🔍 Qidirish", "search:vil"), ("⬅️ Ortga", "back:dom_type")])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row]
        for row in rows
    ])


# ── Tuman ────────────────────────────────────────────────────
def tuman_kb(tumanlar: list[str], prefix: str = "tum") -> InlineKeyboardMarkup:
    rows = []
    row = []
    for t in tumanlar:
        short = t.replace(" tumani", "").replace(" shahri", " sh.")
        row.append((short, f"{prefix}:{t}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([("⬅️ Ortga", "back:viloyat")])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row]
        for row in rows
    ])


# ── Mahalla ──────────────────────────────────────────────────
def mahalla_kb(mahallalar: list[dict], total: int, offset: int,
               prefix: str = "mah") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=m["mahalla"], callback_data=f"{prefix}:{m['id']}")]
            for m in mahallalar]
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="⬆️ Oldingi", callback_data=f"mah_page:{offset-8}"))
    if offset + 8 < total:
        nav.append(InlineKeyboardButton(text="⬇️ Ko'proq", callback_data=f"mah_page:{offset+8}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔍 Qidirish", callback_data="search:mah"),
                 InlineKeyboardButton(text="⬅️ Ortga",    callback_data="back:tuman")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Dom raqami (topilganlar) ─────────────────────────────────
def buildings_kb(buildings: list[dict]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
                text=f"📍 {b['dom_number']}" + (f" ({b['kvartal']})" if b.get("kvartal") else ""),
                callback_data=f"bld:{b['id']}")]
            for b in buildings]
    rows.append([InlineKeyboardButton(text="✏️ O'zim kiritaman", callback_data="bld:manual")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def loc_confirm_kb(building_id: int) -> InlineKeyboardMarkup:
    return kb(
        [("✅ Ha, to'g'ri", f"locok:{building_id}"),
         ("❌ Yo'q, boshqa", "bld:manual")],
    )


def loc_save_kb() -> InlineKeyboardMarkup:
    return kb(
        [("✅ Ha, bazaga saqla", "locsave:yes"),
         ("➡️ Yo'q, davom et",  "locsave:no")],
    )


# ── Remont ──────────────────────────────────────────────────
def renovation_kb() -> InlineKeyboardMarkup:
    return kb(
        [("🧱 Karobka",          "renov:karobka")],
        [("🔧 Ta'mirtalab",       "renov:tamirtalab")],
        [("🏠 O'rtacha",         "renov:ortacha")],
        [("🎨 Kosmetika",        "renov:kosmetika")],
        [("🏗 Kapital ta'mir",   "renov:kapital")],
        [("✨ Yevroremont",      "renov:evro")],
        [("🖼 Dizaynerlik",      "renov:dizayn")],
        [("⬅️ Ortga", "back:area")],
    )


# ── Narx ────────────────────────────────────────────────────
def currency_kb() -> InlineKeyboardMarkup:
    return kb(
        [("💵 Dollar ($)", "cur:usd"), ("🇺🇿 So'm",  "cur:som")],
        [("⬅️ Ortga", "back:landmark")],
    )


# ── Tasdiqlash ───────────────────────────────────────────────
def confirm_publish_kb() -> InlineKeyboardMarkup:
    return kb(
        [("✅ Nashr qilish", "pub:yes")],
        [("✏️ Tahrirlash",   "pub:edit"), ("⬅️ Ortga", "back:price")],
    )


# ── Sotuvchi kabineti ────────────────────────────────────────
def listing_manage_kb(listing_id: int) -> InlineKeyboardMarkup:
    return kb(
        [("✅ Sotildi",     f"lst:sold:{listing_id}"),
         ("🗑 O'chirish",  f"lst:del:{listing_id}")],
        [("📉 Narx tushirish", f"lst:price:{listing_id}")],
    )


# ── Xaridor — raqam ko'rish ──────────────────────────────────
def contact_kb(listing_id: int) -> InlineKeyboardMarkup:
    return kb(
        [("📞 Raqamni ko'rish", f"cl:phone:{listing_id}"),
         ("❤️ Saqlash",         f"cl:fav:{listing_id}")],
        [("🚩 Shikoyat",        f"cl:report:{listing_id}")],
    )


# ── Natijalar pagination ─────────────────────────────────────
def results_nav_kb(offset: int, total: int, filter_key: str) -> InlineKeyboardMarkup:
    rows = []
    nav = []
    if offset + 5 < total:
        nav.append(InlineKeyboardButton(text=f"⬇️ Ko'proq ({total - offset - 5} ta)",
                                        callback_data=f"rn:more"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔍 Yangi qidiruv", callback_data="rn:new"),
                 InlineKeyboardButton(text="🔔 Obuna",         callback_data="rn:sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Xonalar ─────────────────────────────────────────────────
def xonalar_kb(prefix: str = "xon", with_any: bool = False,
               page: int = 0) -> InlineKeyboardMarkup:
    """
    page=0 → 1–6   + "➕ Ko'proq (7–15)"
    page=1 → 7–15  + "⬅️ Kamroq"
    """
    rows = []
    if page == 0:
        nums = range(1, 7)       # 1–6
    else:
        nums = range(7, 19)      # 7–18

    chunk = [InlineKeyboardButton(text=f"{n}xona", callback_data=f"{prefix}:{n}")
             for n in nums]
    # 3 ta ustun
    for i in range(0, len(chunk), 3):
        rows.append(chunk[i:i+3])

    if page == 0:
        rows.append([InlineKeyboardButton(text="➕ Ko'proq (7–18)",
                                          callback_data=f"{prefix}:p1")])
    else:
        rows.append([InlineKeyboardButton(text="⬅️ Kamroq (1–6)",
                                          callback_data=f"{prefix}:p0")])

    if with_any:
        rows.append([InlineKeyboardButton(text="✅ Farqi yo'q",
                                          callback_data=f"{prefix}:any")])

    rows.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data="back:video")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Qavat tanlash (floor) ────────────────────────────────────
def floor_kb(prefix: str = "fl", page: int = 0, qavatli: bool = False) -> InlineKeyboardMarkup:
    """
    page=0 → 1–16   + "➕ Yana (17–32)"
    page=1 → 17–32  + "➕ Yana (33–46)"  + "⬅️ Kamroq"
    page=2 → 33–46  + "⬅️ Kamroq"
    """
    rows = []
    if page == 0:
        nums = range(1, 17)
    elif page == 1:
        nums = range(17, 33)
    else:
        nums = range(33, 47)

    label = "{n}qavatli" if qavatli else "{n}-qavat"
    chunk = [InlineKeyboardButton(text=label.format(n=n), callback_data=f"{prefix}:{n}")
             for n in nums]
    # 4 ta ustun
    for i in range(0, len(chunk), 4):
        rows.append(chunk[i:i+4])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Kamroq",
                                        callback_data=f"{prefix}:p{page-1}"))
    if page == 0:
        nav.append(InlineKeyboardButton(text="➕ Yana (17–32)",
                                        callback_data=f"{prefix}:p1"))
    elif page == 1:
        nav.append(InlineKeyboardButton(text="➕ Yana (33–46)",
                                        callback_data=f"{prefix}:p2"))
    if nav:
        rows.append(nav)

    # Ortga: fl → xonalar, tf → floor
    back_target = "xonalar" if prefix == "fl" else "floor"
    rows.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"back:{back_target}")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Maydon (area) ────────────────────────────────────────────
def area_kb(prefix: str = "area", page: int = 0) -> InlineKeyboardMarkup:
    """
    page=0 → 28–67
    page=1 → 68–107
    page=2 → 108–150
    + "✏️ O'zim yozaman" har doim
    """
    PER_PAGE = 40
    starts = [28, 68, 108]
    start = starts[page]
    end   = min(start + PER_PAGE, 151)   # 150 gacha

    rows = []
    chunk = [InlineKeyboardButton(text=str(n), callback_data=f"{prefix}:{n}")
             for n in range(start, end)]
    for i in range(0, len(chunk), 5):
        rows.append(chunk[i:i+5])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text=f"⬅️ Kamroq ({starts[page-1]}–{start-1})",
                                        callback_data=f"{prefix}:p{page-1}"))
    if end < 151:
        nav.append(InlineKeyboardButton(text=f"➕ Yana ({end}→)",
                                        callback_data=f"{prefix}:p{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="✏️ O'zim yozaman",
                                      callback_data=f"{prefix}:manual"),
                 InlineKeyboardButton(text="⬅️ Ortga",
                                      callback_data="back:total_floors")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Filtrlar ─────────────────────────────────────────────────
def dom_type_filter_kb() -> InlineKeyboardMarkup:
    return kb(
        [("🏢 Novostroyka", "fdt:novo"), ("🏚 Eski", "fdt:eski")],
        [("✅ Farqi yo'q",   "fdt:any")],
        [("⬅️ Ortga", "back:xonalar")],
    )


def renovation_filter_kb() -> InlineKeyboardMarkup:
    return kb(
        [("🧱 Karobka",    "fren:karobka"), ("🔧 Ta'mirtalab", "fren:tamirtalab")],
        [("🏠 O'rtacha",         "fren:ortacha"),  ("🎨 Kosmetika",       "fren:kosmetika")],
        [("🏗 Kapital ta'mir",  "fren:kapital"),  ("✨ Yevroremont",     "fren:evro")],
        [("🖼 Dizaynerlik",     "fren:dizayn")],
        [("✅ Farqi yo'q", "fren:any")],
        [("⬅️ Ortga", "back:dom_type_filter")],
    )


# ── Shikoyat sababi ──────────────────────────────────────────
def report_reason_kb(listing_id: int) -> InlineKeyboardMarkup:
    return kb(
        [("✅ Sotilgan ekan",              f"rep:sotilgan:{listing_id}")],
        [("👻 Mavjud emas / Soxta e'lon", f"rep:soxta:{listing_id}")],
        [("💰 Narx noto'g'ri",            f"rep:narx:{listing_id}")],
        [("📵 Aloqa yo'q / Javob bermaydi", f"rep:aloqa:{listing_id}")],
        [("🎭 Firibgarlik shubhasi",       f"rep:firib:{listing_id}")],
        [("✏️ Boshqa sabab",              f"rep:boshqa:{listing_id}")],
    )


# ── Balkon ──────────────────────────────────────────────────
def balkon_kb() -> InlineKeyboardMarkup:
    return kb(
        [("1×3",   "blk:1x3"),   ("1.5×3", "blk:1.5x3")],
        [("1×7",   "blk:1x7"),   ("1.5×6", "blk:1.5x6")],
        [("2×6",   "blk:2x6")],
        [("❌ Balkonsiz", "blk:yoq")],
    )


# ── Jihoz (multi-select) ─────────────────────────────────────
JIHOZ_LIST = [
    ("📺 Televizor",            "televizor"),
    ("❄️ Konditsioner",         "konditsioner"),
    ("🧊 Xolodilnik",           "xolodilnik"),
    ("🫧 Kir yuvish mashinasi", "steralka"),
    ("🚪 Shkaf",                "shkaf"),
    ("🏠 Gilam",                "gilam"),
    ("🛏 Spalnya",              "spalnya"),
    ("🛋 Divan",                "divan"),
]


def jihoz_kb(selected: set) -> InlineKeyboardMarkup:
    rows = []
    for label, key in JIHOZ_LIST:
        mark = "✅ " if key in selected else "◻️ "
        rows.append([InlineKeyboardButton(text=mark + label, callback_data=f"jh:{key}")])
    rows.append([InlineKeyboardButton(text="✔️ Tayyor", callback_data="jh:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Vositachilik haqi ────────────────────────────────────────
def commission_kb() -> InlineKeyboardMarkup:
    return kb(
        [("✅ Ha, bor",  "com:yes")],
        [("❌ Yo'q",     "com:no")],
    )


# ── Kvartal tugmalari ─────────────────────────────────────────
def kvartal_kb(kvartals: list[dict]) -> InlineKeyboardMarkup:
    """Tuman bo'yicha kvartal tugmalari (4 qator, har birida 3 ta)."""
    rows = []
    row = []
    for kv in kvartals:
        n = kv["kvartal_n"]
        row.append(InlineKeyboardButton(text=f"{n}-kvartal", callback_data=f"kv:{n}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Ko'cha tugmalari ──────────────────────────────────────────
STREETS_PAGE = 8

def street_kb(streets: list[str], offset: int = 0, total: int = 0, show_search: bool = True) -> InlineKeyboardMarkup:
    """Ko'chalar ro'yxati tugmalari (pagination bilan)."""
    rows = []
    for s in streets:
        label = s.title()[:35]
        rows.append([InlineKeyboardButton(text=label, callback_data=f"str:{s[:60]}")])
    nav = []
    if offset > 0:
        rows.append([InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"str_page:{offset - STREETS_PAGE}")])
    if offset + STREETS_PAGE < total:
        rows.append([InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"str_page:{offset + STREETS_PAGE}")])
    if show_search:
        rows.append([InlineKeyboardButton(text="🔍 Qidirish", callback_data="str_search")])
    rows.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="str_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Dom raqami tugmalari ──────────────────────────────────────
def dom_kb(houses: list[dict], offset: int = 0, total: int = 0) -> InlineKeyboardMarkup:
    """Dom raqamlari tugmalari — hammasi bir sahifada, scroll qiladi."""
    rows = []
    row = []
    for h in houses:
        hn = h.get("dom_number") or h.get("house_number", "")
        row.append(InlineKeyboardButton(text=f"{hn}-dom", callback_data=f"dom:{hn}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✏️ Qo'lda yozish", callback_data="dom:manual")])
    rows.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="dom:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
