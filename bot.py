"""
Uy Bot MVP — Toshkent ko'chmas mulk Telegram boti
"""
import json
import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes,
)
from config import BOT_TOKEN
import database as db

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
#  STATES
# ══════════════════════════════════════════════════════════════════════════════
(
    MAIN,
    # Sotuvchi (seller)
    S_VIDEO, S_XONALAR, S_SOTIX, S_ETAJ, S_KVADRAT,
    S_NIMA_QOLADI, S_DOM_NOMERI,
    S_VILOYAT, S_TUMAN, S_MAHALLA_SEARCH, S_MAHALLA_PICK,
    S_LOC_FOUND,      # bazada topildi — tasdiqlash
    S_LOC_MANUAL,     # topilmadi — qo'lda joylashuv
    S_LOC_SAVE,       # yangi joylashuvni saqlash
    S_NARX, S_PHONE, S_CONFIRM,
    # Xaridor (buyer)
    B_VILOYAT, B_TUMAN, B_MAHALLA_SEARCH, B_MAHALLA_PICK, B_MAHALLA_DONE,
    B_XONALAR, B_SOTIX, B_DONE,
) = range(26)

# ══════════════════════════════════════════════════════════════════════════════
#  HELPER KEYBOARDS
# ══════════════════════════════════════════════════════════════════════════════

def main_kb():
    return ReplyKeyboardMarkup(
        [["🏠 Uy sotaman", "🔍 Uy qidiraman"], ["📋 E'lonlarim", "⚙️ Sozlamalarim"]],
        resize_keyboard=True,
    )


def cancel_kb():
    return ReplyKeyboardMarkup([["❌ Bekor qilish"]], resize_keyboard=True)


def list_kb(items: list, prefix: str, columns: int = 2, extra: list = None):
    """Generic inline keyboard from a list of strings."""
    rows = []
    row = []
    for i, item in enumerate(items):
        row.append(InlineKeyboardButton(item, callback_data=f"{prefix}{item}"))
        if len(row) == columns:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if extra:
        for btn in extra:
            rows.append([btn])
    return InlineKeyboardMarkup(rows)


def xonalar_kb(multi=False):
    prefix = "bx_" if multi else "sx_"
    buttons = [
        [
            InlineKeyboardButton("1 xona", callback_data=f"{prefix}1"),
            InlineKeyboardButton("2 xona", callback_data=f"{prefix}2"),
            InlineKeyboardButton("3 xona", callback_data=f"{prefix}3"),
        ],
        [
            InlineKeyboardButton("4 xona", callback_data=f"{prefix}4"),
            InlineKeyboardButton("5+ xona", callback_data=f"{prefix}5"),
        ],
    ]
    if multi:
        buttons.append([InlineKeyboardButton("✅ Hammasi (farq yuq)", callback_data="bx_hammasi")])
    return InlineKeyboardMarkup(buttons)


def sotix_kb(multi=False):
    prefix = "bs_" if multi else "ss_"
    buttons = [
        [InlineKeyboardButton("✨ Yangi ta'mir", callback_data=f"{prefix}yangi")],
        [InlineKeyboardButton("🔧 Eski ta'mir",  callback_data=f"{prefix}eski")],
        [InlineKeyboardButton("🧱 Ta'mirsiz",    callback_data=f"{prefix}tamsiz")],
    ]
    if multi:
        buttons.append([InlineKeyboardButton("✅ Hammasi (farq yuq)", callback_data="bs_hammasi")])
    return InlineKeyboardMarkup(buttons)


SOTIX_LABEL = {"yangi": "✨ Yangi ta'mir", "eski": "🔧 Eski ta'mir", "tamsiz": "🧱 Ta'mirsiz"}

# ══════════════════════════════════════════════════════════════════════════════
#  FORMATTING
# ══════════════════════════════════════════════════════════════════════════════

def format_listing(listing: dict, loc: dict) -> str:
    sotix = SOTIX_LABEL.get(listing["sotix"], listing["sotix"])
    lines = [
        f"🏠 *{listing['xonalar']} xonali kvartira*",
        f"📍 {loc['viloyat']}, {loc['tuman']}, {loc['mahalla']}",
        f"🏢 Dom: {listing.get('dom_nomeri') or '—'}",
        f"📐 Maydon: {listing['kvadrat']}м²",
        f"🏗 Etaj: {listing['etaj']}/{listing['etajlilik']}",
        f"🔨 Holati: {sotix}",
    ]
    if listing.get("nima_qoladi"):
        lines.append(f"🛋 Qoladi: {listing['nima_qoladi']}")
    lines += [
        f"💰 Narx: {listing['narx']}",
        f"📞 Tel: {listing['seller_phone']}",
    ]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
