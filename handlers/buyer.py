from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from handlers.states import BuyerStates
from keyboards.inline import (
    transaction_kb, buyer_transaction_kb,
    property_type_kb, viloyat_kb, tuman_kb, mahalla_kb,
    xonalar_kb, dom_type_filter_kb, renovation_filter_kb,
    results_nav_kb, contact_kb, kb,
)
from keyboards.reply import cancel_kb, main_menu_kb, remove_kb
import database as db
from utils.helpers import (
    listing_full_card, listing_short_line,
    format_price, mask_phone,
)

router = Router()

FILTER_KEY_TTL = 300   # seconds (not used yet, placeholder)


# ── Entry point ──────────────────────────────────────────────────
@router.message(F.text.in_({"🔍 Uy qidirish", "🔍 Qidirish"}))
async def start_search(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer(
        "🔍 <b>Qidiruv</b>\n\nNimani qidiryapsiz?",
        reply_markup=buyer_transaction_kb(),
        parse_mode="HTML",
    )
    await state.set_state(BuyerStates.transaction)


@router.callback_query(BuyerStates.transaction, F.data.startswith("trx:"))
async def buyer_transaction(cb: CallbackQuery, state: FSMContext):
    trx = cb.data.split(":")[1]
    await state.update_data(transaction_type=trx)
    await cb.message.edit_text(
        "🏠 Mulk turini tanlang:",
        reply_markup=property_type_kb("bs"),
    )
    await state.set_state(BuyerStates.property_type)
    await cb.answer()


# ── Property type ────────────────────────────────────────────────
@router.callback_query(BuyerStates.property_type, F.data.startswith("bs:"))
async def buyer_property_type(cb: CallbackQuery, state: FSMContext):
    pt = cb.data.split(":")[1]
    await state.update_data(property_type=pt)
    viloyatlar = await db.get_viloyatlar()
    await cb.message.edit_text(
        "📍 Viloyatni tanlang:",
        reply_markup=viloyat_kb(viloyatlar, "bv"),
    )
    await state.set_state(BuyerStates.viloyat)
    await cb.answer()




@router.callback_query(BuyerStates.location_choice, F.data == "bc:cancel")
async def buyer_cancel_cb(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.get_user(cb.from_user.id)
    role = user.get("role", "buyer") if user else "buyer"
    await cb.message.edit_text("Bekor qilindi.")
    await cb.message.answer("Asosiy menyu 👇", reply_markup=main_menu_kb(role))
    await cb.answer()


# ── Viloyat ──────────────────────────────────────────────────────
@router.callback_query(BuyerStates.viloyat, F.data.startswith("bv:"))
async def buyer_viloyat(cb: CallbackQuery, state: FSMContext):
    action = cb.data.split(":")[1]

    # Butun O'zbekiston
    if action == "__all__":
        await state.update_data(location_id=None, viloyat=None)
        await _ask_xonalar(cb.message, state, edit=True)
        await cb.answer()
        return

    viloyat = action
    await state.update_data(viloyat=viloyat)
    tumanlar = await db.get_tumanlar(viloyat)
    await cb.message.edit_text(
        f"📍 <b>{viloyat}</b>\n\nTumanni tanlang:",
        reply_markup=tuman_kb(tumanlar, "bt"),
        parse_mode="HTML",
    )
    await state.set_state(BuyerStates.tuman)
    await cb.answer()


# ── Tuman ────────────────────────────────────────────────────────
@router.callback_query(BuyerStates.tuman, F.data.startswith("bt:"))
async def buyer_tuman(cb: CallbackQuery, state: FSMContext):
    action = cb.data.split(":")[1]
    if action == "back":
        viloyatlar = await db.get_viloyatlar()
        await cb.message.edit_text(
            "🗺 Viloyatni tanlang:",
            reply_markup=viloyat_kb(viloyatlar, "bv"),
        )
        await state.set_state(BuyerStates.viloyat)
        await cb.answer()
        return

    tuman = action
    data = await state.get_data()
    await state.update_data(tuman=tuman)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await cb.message.edit_text(
        f"📍 <b>{tuman}</b>\n\nQanday qidirasiz?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏘 Butun tuman bo'ylab", callback_data="bscope:tuman")],
            [InlineKeyboardButton(text="📍 Mahalla tanlash", callback_data="bscope:mahalla")],
        ]),
        parse_mode="HTML",
    )
    await state.set_state(BuyerStates.tuman)
    await cb.answer()


