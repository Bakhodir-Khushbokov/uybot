from config import BANNED_WORDS

PROPERTY_LABELS = {
    "hovli":    "🏡 Hovli",
    "kvartira": "🏢 Kvartira",
    "ofis":     "🏬 Ofis / Noturar joy",
    "yer":      "🌿 Yer",
}
DOM_TYPE_LABELS = {
    "novo": "🏢 Novostroyka",
    "eski": "🏚 Eski dom",
}
RENOVATION_LABELS = {
    "karobka":    "🧱 Karobka",
    "tamirtalab": "🔧 Ta'mirtalab",
    "ortacha":    "🏠 O'rtacha",
    "kosmetika":  "🎨 Kosmetika",
    "kapital":    "🏗 Kapital ta'mir",
    "evro":       "✨ Yevroremont",
    "dizayn":     "🖼 Dizaynerlik",
}
RENOVATION_SHORT = {
    "karobka":    "karobka",
    "tamirtalab": "ta'mirtalab",
    "ortacha":    "o'rtacha",
    "kosmetika":  "kosmetika",
    "evro":       "yevroremont",
    "dizayn":     "dizayn",
    "kapital":    "kapital",
}


RENT_PERIOD_LABELS = {
    "oylik":    "/oy",
    "haftalik": "/hafta",
    "kunlik":   "/kun",
}


def format_price(amount: float, currency: str, rent_period: str = None) -> str:
    """
    USD:  47500      → 47.500$
    So'm: 350_000_000 → 350 mln so'm
          1_200_000_000 → 1.2 mlrd so'm
    """
    suffix = RENT_PERIOD_LABELS.get(rent_period, "") if rent_period else ""
    if currency == "usd":
        return f"{int(amount)}${suffix}"
    else:
        n = int(amount)
        if n >= 1_000_000_000:
            mlrd = n // 1_000_000_000
            qolgan_mln = (n % 1_000_000_000) // 1_000_000
            if qolgan_mln:
                return f"{mlrd} mlrd {qolgan_mln} mln so'm{suffix}"
            return f"{mlrd} mlrd so'm{suffix}"
        else:
            mln = n // 1_000_000
            qolgan = (n % 1_000_000) // 1_000
            if qolgan:
                return f"{mln} mln {qolgan} ming so'm{suffix}"
            return f"{mln} mln so'm{suffix}"


def parse_price_usd(text: str) -> float | None:
    """
    '47.500' → 47500.0
    '47,500' → 47500.0
    '47 500' → 47500.0
    """
    try:
        cleaned = (text.strip()
                   .replace("$", "")
                   .replace(" ", "")
                   .replace(",", "")
                   .replace(".", ""))
        return float(cleaned)
    except Exception:
        return None


def parse_price_som(text: str) -> float | None:
    """
    Aqlli formatlovchi — foydalanuvchi qanday yozishidan qat'i nazar:
      '350'           → 350_000_000   (350 mln)
      '350 000 000'   → 350_000_000   (350 mln)
      '340000000'     → 340_000_000   (340 mln)
      '1 200 000 000' → 1_200_000_000 (1.2 mlrd)
      '4500'          → 4_500_000_000 (4.5 mlrd)
      '1.2'           → 1_200_000_000 (1.2 mlrd — nuqtali mlrd)

    Qoida:
      - Bo'sh joy, nuqta, vergullarni olib tashlab sof raqam olinadi
      - Agar natija < 1_000_000 → millionlar birligida deb qabul qilinadi (*1_000_000)
      - Aks holda — haqiqiy so'm summa
    """
    try:
        raw = text.strip()

        # Nuqta bor va nuqtadan keyin 1-2 xona: "1.2" yoki "4.5" — mlrd formatda
        import re
        if re.match(r'^\d+\.\d{1,2}$', raw):
            n = float(raw)
            return n * 1_000_000_000   # 1.2 → 1.2 mlrd

        # Hamma ajratuvchilarni olib tashlash: bo'sh joy, nuqta, vergul
        cleaned = re.sub(r'[\s.,]', '', raw)
        n = float(cleaned)

        # 1_000_000 dan kichik → million birligida deb qabul qilish
        if n < 1_000_000:
            return n * 1_000_000

        return n
    except Exception:
        return None


def check_banned(text: str) -> str | None:
    """Taqiqlangan so'z topilsa — uni qaytaradi, yo'q bo'lsa None."""
    low = text.lower()
    for w in BANNED_WORDS:
        if w in low:
            return w
    return None


