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


# ── Mulk turi ────────────────────────────────────────────────
def property_type_kb(prefix: str = "pt") -> InlineKeyboardMarkup:
    return kb(
        [("🏡 Hovli",          f"{prefix}:hovli"),
         ("🏢 Kvartira",       f"{prefix}:kvartira")],
        [("🏬 Ofis / Noturar", f"{prefix}:ofis"),
         ("🌿 Yer",            f"{prefix}:yer")],
        [("❓ Yordam",         "help:property_type")],
    )


# ── Dom turi ─────────────────────────────────────────────────
def dom_type_kb() -> InlineKeyboardMarkup:
    return kb(
        [("🏢 Novostroyka (Yangi qurilish)", "dt:novo")],
        [("🏚 Eski dom",                     "dt:eski")],
        [("❓ Yordam", "help:dom_type"), ("⬅️ Ortga", "back:property_type")],
    )


# ── Viloyat ──────────────────────────────────────────────────
def viloyat_kb(viloyatlar: list[str], prefix: str = "vil") -> InlineKeyboardMarkup:
    rows = []
    row = []
    for v in viloyatlar:
        short = v.replace(" shahri", " sh.").replace(" viloyati", "")
        row.append((short, f"{prefix}:{v}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([("🔍 Qidirish", "search:vil"), ("❓", "help:location"), ("⬅️", "back:dom_type")])
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
    rows.append([("❓", "help:location"), ("⬅️", "back:viloyat")])
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
        [("✨ Evro",            "renov:evro")],
        [("🏠 O'rta",           "renov:orta")],
        [("🪣 Qora (ta'mirsiz)", "renov:qora")],
        [("🆕 Muallim",         "renov:muallim")],
        [("❓ Yordam", "help:renovation"), ("⬅️ Ortga", "back:area")],
    )


# ── Narx ────────────────────────────────────────────────────
def currency_kb() -> InlineKeyboardMarkup:
    return kb(
        [("💵 Dollar ($)", "cur:usd"), ("🇺🇿 So'm",  "cur:som")],
        [("❓ Yordam", "help:price"), ("⬅️ Ortga", "back:landmark")],
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
        [("📍 Lokatsiya",       f"cl:loc:{listing_id}"),
         ("🚩 Shikoyat",        f"cl:report:{listing_id}")],
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
               extended: bool = False) -> InlineKeyboardMarkup:
    """
    extended=False → 1–16 ko'rsatiladi + "Ko'proq 17–48" tugmasi
    extended=True  → 17–48 ko'rsatiladi + "Kamroq" tugmasi
    """
    rows = []
    if not extended:
        nums = range(1, 17)          # 1–16
    else:
        nums = range(17, 49)         # 17–48

    # 4 ta ustun
    chunk = [InlineKeyboardButton(text=str(n), callback_data=f"{prefix}:{n}")
             for n in nums]
    for i in range(0, len(chunk), 4):
        rows.append(chunk[i:i+4])

    # Ko'proq / Kamroq tugmasi
    if not extended:
        rows.append([InlineKeyboardButton(text="➕ Ko'proq (17–48)",
                                          callback_data=f"{prefix}:more")])
    else:
        rows.append([InlineKeyboardButton(text="⬅️ Kamroq (1–16)",
                                          callback_data=f"{prefix}:less")])

    if with_any:
        rows.append([InlineKeyboardButton(text="✅ Farqi yo'q",
                                          callback_data=f"{prefix}:any")])

    rows.append([InlineKeyboardButton(text="❓ Yordam", callback_data="help:xonalar")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Qavat tanlash (floor) ────────────────────────────────────
def floor_kb(prefix: str = "fl", extended: bool = False) -> InlineKeyboardMarkup:
    """
    extended=False → 1–16 ko'rsatiladi
    extended=True  → 17–48 ko'rsatiladi
    """
    rows = []
    nums = range(17, 49) if extended else range(1, 17)

    chunk = [InlineKeyboardButton(text=str(n), callback_data=f"{prefix}:{n}")
             for n in nums]
    for i in range(0, len(chunk), 4):
        rows.append(chunk[i:i+4])

    if not extended:
        rows.append([InlineKeyboardButton(text="➕ Ko'proq (17–48)",
                                          callback_data=f"{prefix}:more")])
    else:
        rows.append([InlineKeyboardButton(text="⬅️ Kamroq (1–16)",
                                          callback_data=f"{prefix}:less")])
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
        [("✨ Evro",  "fren:evro"), ("🏠 O'rta",  "fren:orta")],
        [("🪣 Qora",  "fren:qora"), ("🆕 Muallim","fren:muallim")],
        [("✅ Farqi yo'q", "fren:any")],
        [("⬅️ Ortga", "back:dom_type_filter")],
    )