@router.callback_query(BuyerStates.tuman, F.data.startswith("bscope:"))
async def buyer_scope(cb: CallbackQuery, state: FSMContext):
    scope = cb.data.split(":")[1]
    data = await state.get_data()
    if scope == "tuman":
        await state.update_data(location_id=None, scope="tuman")
        from keyboards.inline import property_type_kb
        await cb.message.edit_text(
            f"🏘 <b>Butun {data['tuman']} bo'ylab qidiramiz</b>\n\nMulk turini tanlang:",
            reply_markup=property_type_kb("bpt"),
            parse_mode="HTML",
        )
        from handlers.states import BuyerStates as BS
        await state.set_state(BS.property_type)
    else:
        await _show_mahallalar_buyer(cb.message, state, data["viloyat"], data["tuman"], offset=0, edit=True)
        from handlers.states import BuyerStates as BS
        await state.set_state(BS.mahalla_page)
    await cb.answer()


# ── Mahalla pagination ───────────────────────────────────────────
async def _show_mahallalar_buyer(msg, state, viloyat, tuman, offset=0, query="", edit=False):
    PER_PAGE = 8
    mahallalar = await db.search_mahallalar(viloyat, tuman, query, PER_PAGE, offset)
    total      = await db.count_mahallalar(viloyat, tuman, query)

    text = (
        f"📍 <b>{viloyat} › {tuman}</b>\n"
        f"Mahallani tanlang ({total} ta):"
    )
    markup = mahalla_kb(mahallalar, total, offset, "bm")
    if edit:
        await msg.edit_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await msg.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(BuyerStates.mahalla_page, F.data.startswith("bm:"))