#  /start  &  MAIN MENU
# ══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Assalomu alaykum! 👋\n\n"
        "Bu bot orqali Toshkentda *uy sotish yoki sotib olish* juda oson.\n\n"
        "Nima qilmoqchisiz?",
        reply_markup=main_kb(),
        parse_mode="Markdown",
    )
    return MAIN


async def main_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🏠 Uy sotaman":
        await update.message.reply_text(
            "Uyingizning *3 daqiqagacha* bo'lgan video obzorini yuboring 📹\n\n"
            "_(Video telefon kamerasi bilan oling, ichkarini ko'rsating)_",
            reply_markup=cancel_kb(),
            parse_mode="Markdown",
        )
        ctx.user_data.clear()
        return S_VIDEO

    elif text == "🔍 Uy qidiraman":
        ctx.user_data.clear()
        ctx.user_data["b_locs"] = []
        viloyatlar = db.get_viloyatlar()
        if not viloyatlar:
            await update.message.reply_text(
                "Hozircha ma'lumotlar bazasida hududlar yo'q. Admin bilan bog'laning."
            )
            return MAIN
        await update.message.reply_text(
            "Qaysi *viloyatda* uy qidiryapsiz?",
            reply_markup=list_kb(viloyatlar, "bv_", columns=2),
            parse_mode="Markdown",
        )
        return B_VILOYAT

    elif text == "📋 E'lonlarim":
        return await show_my_listings(update, ctx)

    elif text == "⚙️ Sozlamalarim":
        return await show_settings(update, ctx)

    return MAIN


# ══════════════════════════════════════════════════════════════════════════════
#  SELLER FLOW
# ══════════════════════════════════════════════════════════════════════════════

async def seller_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Bekor qilish":
        return await cancel(update, ctx)

    video = update.message.video
    if not video:
        await update.message.reply_text("❗ Iltimos, *video* yuboring (rasm emas).", parse_mode="Markdown")
        return S_VIDEO

    if video.duration and video.duration > 180:
        await update.message.reply_text("❗ Video 3 daqiqadan uzun. Iltimos, qisqaroq video yuboring.")
        return S_VIDEO

    ctx.user_data["video_file_id"] = video.file_id
    await update.message.reply_text(
        "Xonalar sonini tanlang:", reply_markup=xonalar_kb()
    )
    return S_XONALAR


async def seller_xonalar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    xona = q.data.replace("sx_", "")
    ctx.user_data["xonalar"] = int(xona) if xona != "5" else 5
    await q.edit_message_text("Ta'mir holatini tanlang:", reply_markup=sotix_kb())
    return S_SOTIX