def listing_short_line(lst: dict) -> str:
    """Qisqa qator: 'Orinter  2xona  50m²  2/9  65.000$  O'rtacha'"""
    parts = []
    if lst.get("landmark"):
        parts.append(lst["landmark"])
    if lst.get("xonalar"):
        parts.append(f"{lst['xonalar']}xona")
    if lst.get("area"):
        parts.append(f"{int(lst['area'])}m²")
    if lst.get("floor") and lst.get("total_floors"):
        parts.append(f"{lst['floor']}-etaj/{lst['total_floors']}")
    if lst.get("price_display"):
        parts.append(lst["price_display"])
    if lst.get("renovation"):
        parts.append(RENOVATION_SHORT.get(lst["renovation"], lst["renovation"]).capitalize())
    return "  ".join(parts) if parts else "E'lon"


RENT_FOR_LABELS = {
    "oila": "👨‍👩‍👧 Oila", "chet_ellik": "🌍 Chet ellik",
    "yigitlar": "👦 Yigitlar", "qizlar": "👧 Qizlar", "farqi_yoq": "✅ Farqi yo'q",
}
JIHOZ_ICONS = {
    "televizor": "📺", "konditsioner": "❄️", "xolodilnik": "🧊",
    "steralka": "🫧", "shkaf": "🚪", "gilam": "🏠",
    "spalnya": "🛏", "divan": "🛋",
}


def listing_full_card(lst: dict, loc: dict | None = None) -> str:
    import json as _json

    lines = []

    # 1. Sarlavha — "Sotiladi kvartira · Eski dom" yoki "Ijaraga kvartira · Novostroyka"
    trx   = "Ijaraga" if lst.get("transaction_type") == "arenda" else "Sotiladi"
    ptype_raw = lst.get("property_type", "")
    ptype = {"kvartira": "kvartira", "hovli": "hovli",
             "ofis": "ofis / noturar joy", "yer": "yer parchasiga"}.get(ptype_raw, ptype_raw)
    dtype = {"novo": "Novostroyka", "eski": "Eski dom"}.get(lst.get("dom_type", ""), "")
    title = f"🏷 <b>{trx} {ptype}"
    if dtype:
        title += f" · {dtype}"
    title += "</b>"
    lines.append(title)

    # 2. Joylashuv
    if loc:
        parts = []
        viloyat = loc.get("viloyat", "")
        tuman   = loc.get("tuman", "").replace(" tumani","").replace(" shahri","")
        mahalla = loc.get("mahalla", "")
        if viloyat: parts.append(viloyat)
        if tuman:   parts.append(tuman)
        if mahalla: parts.append(mahalla)
        if parts:
            lines.append("📍 " + ", ".join(parts))
    if lst.get("landmark"):
        lines.append(f"▫️ Mo'ljal: {lst['landmark']}")

    # 3. Asosiy parametrlar — bir qatorda
    params = []
    if lst.get("xonalar"):
        params.append(f"▫️ {lst['xonalar']} xona")
    if lst.get("area"):
        params.append(f"{int(lst['area'])} m²")
    if lst.get("floor") and lst.get("total_floors"):
        params.append(f"{lst['floor']}-etaj/{lst['total_floors']}")
    if params:
        lines.append("  ".join(params))

    # 4. Ta'mirlash va balkon — alohida qatorlarda
    renov = RENOVATION_LABELS.get(lst.get("renovation", ""), "")
    if renov:
        lines.append(f"▫️ Ta'mir: {renov}")
    if lst.get("balkon"):
        lines.append(f"▫️ Balkon: {lst['balkon']} m")

    # 5. Jihoz (arenda uchun)
    if lst.get("jihoz"):
        try:
            items = _json.loads(lst["jihoz"]) if isinstance(lst["jihoz"], str) else lst["jihoz"]
            names = [JIHOZ_ICONS.get(i, "") + " " + i.capitalize() for i in items if i]
            if names:
                lines.append("🛋 " + "  ".join(names))
        except Exception:
            pass

    if lst.get("rent_for"):
        lines.append(f"👥 {RENT_FOR_LABELS.get(lst['rent_for'], lst['rent_for'])}")

    if lst.get("has_commission"):
        lines.append("💼 Vositachi orqali")

    # 6. Narx
    if lst.get("price_display"):
        lines.append(f"\n💰 <b>{lst['price_display']}</b>")

    # 7. Telefon — so'nggi 4 raqam yashirin
    phone = lst.get("phone", "")
    if phone:
        lines.append(f"📞 {mask_phone(phone)}")

    return "\n".join(lines)


def mask_phone(phone: str) -> str:
    """'+998901234567' → '+998 90 *** 23 45'  (so'nggi 4 raqam ko'rinadi)"""
    p = phone.replace("+", "").replace(" ", "")
    if len(p) >= 12:
        return f"+{p[:3]} {p[3:5]} *** {p[-4:-2]} {p[-2:]}"
    return phone


def make_progress(step: int, total: int) -> str:
    filled = "▓" * step
    empty  = "░" * (total - step)
    return f"`{filled}{empty}` Qadam {step}/{total}"