async def buyer_mahalla_page(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    action = parts[1]
    data = await state.get_data()

    if action == "pg":
        offset = int(parts[2])
        await _show_mahallalar_buyer(
            cb.message, state,
            data["viloyat"], data["tuman"], offset,
            data.get("mah_query", ""),
            edit=True,
        )
        await cb.answer()
        return

    if action == "search":
        await cb.message.edit_text(
            "🔍 Mahalla nomini yozing (masalan: Chilonzor, Yunusob...):",
        )
        await state.set_state(BuyerStates.mahalla_search)
        await cb.answer()
        return

    if action == "back":
        tumanlar = await db.get_tumanlar(data["viloyat"])
        await cb.message.edit_text(
            f"📍 <b>{data['viloyat']}</b>\n\nTumanni tanlang:",
            reply_markup=tuman_kb(tumanlar, "bt"),
            parse_mode="HTML",
        )
        await state.set_state(BuyerStates.tuman)
        await cb.answer()
        return

    if action == "pick":
        loc_id = int(parts[2])
        await state.update_data(location_id=loc_id)
        await _ask_xonalar(cb.message, state, edit=True)
        await cb.answer()
        return

    await cb.answer()


@router.message(BuyerStates.mahalla_search)
async def buyer_mah_search(msg: Message, state: FSMContext):
    query = msg.text.strip()
    await state.update_data(mah_query=query)
    data = await state.get_data()
    await _show_mahallalar_buyer(
        msg, state,
        data["viloyat"], data["tuman"], 0, query,
    )
    await state.set_state(BuyerStates.mahalla_page)


# ── Xonalar filter ───────────────────────────────────────────────
async def _ask_xonalar(msg, state, edit=False):
    text = "🛏 Nechta xona?"
    markup = xonalar_kb("bx", with_any=True)
    if edit:
        await msg.edit_text(text, reply_markup=markup)
    else:
        await msg.answer(text, reply_markup=markup)
    await state.set_state(BuyerStates.xonalar)


@router.callback_query(BuyerStates.xonalar, F.data.startswith("bx:"))
async def buyer_xonalar(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]   # "1","2","3","4","4+","any"
    xonalar = None if val == "any" else val
    await state.update_data(xonalar=xonalar)
    await cb.message.edit_text(
        "🏗 Turar-joy turi?",
        reply_markup=dom_type_filter_kb(),
    )
    await state.set_state(BuyerStates.dom_type)
    await cb.answer()


# ── Dom type filter ──────────────────────────────────────────────
@router.callback_query(BuyerStates.dom_type, F.data.startswith("fdt:"))
async def buyer_dom_type(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]
    dom_type = None if val == "any" else val
    await state.update_data(dom_type=dom_type)
    await cb.message.edit_text(
        "🔨 Ta'mirlash holati?",
        reply_markup=renovation_filter_kb(),
    )
    await state.set_state(BuyerStates.renovation)
    await cb.answer()


# ── Renovation filter → run search ──────────────────────────────
@router.callback_query(BuyerStates.renovation, F.data.startswith("fren:"))
async def buyer_renovation(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]
    renovation = None if val == "any" else val
    await state.update_data(renovation=renovation, results_offset=0)
    await _show_results(cb.message, state, offset=0, edit=True)
    await cb.answer()


# ── Results ──────────────────────────────────────────────────────
async def _show_results(msg, state, offset=0, edit=False):
    data = await state.get_data()
    PER_PAGE = 5

    results = await db.search_listings(
        property_type=data.get("property_type"),
        location_id=data.get("location_id"),
        xonalar=data.get("xonalar"),
        dom_type=data.get("dom_type"),
        renovation=data.get("renovation"),
        transaction_type=data.get("transaction_type"),
        tuman=data.get("tuman") if data.get("scope") == "tuman" else None,
        viloyat=data.get("viloyat") if data.get("scope") == "tuman" else None,
        limit=PER_PAGE,
        offset=offset,
    )

    if not results:
        text = (
            "😔 <b>Hech narsa topilmadi.</b>\n\n"
            "Filtrlarni o'zgartirib qaytadan qidiring yoki "
            "yangi e'lonlar uchun obuna bo'ling."
        )
        markup = kb(
            [("🔄 Qaytadan qidirish", "br:restart"), ("🔔 Obuna bo'lish", "br:subscribe")],
        )
        if edit:
            await msg.edit_text(text, reply_markup=markup, parse_mode="HTML")
        else:
            await msg.answer(text, reply_markup=markup, parse_mode="HTML")
        await state.set_state(BuyerStates.results)
        return

    # Build total count approximately
    total_results = await db.search_listings(
        property_type=data.get("property_type"),
        location_id=data.get("location_id"),
        xonalar=data.get("xonalar"),
        dom_type=data.get("dom_type"),
        renovation=data.get("renovation"),
        transaction_type=data.get("transaction_type"),
        tuman=data.get("tuman") if data.get("scope") == "tuman" else None,
        viloyat=data.get("viloyat") if data.get("scope") == "tuman" else None,
        limit=200, offset=0,
    )
    total = len(total_results)

    await state.update_data(
        result_ids=[r["id"] for r in results],
        results_offset=offset,
        results_total=total,
    )

    # Qisqa ro'yxat — raqamli inline tugmalar
    lines = [f"🔍 <b>{total} ta e'lon topildi</b> ({offset+1}–{min(offset+PER_PAGE, total)})\n"]
    buttons = []
    for i, lst in enumerate(results, start=offset + 1):
        short = listing_short_line(lst)
        lines.append(f"{i}. {short}")
        buttons.append([InlineKeyboardButton(
            text=f"{i}. {short}",
            callback_data=f"cl:open:{lst['id']}"
        )])

    filter_key = f"{data.get('property_type')}:{data.get('location_id')}"
    nav_row = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton(text="⬆️ Oldingi", callback_data="rn:prev"))
    if offset + PER_PAGE < total:
        nav_row.append(InlineKeyboardButton(text=f"⬇️ Ko'proq ({total - offset - PER_PAGE} ta)", callback_data="rn:more"))
    if nav_row:
        buttons.append(nav_row)
    buttons.append([
        InlineKeyboardButton(text="🔍 Yangi qidiruv", callback_data="rn:new"),
        InlineKeyboardButton(text="🔔 Obuna",         callback_data="rn:sub"),
    ])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)

    list_text = "\n".join(lines)
    if edit:
        try:
            await msg.edit_text(list_text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            await msg.answer(list_text, reply_markup=markup, parse_mode="HTML")
    else:
        await msg.answer(list_text, reply_markup=markup, parse_mode="HTML")

    await state.set_state(BuyerStates.results)

    # Save to search history
    await db.save_search(msg.chat.id if hasattr(msg, "chat") else msg.from_user.id, {
        "property_type": data.get("property_type"),
        "location_id":   data.get("location_id"),
        "xonalar":       data.get("xonalar"),
        "dom_type":      data.get("dom_type"),
        "renovation":    data.get("renovation"),
    })


# ── Results navigation ───────────────────────────────────────────
@router.callback_query(BuyerStates.results, F.data.startswith("rn:"))
async def results_nav(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    action = parts[1]

    if action == "more":
        data = await state.get_data()
        new_offset = data.get("results_offset", 0) + 5
        await _show_results(cb.message, state, offset=new_offset, edit=True)

    elif action == "prev":
        data = await state.get_data()
        new_offset = max(0, data.get("results_offset", 0) - 5)
        await _show_results(cb.message, state, offset=new_offset, edit=True)

    elif action == "new":
        await start_search(cb.message, state)

    elif action == "sub":
        data = await state.get_data()
        await db.save_subscription(cb.from_user.id, {
            "property_type": data.get("property_type"),
            "location_id":   data.get("location_id"),
            "xonalar":       data.get("xonalar"),
            "dom_type":      data.get("dom_type"),
            "renovation":    data.get("renovation"),
        })
        await cb.answer("✅ Obuna saqlandi! Yangi e'lonlar kelganda xabar beraman.", show_alert=True)
        return

    await cb.answer()


# ── User picks result by number ──────────────────────────────────
@router.message(BuyerStates.results)
async def buyer_pick_result(msg: Message, state: FSMContext):
    text = msg.text or ""

    if text == "❌ Bekor qilish":
        await state.clear()
        user = await db.get_user(msg.from_user.id)
        role = user.get("role", "buyer") if user else "buyer"
        await msg.answer("Bekor qilindi.", reply_markup=main_menu_kb(role))
        return

    data = await state.get_data()
    result_ids = data.get("result_ids", [])
    offset = data.get("results_offset", 0)

    try:
        idx = int(text.strip()) - 1 - offset   # 0-based index in current page
        if idx < 0 or idx >= len(result_ids):
            raise ValueError
    except ValueError:
        await msg.answer("Iltimos, ro'yxatdagi raqamni kiriting (masalan: 1, 2, 3...)")
        return

    listing_id = result_ids[idx]
    await show_listing_detail(msg, listing_id, msg.from_user.id)


async def show_listing_detail(msg: Message, listing_id: int, user_id: int):
    lst = await db.get_listing(listing_id)
    if not lst:
        await msg.answer("Bu e'lon topilmadi.")
        return

    if lst.get("status") == "deleted":
        await msg.answer(
            "🗑 <b>Bu e'lon endi mavjud emas.</b>\n\n"
            "E'lon sotildi va egasi tomonidan botdan olib tashlandi.",
            parse_mode="HTML",
        )
        return

    loc = await db.get_location(lst["location_id"]) if lst.get("location_id") else {}
    text = listing_full_card(lst, loc)

    await db.increment_views(listing_id)
    # Telefon 30 daqiqalik vaqtini boshlash
    await db.reveal_phone(user_id, listing_id)

    markup = contact_kb(listing_id)

    if lst.get("video_file_id"):
        await msg.answer_video(lst["video_file_id"], caption=text, reply_markup=markup, parse_mode="HTML")
    else:
        await msg.answer(text, reply_markup=markup, parse_mode="HTML")

    # Lokatsiya avtomatik
    lat = lst.get("lat")
    lon = lst.get("lon")
    if lat and lon:
        await msg.answer_location(latitude=float(lat), longitude=float(lon))


# ── Contact / favorite callbacks ────────────────────────────────
@router.callback_query(F.data.startswith("cl:"))
async def contact_action(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    action = parts[1]
    listing_id = int(parts[2])

    if action == "open":
        await show_listing_detail(cb.message, listing_id, cb.from_user.id)
        await cb.answer()
        return

    if action == "phone":
        lst = await db.get_listing(listing_id)
        if not lst:
            await cb.answer("E'lon topilmadi.", show_alert=True)
            return
        if lst.get("status") == "deleted":
            await cb.answer("Bu e'lon sotildi va egasi tomonidan olib tashlandi.", show_alert=True)
            return
        # 30 daqiqa chek
        active = await db.is_phone_active(cb.from_user.id, listing_id, minutes=30)
        if not active:
            await cb.answer("⏳ Raqam muddati tugagan. E'lonni qayta oching.", show_alert=True)
            return
        seller = await db.get_user(lst["seller_id"])
        phone = seller.get("phone", "—") if seller else "—"
        await db.increment_contacts(listing_id)
        await cb.answer(f"📞 {phone}", show_alert=True)
        await cb.message.answer(
            "⚠️ <b>Ehtiyot bo'ling!</b>\n\n"
            "🚫 Uyni <b>ko'rmasdan</b> hech qachon zalog yoki avans to'lamang\n"
            "🎭 Firibgarlar ko'pincha arzon narx va shoshiltirish orqali aldaydi\n"
            "📵 Bot orqali yuzaga kelgan firibgarlik uchun bot javobgar emas\n\n"
            "🔑 Faqat uyni borib ko'rganingizdan so'ng shartnoma tuzing!",
            parse_mode="HTML",
        )

    elif action == "fav":
        await db.add_favorite(cb.from_user.id, listing_id)
        await cb.answer("❤️ Sevimlilarga qo'shildi!", show_alert=False)

    elif action == "loc":
        lst = await db.get_listing(listing_id)
        if lst and lst.get("building_id"):
            bld = await db.get_building(lst["building_id"])
            if bld and bld.get("lat") and bld.get("lon"):
                await cb.message.answer_location(bld["lat"], bld["lon"])
                await cb.answer()
                return
        await cb.answer("Joylashuv ma'lumoti mavjud emas.", show_alert=True)

    elif action == "report":
        from keyboards.inline import report_reason_kb
        await cb.message.answer(
            "🚩 *Shikoyat sababi:*",
            reply_markup=report_reason_kb(listing_id),
            parse_mode="HTML",
        )
        await cb.answer()

    else:
        await cb.answer()


# ── Shikoyat sababi ──────────────────────────────────────────
@router.callback_query(F.data.startswith("rep:"))
async def report_reason_cb(cb: CallbackQuery, state: FSMContext):
    from config import ADMIN_IDS
    _, reason_key, lid = cb.data.split(":")
    listing_id = int(lid)

    REASONS = {
        "sotilgan": "✅ Sotilgan ekan",
        "soxta":    "👻 Mavjud emas / Soxta e'lon",
        "narx":     "💰 Narx noto'g'ri",
        "aloqa":    "📵 Aloqa yo'q / Javob bermaydi",
        "firib":    "🎭 Firibgarlik shubhasi",
    }

    # "Boshqa sabab" — erkin matn so'raymiz
    if reason_key == "boshqa":
        await state.update_data(report_listing_id=listing_id)
        await state.set_state(BuyerStates.report_text)
        await cb.message.edit_text(
            "✏️ <b>Shikoyat sababini yozing:</b>\n\n"
            "<i>Qisqacha tushuntiring — nima muammo bor?</i>",
            parse_mode="HTML",
        )
        await cb.answer()
        return

    reason_text = REASONS.get(reason_key, reason_key)

    result = await db.add_report(listing_id, cb.from_user.id, reason_text)

    if not result["added"]:
        await cb.answer("Siz bu e'longa allaqachon shikoyat qilgansiz.", show_alert=True)
        return

    total = result["total"]
    await cb.message.edit_text(
        f"✅ Shikoyatingiz qabul qilindi.\nSabab: {reason_text}\n\nRahmat, biz tergov qilamiz!"
    )
    await cb.answer()

    # Adminga xabar
    lst = await db.get_listing(listing_id)
    reporter = cb.from_user
    reporter_info = f"@{reporter.username}" if reporter.username else f"#{reporter.id}"

    alert_text = (
        f"🚩 <b>Shikoyat #{total}</b> | E'lon #{listing_id}\n"
        f"Sabab: {reason_text}\n"
        f"Kim: {reporter_info}\n"
    )
    if total >= 5:
        alert_text += "\n🔴 <b>E'lon avtomatik bloklandi!</b>"
    elif total == 3:
        alert_text += "\n⚠️ <b>3 ta shikoyat — tekshiring!</b>"

    if total >= 3:
        for admin_id in ADMIN_IDS:
            try:
                await cb.bot.send_message(admin_id, alert_text, parse_mode="HTML")
            except Exception:
                pass


async def _notify_report(bot, listing_id: int, reporter, reason_text: str, total: int):
    from config import ADMIN_IDS
    reporter_info = f"@{reporter.username}" if reporter.username else f"#{reporter.id}"
    alert_text = (
        f"🚩 <b>Shikoyat #{total}</b> | E'lon #{listing_id}\n"
        f"Sabab: {reason_text}\n"
        f"Kim: {reporter_info}\n"
    )
    if total >= 5:
        alert_text += "\n🔴 <b>E'lon avtomatik bloklandi!</b>"
    elif total == 3:
        alert_text += "\n⚠️ <b>3 ta shikoyat — tekshiring!</b>"
    if total >= 3:
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, alert_text, parse_mode="HTML")
            except Exception:
                pass


@router.message(BuyerStates.report_text)
async def report_custom_text(msg: Message, state: FSMContext):
    text = (msg.text or "").strip()
    if not text or len(text) < 3:
        await msg.answer("Iltimos, kamida 3 ta belgi kiriting.")
        return

    data = await state.get_data()
    listing_id = data.get("report_listing_id")
    if not listing_id:
        await state.clear()
        return

    reason_text = f"✏️ Boshqa: {text[:200]}"
    result = await db.add_report(listing_id, msg.from_user.id, reason_text)
    await state.clear()

    if not result["added"]:
        await msg.answer("Siz bu e'longa allaqachon shikoyat qilgansiz.")
        return

    await msg.answer(
        f"✅ <b>Shikoyatingiz qabul qilindi.</b>\n\nSabab: {reason_text}\n\nRahmat, biz ko'rib chiqamiz!",
        parse_mode="HTML",
    )
    await _notify_report(msg.bot, listing_id, msg.from_user, reason_text, result["total"])


# ── Restart search from results nav ─────────────────────────────
@router.callback_query(F.data == "br:restart")
async def restart_search(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "🔍 <b>Yangi qidiruv</b>\n\nNimani qidiryapsiz?",
        reply_markup=property_type_kb("bs"),
        parse_mode="HTML",
    )
    await state.set_state(BuyerStates.property_type)
    await cb.answer()


@router.callback_query(F.data == "br:subscribe")
async def subscribe_empty(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await db.save_subscription(cb.from_user.id, {
        "property_type": data.get("property_type"),
        "location_id":   data.get("location_id"),
        "xonalar":       data.get("xonalar"),
        "dom_type":      data.get("dom_type"),
        "renovation":    data.get("renovation"),
    })
    await cb.answer("✅ Obuna saqlandi! Yangi e'lonlar kelganda xabar beraman.", show_alert=True)


# ── Favorites ────────────────────────────────────────────────────
@router.message(F.text == "❤️ Sevimlilar")
async def show_favorites(msg: Message, state: FSMContext):
    favs = await db.get_favorites(msg.from_user.id)
    if not favs:
        await msg.answer(
            "❤️ Sevimlilari yo'q.\n\n"
            "E'lon ko'rayotganda <b>❤️ Saqlash</b> tugmasini bosing.",
            parse_mode="HTML",
        )
        return

    await msg.answer(f"❤️ <b>Sevimlilar ({len(favs)} ta):</b>", parse_mode="HTML")
    for lst in favs[:10]:
        loc = await db.get_location(lst["location_id"]) if lst.get("location_id") else {}
        text = listing_full_card(lst, loc)
        markup = contact_kb(lst["id"])
        if lst.get("video_file_id"):
            await msg.answer_video(lst["video_file_id"], caption=text, reply_markup=markup, parse_mode="HTML")
        else:
            await msg.answer(text, reply_markup=markup, parse_mode="HTML")


# ── Search history ───────────────────────────────────────────────
@router.message(F.text == "📂 Qidiruv tarixi")
async def show_history(msg: Message, state: FSMContext):
    history = await db.get_search_history(msg.from_user.id, limit=10)
    if not history:
        await msg.answer("📂 Qidiruv tarixi bo'sh.")
        return

    from utils.helpers import PROPERTY_LABELS, RENOVATION_LABELS, DOM_TYPE_LABELS
    lines = ["📂 <b>Oxirgi qidiruvlar:</b>\n"]
    for i, h in enumerate(history, 1):
        f = h.get("filters", {})
        parts = []
        if f.get("property_type"):
            parts.append(PROPERTY_LABELS.get(f["property_type"], f["property_type"]))
        if f.get("xonalar"):
            parts.append(f"{f['xonalar']} xona")
        if f.get("dom_type"):
            parts.append(DOM_TYPE_LABELS.get(f["dom_type"], f["dom_type"]))
        if f.get("renovation"):
            parts.append(RENOVATION_LABELS.get(f["renovation"], f["renovation"]))
        lines.append(f"{i}. {' · '.join(parts) or 'Umumiy qidiruv'}")

    await msg.answer("\n".join(lines), parse_mode="HTML")