async def seller_sotix(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data["sotix"] = q.data.replace("ss_", "")
    await q.edit_message_text(
        "Necha-necha etaj?\n\n"
        "Masalan: *3/9* (3-etaj, 9 qavatli uy)\n"
        "Raqamlarni '/' bilan yozing:",
        parse_mode="Markdown",
    )
    return S_ETAJ


async def seller_etaj(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Bekor qilish":
        return await cancel(update, ctx)
    try:
        parts = update.message.text.strip().split("/")
        etaj, etajlilik = int(parts[0]), int(parts[1])
        if etaj > etajlilik or etaj < 1:
            raise ValueError
    except Exception:
        await update.message.reply_text("❗ Noto'g'ri format. Masalan: *3/9*", parse_mode="Markdown")
        return S_ETAJ

    ctx.user_data["etaj"] = etaj
    ctx.user_data["etajlilik"] = etajlilik
    await update.message.reply_text("Uyning umumiy maydoni (м²)? Faqat raqam yozing:\nMasalan: *65*")
    return S_KVADRAT


async def seller_kvadrat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Bekor qilish":
        return await cancel(update, ctx)
    try:
        kv = float(update.message.text.strip().replace(",", "."))
        if kv <= 0 or kv > 2000:
            raise ValueError
    except Exception:
        await update.message.reply_text("❗ Noto'g'ri. Faqat raqam yozing (masalan: 65)")
        return S_KVADRAT

    ctx.user_data["kvadrat"] = kv
    await update.message.reply_text(
        "Uydan *nima qoladi*? (mebel, texnika...)\n\n"
        "Yoki «Hech narsa» deb yozing:",
        parse_mode="Markdown",
    )
    return S_NIMA_QOLADI


async def seller_nima_qoladi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Bekor qilish":
        return await cancel(update, ctx)
    ctx.user_data["nima_qoladi"] = update.message.text.strip()
    # Avval viloyat/tuman/mahalla, keyin dom nomeri
    viloyatlar = db.get_viloyatlar()
    await update.message.reply_text(
        "Viloyatni tanlang:", reply_markup=list_kb(viloyatlar, "sv_", columns=2)
    )
    return S_VILOYAT


async def seller_dom_nomeri(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Mahalla tanlangandan keyin dom nomeri so'raladi."""
    if update.message.text == "❌ Bekor qilish":
        return await cancel(update, ctx)
    ctx.user_data["dom_nomeri"] = update.message.text.strip()

    # Bazadan darhol qidirish
    loc_id = ctx.user_data.get("location_id")
    dom = ctx.user_data["dom_nomeri"]
    buildings = db.find_building(loc_id, dom) if (loc_id and dom != "—") else []

    if buildings:
        ctx.user_data["_buildings"] = buildings
        if len(buildings) == 1:
            b = buildings[0]
            await update.message.reply_text(
                f"✅ Bazada topildi: *{b['dom_nomeri']}*\n\nJoylashuvni tekshiring 👇",
                parse_mode="Markdown",
            )
            await update.message.reply_location(latitude=b["lat"], longitude=b["lon"])
            await update.message.reply_text(
                "Shu to'g'ri joymiZ?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Ha, to'g'ri", callback_data=f"locok_{b['id']}"),
                     InlineKeyboardButton("❌ Yo'q, boshqa", callback_data="loc_manual")],
                ]),
            )
        else:
            rows = [
                [InlineKeyboardButton(f"📍 {b['dom_nomeri']}", callback_data=f"locok_{b['id']}")]
                for b in buildings
            ]
            rows.append([InlineKeyboardButton("✏️ O'zim kiritaman", callback_data="loc_manual")])
            await update.message.reply_text(
                f"*{len(buildings)} ta mos bino topildi.* Qaysi biri?",
                reply_markup=InlineKeyboardMarkup(rows),
                parse_mode="Markdown",
            )
        return S_LOC_FOUND
    else:
        await update.message.reply_text(
            f"❗ *«{dom}»* bazamizda topilmadi.\n\n"
            "📍 Joylashuvni qo'lda yuboring:\n"
            "Telegramda 📎 → *Location* tugmasini bosing,\n"
            "xaritada domni toping va yuboring.",
            reply_markup=ReplyKeyboardMarkup(
                [[{"text": "📍 Joylashuvni ulashish", "request_location": True}],
                 ["❌ Bekor qilish"]],
                resize_keyboard=True,
            ),
            parse_mode="Markdown",
        )
        return S_LOC_MANUAL


async def seller_viloyat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    viloyat = q.data.replace("sv_", "")
    ctx.user_data["viloyat"] = viloyat
    tumanlar = db.get_tumanlar(viloyat)
    await q.edit_message_text(
        f"*{viloyat}* — Tumanni tanlang:",
        reply_markup=list_kb(tumanlar, "st_", columns=2),
        parse_mode="Markdown",
    )
    return S_TUMAN


async def seller_tuman(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tuman = q.data.replace("st_", "")
    ctx.user_data["tuman"] = tuman
    await q.edit_message_text(
        f"*{tuman}* — Mahallani qidiring:\n\n"
        "Mahalla nomini yozing (yoki boshlang'ich harflarini):",
        parse_mode="Markdown",
    )
    return S_MAHALLA_SEARCH


async def seller_mahalla_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Bekor qilish":
        return await cancel(update, ctx)
    query = update.message.text.strip()
    results = db.search_mahallalar(ctx.user_data["viloyat"], ctx.user_data["tuman"], query)
    if not results:
        await update.message.reply_text("❗ Topilmadi. Boshqacha yozib ko'ring:")
        return S_MAHALLA_SEARCH

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(r["mahalla"], callback_data=f"sm_{r['id']}")]
        for r in results
    ])
    await update.message.reply_text("Mahallani tanlang:", reply_markup=kb)
    return S_MAHALLA_PICK


