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
    "evro":    "✨ Evro",
    "orta":    "🏠 O'rta",
    "qora":    "🪣 Qora (ta'mirsiz)",
    "muallim": "🆕 Muallim",
}
RENOVATION_SHORT = {
    "evro": "evro", "orta": "o'rta", "qora": "qora", "muallim": "muallim"
}


def format_price(amount: float, currency: str) -> str:
    """
    USD:  47500      → 47.500$
    So'm: 350_000_000 → 350 mln so'm
          1_200_000_000 → 1.2 mlrd so'm
    """
    if currency == "usd":
        s = f"{int(amount):,}".replace(",", ".")
        return f"{s}$"
    else:
        n = int(amount)
        if n >= 1_000_000_000:
            mlrd = n // 1_000_000_000
            qolgan_mln = (n % 1_000_000_000) // 1_000_000
            if qolgan_mln:
                return f"{mlrd} mlrd {qolgan_mln} mln so'm"
            return f"{mlrd} mlrd so'm"
        else:
            mln = n // 1_000_000
            qolgan = (n % 1_000_000) // 1_000
            if qolgan:
                return f"{mln} mln {qolgan} ming so'm"
            return f"{mln} mln so'm"


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
    """Qisqa qator: '🏢 Korzinka · 2x · 3/9 · 68m² · evro · 72.000$'"""
    parts = [PROPERTY_LABELS.get(lst.get("property_type", ""), "🏠")]
    if lst.get("landmark"):
        parts[0] += f" {lst['landmark']}"
    if lst.get("xonalar"):
        parts.append(f"{lst['xonalar']}x")
    if lst.get("floor") and lst.get("total_floors"):
        parts.append(f"{lst['floor']}/{lst['total_floors']}")
    if lst.get("area"):
        parts.append(f"{int(lst['area'])}m²")
    if lst.get("renovation"):
        parts.append(RENOVATION_SHORT.get(lst["renovation"], lst["renovation"]))
    if lst.get("price_display"):
        parts.append(f"*{lst['price_display']}*")
    return " · ".join(parts)


def listing_full_card(lst: dict, loc: dict | None = None) -> str:
    """Format 1 — to'liq karta matni."""
    ptype  = PROPERTY_LABELS.get(lst.get("property_type", ""), "🏠")
    dtype  = DOM_TYPE_LABELS.get(lst.get("dom_type", ""), "")
    renov  = RENOVATION_LABELS.get(lst.get("renovation", ""), "")

    lines = [f"{ptype}" + (f" · {dtype}" if dtype else "")]
    if loc:
        loc_str = f"{loc['viloyat']}, {loc['tuman']}, {loc['mahalla']}"
        if lst.get("landmark"):
            loc_str += f" · _{lst['landmark']}_"
        lines.append(f"📍 {loc_str}")

    details = []
    if lst.get("xonalar"):   details.append(f"🛏 {lst['xonalar']} xona")
    if lst.get("floor"):     details.append(f"🏗 {lst['floor']}/{lst['total_floors']} qavat")
    if lst.get("area"):      details.append(f"📐 {int(lst['area'])} m²")
    if details:
        lines.append("  ".join(details))
    if renov:
        lines.append(f"🔨 {renov}")
    if lst.get("price_display"):
        lines.append(f"💰 *{lst['price_display']}*")

    phone = lst.get("phone", "")
    if phone:
        masked = mask_phone(phone)
        lines.append(f"📞 {masked}")

    return "\n".join(lines)


def mask_phone(phone: str) -> str:
    """'+998901234567' → '+998 90 *** ** 67'"""
    p = phone.replace("+", "").replace(" ", "")
    if len(p) >= 12:
        return f"+{p[:3]} {p[3:5]} *** ** {p[-2:]}"
    return phone


def make_progress(step: int, total: int) -> str:
    filled = "▓" * step
    empty  = "░" * (total - step)
    return f"`{filled}{empty}` Qadam {step}/{total}"