async def seller_mahalla_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    loc_id = int(q.data.replace("sm_", ""))
    ctx.user_data["location_id"] = loc_id
    await q.edit_message_text(
        "Dom raqami yoki nomi:\nMasalan: *Navruz ko'chasi 14* yoki *19-dom*\n\n"
        "Bilmasangiz «—» yozing:",
        parse_mode="Markdown",
    )
    return S_DOM_NOMERI


async def seller_loc_found(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Bazadan topilgan joylashuvni tasdiqlash yoki rad etish."""
    q = update.callback_query
    await q.answer()

    if q.data == "loc_manual":
        await q.edit_message_text(
            "📍 Joylashuvni qo'lda yuboring:\n"
            "Telegramda 📎 → *Location* tugmasini bosing.",
            parse_mode="Markdown",
        )
        await q.message.reply_text(
            "📍 Joylashuvni yuboring:",
            reply_markup=ReplyKeyboardMarkup(
                [[{"text": "📍 Joylashuvni ulashish", "request_location": True}],
                 ["❌ Bekor qilish"]],
                resize_keyboard=True,
            ),
        )
        return S_LOC_MANUAL

    # locok_{building_id}
    building_id = int(q.data.replace("locok_", ""))
    buildings = ctx.user_data.get("_buildings", [])
    chosen = next((b for b in buildings if b["id"] == building_id), None)

    if chosen:
        ctx.user_data["lat"] = chosen["lat"]
        ctx.user_data["lon"] = chosen["lon"]
        await q.edit_message_text("✅ Joylashuv tasdiqlandi!")
    else:
        await q.edit_message_text("✅ Saqlandi.")

    await q.message.reply_text(
        "Narxni yozing:\nMasalan: *85 000$* yoki *1 200 000 000 so'm*",
        parse_mode="Markdown",
    )
    return S_NARX


async def seller_loc_manual(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Sotuvchi qo'lda joylashuv yuboradi."""
    if update.message.text == "❌ Bekor qilish":
        return await cancel(update, ctx)

    loc = update.message.location
    if not loc:
        await update.message.reply_text(
            "❗ Joylashuv yuborilmadi. 📎 → *Location* tugmasini bosing.",
            parse_mode="Markdown",
        )
        return S_LOC_MANUAL

    ctx.user_data["lat"] = loc.latitude
    ctx.user_data["lon"] = loc.longitude

    # Yangi binoni bazaga saqlashni taklif qil
    dom = ctx.user_data.get("dom_nomeri", "")
    await update.message.reply_text(
        f"✅ Joylashuv qabul qilindi!\n\n"
        f"*{dom}* ni bazaga saqlasinmi?\n"
        "(Keyingi sotuvchilar uchun avtomatik topiladi)",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Ha, saqla", callback_data="locsave_yes"),
             InlineKeyboardButton("➡️ Yo'q, davom et", callback_data="locsave_no")],
        ]),
        parse_mode="Markdown",
    )
    return S_LOC_SAVE


async def seller_loc_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Yangi joylashuvni bazaga saqlash yoki o'tkazib yuborish."""
    q = update.callback_query
    await q.answer()

    if q.data == "locsave_yes":
        dom = ctx.user_data.get("dom_nomeri", "")
        loc_id = ctx.user_data.get("location_id")
        lat = ctx.user_data.get("lat")
        lon = ctx.user_data.get("lon")
        if loc_id and lat and lon:
            db.add_building(loc_id, dom, lat, lon)
        await q.edit_message_text("✅ Saqlandi! Rahmat.")
    else:
        await q.edit_message_text("Davom etamiz.")

    await q.message.reply_text(
        "Narxni yozing:\nMasalan: *85 000$* yoki *1 200 000 000 so'm*",
        parse_mode="Markdown",
    )
    return S_NARX


async def seller_narx(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Bekor qilish":
        return await cancel(update, ctx)
    ctx.user_data["narx"] = update.message.text.strip()
    await update.message.reply_text(
        "Telefon raqamingizni yuboring 📞",
        reply_markup=ReplyKeyboardMarkup(
            [[{"text": "📱 Raqamni ulashish", "request_contact": True}], ["❌ Bekor qilish"]],
            resize_keyboard=True,
        ),
    )
    return S_PHONE


async def seller_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text and update.message.text == "❌ Bekor qilish":
        return await cancel(update, ctx)

    if update.message.contact:
        phone = update.message.contact.phone_number
    elif update.message.text:
        phone = update.message.text.strip()
    else:
        await update.message.reply_text("❗ Telefon raqamini yuboring.")
        return S_PHONE

    ctx.user_data["seller_phone"] = phone
    loc = db.get_location(ctx.user_data["location_id"])
    sotix = SOTIX_LABEL.get(ctx.user_data["sotix"], ctx.user_data["sotix"])

    summary = (
        f"📋 *E'lon ma'lumotlari:*\n\n"
        f"📍 {loc['viloyat']}, {loc['tuman']}, {loc['mahalla']}\n"
        f"🏢 Dom: {ctx.user_data.get('dom_nomeri') or '—'}\n"
        f"🏠 Xonalar: {ctx.user_data['xonalar']}\n"
        f"🔨 Holati: {sotix}\n"
        f"🏗 Etaj: {ctx.user_data['etaj']}/{ctx.user_data['etajlilik']}\n"
        f"📐 Maydon: {ctx.user_data['kvadrat']}м²\n"
        f"🛋 Qoladi: {ctx.user_data.get('nima_qoladi') or '—'}\n"
        f"💰 Narx: {ctx.user_data['narx']}\n"
        f"📞 Tel: {phone}\n\n"
        f"Joylashtirilsinmi?"
    )
    await update.message.reply_text(
        summary,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Ha, joylashtir", callback_data="confirm_yes"),
             InlineKeyboardButton("❌ Yo'q", callback_data="confirm_no")],
        ]),
        parse_mode="Markdown",
    )
    return S_CONFIRM


async def seller_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "confirm_no":
        await q.edit_message_text("Bekor qilindi.")
        await q.message.reply_text("Bosh menyu:", reply_markup=main_kb())
        return MAIN

    user = q.from_user
    data = {**ctx.user_data, "seller_id": user.id, "seller_username": user.username}
    listing_id = db.add_listing(data)

    await q.edit_message_text(f"✅ E'lon #{listing_id} joylashtirildi!\n\nRahmat!")
    await q.message.reply_text("Bosh menyu:", reply_markup=main_kb())

    # Notify matching buyers
    listing = db.get_listing(listing_id)
    buyers = db.find_matching_buyers(listing)
    loc = db.get_location(listing["location_id"])
    caption = format_listing(listing, loc)

    for buyer_id in buyers:
        try:
            await ctx.bot.send_video(
                chat_id=buyer_id,
                video=listing["video_file_id"],
                caption=f"🔔 *Siz qidirayotgan hududda yangi e'lon!*\n\n{caption}",
                parse_mode="Markdown",
            )
            db.mark_notified(buyer_id, listing_id)
        except Exception as e:
            logger.warning(f"Buyer {buyer_id} ga xabar yuborilamdi: {e}")

    ctx.user_data.clear()
    return MAIN


# ══════════════════════════════════════════════════════════════════════════════
#  BUYER FLOW
# ══════════════════════════════════════════════════════════════════════════════

async def buyer_viloyat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    viloyat = q.data.replace("bv_", "")
    ctx.user_data["b_viloyat"] = viloyat
    tumanlar = db.get_tumanlar(viloyat)
    await q.edit_message_text(
        f"*{viloyat}* — Tumanni tanlang:",
        reply_markup=list_kb(tumanlar, "bt_", columns=2),
        parse_mode="Markdown",
    )
    return B_TUMAN


async def buyer_tuman(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tuman = q.data.replace("bt_", "")
    ctx.user_data["b_tuman"] = tuman
    await q.edit_message_text(
        f"*{tuman}* — Mahallani qidiring:\n\nMahalla nomini yozing:",
        parse_mode="Markdown",
    )
    return B_MAHALLA_SEARCH


async def buyer_mahalla_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Bekor qilish":
        return await cancel(update, ctx)

    query = update.message.text.strip()
    results = db.search_mahallalar(ctx.user_data["b_viloyat"], ctx.user_data["b_tuman"], query)
    if not results:
        await update.message.reply_text("❗ Topilmadi. Boshqacha yozib ko'ring:")
        return B_MAHALLA_SEARCH

    kb_rows = [
        [InlineKeyboardButton(r["mahalla"], callback_data=f"bm_{r['id']}")]
        for r in results
    ]
    kb_rows.append([InlineKeyboardButton("✅ Tanlashni tugatdim", callback_data="bm_done")])
    await update.message.reply_text(
        "Mahallani tanlang (bir nechta tanlash mumkin):\n"
        f"_(Hozir tanlangan: {len(ctx.user_data.get('b_locs', []))} ta)_",
        reply_markup=InlineKeyboardMarkup(kb_rows),
        parse_mode="Markdown",
    )
    return B_MAHALLA_PICK


async def buyer_mahalla_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "bm_done":
        if not ctx.user_data.get("b_locs"):
            await q.edit_message_text(
                "Hech qaysi mahalla tanlanmadi. Kamida bitta tanlang yoki 'Barcha mahallalar' uchun /start dan boshqatdan sozlang."
            )
            return B_MAHALLA_PICK

        await q.edit_message_text(
            f"*{len(ctx.user_data['b_locs'])} ta mahalla* tanlandi ✅\n\nXonalar soni?",
            reply_markup=xonalar_kb(multi=True),
            parse_mode="Markdown",
        )
        return B_XONALAR

    loc_id = int(q.data.replace("bm_", ""))
    if "b_locs" not in ctx.user_data:
        ctx.user_data["b_locs"] = []

    if loc_id in ctx.user_data["b_locs"]:
        ctx.user_data["b_locs"].remove(loc_id)
        status = "olib tashlandi"
    else:
        ctx.user_data["b_locs"].append(loc_id)
        status = "qo'shildi"

    await q.answer(f"✅ {status}")
    await q.edit_message_text(
        f"Mahalla {status}.\nJami tanlangan: *{len(ctx.user_data['b_locs'])}* ta\n\n"
        "Yana mahalla qidiring yoki «Tanlashni tugatdim» bosing.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Tanlashni tugatdim", callback_data="bm_done")]
        ]),
        parse_mode="Markdown",
    )
    return B_MAHALLA_PICK


async def buyer_xonalar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    val = q.data.replace("bx_", "")
    if val == "hammasi":
        ctx.user_data["b_xonalar"] = "hammasi"
    else:
        existing = ctx.user_data.get("b_xonalar_list", [])
        if val in existing:
            existing.remove(val)
        else:
            existing.append(val)
        ctx.user_data["b_xonalar_list"] = existing
        ctx.user_data["b_xonalar"] = json.dumps(existing) if existing else "hammasi"

    await q.edit_message_text(
        f"Xonalar: *{ctx.user_data['b_xonalar']}* ✅\n\nTa'mir holati?",
        reply_markup=sotix_kb(multi=True),
        parse_mode="Markdown",
    )
    return B_SOTIX


async def buyer_sotix(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    val = q.data.replace("bs_", "")
    if val == "hammasi":
        ctx.user_data["b_sotix"] = "hammasi"
    else:
        ctx.user_data["b_sotix"] = val  # MVP: bitta tanlash

    user = q.from_user
    locs = ctx.user_data.get("b_locs", [])
    xonalar = ctx.user_data.get("b_xonalar", "hammasi")
    sotix = ctx.user_data.get("b_sotix", "hammasi")

    db.save_buyer_prefs(user.id, user.username, locs, xonalar, sotix)

    await q.edit_message_text(
        "✅ *Sozlamalar saqlandi!*\n\n"
        f"📍 Mahallalar: {len(locs)} ta\n"
        f"🏠 Xonalar: {xonalar}\n"
        f"🔨 Ta'mir: {sotix}\n\n"
        "Yangi e'lonlar chiqishi bilan sizga xabar beramiz 🔔",
        parse_mode="Markdown",
    )
    await q.message.reply_text("Bosh menyu:", reply_markup=main_kb())
    ctx.user_data.clear()
    return MAIN


# ══════════════════════════════════════════════════════════════════════════════
#  MY LISTINGS  &  SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

async def show_my_listings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    listings = db.get_seller_listings(user_id)
    if not listings:
        await update.message.reply_text(
            "Sizda hozircha e'lonlar yo'q.\n\nUy sotish uchun «🏠 Uy sotaman» tugmasini bosing.",
            reply_markup=main_kb(),
        )
        return MAIN

    for lst in listings[:5]:  # max 5 ta
        loc = db.get_location(lst["location_id"])
        caption = format_listing(lst, loc)
        status_icon = "✅" if lst["status"] == "active" else "❌"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{status_icon} Yopish #{lst['id']}", callback_data=f"close_{lst['id']}")]
        ]) if lst["status"] == "active" else None
        try:
            await update.message.reply_video(
                video=lst["video_file_id"],
                caption=caption,
                reply_markup=kb,
                parse_mode="Markdown",
            )
        except Exception:
            await update.message.reply_text(caption + f"\n_(Video yuklanmadi)_", parse_mode="Markdown")

    await update.message.reply_text("Bosh menyu:", reply_markup=main_kb())
    return MAIN


async def close_listing_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    listing_id = int(q.data.replace("close_", ""))
    db.deactivate_listing(listing_id, q.from_user.id)
    await q.edit_message_reply_markup(reply_markup=None)
    await q.message.reply_text(f"✅ E'lon #{listing_id} yopildi.")


async def show_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    prefs = db.get_buyer_prefs(update.effective_user.id)
    if prefs:
        text = (
            f"⚙️ *Sizning sozlamalaringiz:*\n\n"
            f"📍 Mahallalar: {len(prefs['location_ids'])} ta\n"
            f"🏠 Xonalar: {prefs['xonalar']}\n"
            f"🔨 Ta'mir: {prefs['sotix']}\n\n"
            "Qayta sozlash uchun «🔍 Uy qidiraman» tugmasini bosing."
        )
    else:
        text = "⚙️ Siz hali sozlamalar qilmagansiz.\n\n«🔍 Uy qidiraman» tugmasini bosing."
    await update.message.reply_text(text, reply_markup=main_kb(), parse_mode="Markdown")
    return MAIN


# ══════════════════════════════════════════════════════════════════════════════
#  CANCEL
# ══════════════════════════════════════════════════════════════════════════════

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("Bekor qilindi.", reply_markup=main_kb())
    return MAIN


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    db.init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    cancel_filter = filters.Regex("^❌ Bekor qilish$")

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu)],
        states={
            MAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu)],
            # Seller
            S_VIDEO:         [MessageHandler(filters.VIDEO | filters.TEXT, seller_video)],
            S_XONALAR:       [CallbackQueryHandler(seller_xonalar, pattern="^sx_")],
            S_SOTIX:         [CallbackQueryHandler(seller_sotix, pattern="^ss_")],
            S_ETAJ:          [MessageHandler(filters.TEXT, seller_etaj)],
            S_KVADRAT:       [MessageHandler(filters.TEXT, seller_kvadrat)],
            S_NIMA_QOLADI:   [MessageHandler(filters.TEXT, seller_nima_qoladi)],
            S_VILOYAT:       [CallbackQueryHandler(seller_viloyat, pattern="^sv_")],
            S_TUMAN:         [CallbackQueryHandler(seller_tuman, pattern="^st_")],
            S_MAHALLA_SEARCH:[MessageHandler(filters.TEXT, seller_mahalla_search)],
            S_MAHALLA_PICK:  [CallbackQueryHandler(seller_mahalla_pick, pattern="^sm_")],
            S_DOM_NOMERI:    [MessageHandler(filters.TEXT, seller_dom_nomeri)],
            S_LOC_FOUND:     [CallbackQueryHandler(seller_loc_found, pattern="^(locok_|loc_manual)")],
            S_LOC_MANUAL:    [MessageHandler(filters.LOCATION | filters.TEXT, seller_loc_manual)],
            S_LOC_SAVE:      [CallbackQueryHandler(seller_loc_save, pattern="^locsave_")],
            S_NARX:          [MessageHandler(filters.TEXT, seller_narx)],
            S_PHONE:         [MessageHandler(filters.CONTACT | filters.TEXT, seller_phone)],
            S_CONFIRM:       [CallbackQueryHandler(seller_confirm, pattern="^confirm_")],
            # Buyer
            B_VILOYAT:       [CallbackQueryHandler(buyer_viloyat, pattern="^bv_")],
            B_TUMAN:         [CallbackQueryHandler(buyer_tuman, pattern="^bt_")],
            B_MAHALLA_SEARCH:[MessageHandler(filters.TEXT, buyer_mahalla_search)],
            B_MAHALLA_PICK:  [CallbackQueryHandler(buyer_mahalla_pick, pattern="^bm_")],
            B_XONALAR:       [CallbackQueryHandler(buyer_xonalar, pattern="^bx_")],
            B_SOTIX:         [CallbackQueryHandler(buyer_sotix, pattern="^bs_")],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(cancel_filter, cancel),
        ],
        per_message=False,
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(close_listing_cb, pattern="^close_"))

    logger.info("Bot ishga tushdi...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
