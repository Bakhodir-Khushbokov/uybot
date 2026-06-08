from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import MEDIA_CHANNEL_ID
from handlers.states import SellerStates
from keyboards.inline import (
    transaction_kb, rent_for_kb, balkon_kb, jihoz_kb, commission_kb,
    property_type_kb, dom_type_kb, viloyat_kb, tuman_kb,
    mahalla_kb, buildings_kb, loc_confirm_kb,
    renovation_kb, currency_kb, confirm_publish_kb, listing_manage_kb,
    xonalar_kb, floor_kb, area_kb,
)
from keyboards.reply import cancel_kb, location_kb, skip_kb, main_menu_kb, remove_kb
import database as db
from utils.helpers import (
    format_price, parse_price_usd, parse_price_som,
    check_banned, listing_full_card, make_progress,
    PROPERTY_LABELS, DOM_TYPE_LABELS, RENOVATION_LABELS,
)

router = Router()
PAGE = 8  # Mahalla per page


# ── E'lon joylash (boshlash) ─────────────────────────────────
@router.message(F.text == "➕ E'lon joylash")
async def start_listing(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Bekor qilish uchun:", reply_markup=cancel_kb())
    await msg.answer(
        "🏷 *Sotasizmi yoki ijaraga berasizmi?*",
        reply_markup=transaction_kb(),
        parse_mode="Markdown",
    )
    await state.set_state(SellerStates.transaction)


@router.callback_query(SellerStates.transaction, F.data.startswith("trx:"))
async def seller_transaction(cb: CallbackQuery, state: FSMContext):
    trx = cb.data.split(":")[1]
    await state.update_data(transaction_type=trx)
    await cb.message.edit_text(
        f"{make_progress(1, 6)}\n\n"
        "🏠 Mulk turini tanlang:",
        reply_markup=property_type_kb("pt"),
    )
    await state.set_state(SellerStates.property_type)
    await cb.answer()


# ── 1. Mulk turi ─────────────────────────────────────────────
@router.callback_query(SellerStates.property_type, F.data.startswith("pt:"))
async def seller_property_type(cb: CallbackQuery, state: FSMContext):
    ptype = cb.data.split(":")[1]
    await state.update_data(property_type=ptype)

    if ptype in ("kvartira", "ofis"):
        await cb.message.edit_text(
            f"{make_progress(1, 6)}\n\n"
            "Dom qanday?",
            reply_markup=dom_type_kb(),
            parse_mode="Markdown",
        )
        await state.set_state(SellerStates.dom_type)
    else:
        await _ask_viloyat(cb.message, state)
    await cb.answer()


# ── 1.1 Dom turi ─────────────────────────────────────────────
@router.callback_query(SellerStates.dom_type, F.data.startswith("dt:"))
async def seller_dom_type(cb: CallbackQuery, state: FSMContext):
    await state.update_data(dom_type=cb.data.split(":")[1])
    await _ask_viloyat(cb.message, state)
    await cb.answer()


# ── 2. Viloyat ───────────────────────────────────────────────
async def _ask_viloyat(msg, state: FSMContext):
    viloyatlar = await db.get_viloyatlar()
    if not viloyatlar:
        await msg.answer("❗ Hududlar bazasi bo'sh. Admin bilan bog'laning.")
        return
    await msg.edit_text(
        f"{make_progress(2, 6)}\n\n"
        "📍 Viloyatni tanlang:",
        reply_markup=viloyat_kb(viloyatlar),
        parse_mode="Markdown",
    )
    await state.set_state(SellerStates.viloyat)


@router.callback_query(SellerStates.viloyat, F.data.startswith("vil:"))
async def seller_viloyat(cb: CallbackQuery, state: FSMContext):
    viloyat = cb.data[4:]
    await state.update_data(viloyat=viloyat, mah_offset=0)
    tumanlar = await db.get_tumanlar(viloyat)
    await cb.message.edit_text(
        f"*{viloyat}* — Tumanni tanlang:",
        reply_markup=tuman_kb(tumanlar),
        parse_mode="Markdown",
    )
    await state.set_state(SellerStates.tuman)
    await cb.answer()


# ── 2b. Tuman ────────────────────────────────────────────────
@router.callback_query(SellerStates.tuman, F.data.startswith("tum:"))
async def seller_tuman(cb: CallbackQuery, state: FSMContext):
    tuman = cb.data[4:]
    await state.update_data(tuman=tuman, mah_offset=0, mah_query="")
    await _show_mahallalar(cb.message, state)
    await state.set_state(SellerStates.mahalla_page)
    await cb.answer()


async def _show_mahallalar(msg, state: FSMContext, edit: bool = True):
    data   = await state.get_data()
    viloyat= data["viloyat"]
    tuman  = data["tuman"]
    query  = data.get("mah_query", "")
    offset = data.get("mah_offset", 0)

    mahallalar = await db.search_mahallalar(viloyat, tuman, query, PAGE, offset)
    total      = await db.count_mahallalar(viloyat, tuman, query)
    text = f"*{tuman}* — Mahallani tanlang:\n_({total} ta topildi)_"
    kb   = mahalla_kb(mahallalar, total, offset)
    if edit:
        await msg.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await msg.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(SellerStates.mahalla_page, F.data.startswith("mah_page:"))
async def seller_mah_page(cb: CallbackQuery, state: FSMContext):
    offset = int(cb.data.split(":")[1])
    await state.update_data(mah_offset=offset)
    await _show_mahallalar(cb.message, state)
    await cb.answer()


@router.callback_query(F.data == "search:mah")
async def ask_mah_search(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text("🔍 Mahalla nomini yozing:")
    await state.set_state(SellerStates.mahalla_search)
    await cb.answer()


@router.message(SellerStates.mahalla_search)
async def seller_mah_search(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        return
    await state.update_data(mah_query=msg.text.strip(), mah_offset=0)
    await _show_mahallalar(msg, state, edit=False)
    await state.set_state(SellerStates.mahalla_page)


# ── 2c. Mahalla tanlash ──────────────────────────────────────
@router.callback_query(SellerStates.mahalla_page, F.data.startswith("mah:"))
async def seller_mahalla_pick(cb: CallbackQuery, state: FSMContext):
    loc_id = int(cb.data[4:])
    await state.update_data(location_id=loc_id)

    await cb.message.edit_text(
        "Dom raqami yoki nomini yozing:\n"
        "_Masalan: 14-A yoki Navruz ko'chasi 22_\n\n"
        "Bilmasangiz — «—» yozing",
        parse_mode="Markdown",
    )
    await cb.message.answer("👇", reply_markup=cancel_kb())
    await state.set_state(SellerStates.dom_number)
    await cb.answer()


# ── 2d. Dom raqami ───────────────────────────────────────────
@router.message(SellerStates.dom_number)
async def seller_dom_number(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        return
    dom = msg.text.strip()
    await state.update_data(dom_number=dom)

    data   = await state.get_data()
    loc_id = data.get("location_id")

    if dom == "—":
        # Joylashuvni qo'lda so'rash
        await _ask_manual_location(msg)
        await state.set_state(SellerStates.loc_manual)
        return

    buildings = await db.find_buildings(loc_id, dom)
    if buildings:
        await state.update_data(_buildings=buildings)
        if len(buildings) == 1:
            b = buildings[0]
            await msg.answer(
                f"✅ Bazada topildi: *{b['dom_number']}*\n"
                f"Joylashuvni tekshiring 👇",
                parse_mode="Markdown",
            )
            await msg.answer_location(latitude=b["lat"], longitude=b["lon"])
            await msg.answer("Shu to'g'ri joymiZ?", reply_markup=loc_confirm_kb(b["id"]))
        else:
            await msg.answer(
                f"*{len(buildings)} ta mos bino topildi.* Qaysi biri?",
                reply_markup=buildings_kb(buildings),
                parse_mode="Markdown",
            )
        await state.set_state(SellerStates.loc_found)
    else:
        await msg.answer(
            f"❗ *«{dom}»* bazamizda topilmadi.\n\n"
            "📍 Joylashuvni qo'lda yuboring:",
            parse_mode="Markdown",
        )
        await _ask_manual_location(msg)
        await state.set_state(SellerStates.loc_manual)


async def _ask_manual_location(msg: Message):
    await msg.answer(
        "Telegramda 📎 → *Joylashuv* tugmasini bosing,\n"
        "xaritada domni toping va yuboring.",
        reply_markup=location_kb(),
        parse_mode="Markdown",
    )


# ── 2e. Joylashuv — bazadan tasdiqlash ──────────────────────
@router.callback_query(SellerStates.loc_found, F.data.startswith("locok:"))
async def loc_ok(cb: CallbackQuery, state: FSMContext):
    bid = int(cb.data.split(":")[1])
    b   = await db.get_building(bid)
    if b:
        await state.update_data(lat=b["lat"], lon=b["lon"], building_id=bid)
    await cb.message.edit_text("✅ Joylashuv tasdiqlandi!")
    await _ask_video(cb.message, state)
    await cb.answer()


@router.callback_query(SellerStates.loc_found, F.data == "bld:manual")
async def loc_manual_from_found(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text("📍 Joylashuvni qo'lda yuboring:")
    await _ask_manual_location(cb.message)
    await state.set_state(SellerStates.loc_manual)
    await cb.answer()


@router.callback_query(SellerStates.loc_found, F.data.startswith("bld:"))
async def loc_pick_building(cb: CallbackQuery, state: FSMContext):
    bid = int(cb.data.split(":")[1])
    b   = await db.get_building(bid)
    if b:
        await cb.message.edit_text(
            f"*{b['dom_number']}* — joylashuv:",
            parse_mode="Markdown",
        )
        await cb.message.answer_location(latitude=b["lat"], longitude=b["lon"])
        await cb.message.answer("Shu to'g'ri joymiZ?", reply_markup=loc_confirm_kb(bid))
    await cb.answer()


# ── 2f. Qo'lda joylashuv ────────────────────────────────────
@router.message(SellerStates.loc_manual, F.location)
async def got_manual_location(msg: Message, state: FSMContext):
    lat = msg.location.latitude
    lon = msg.location.longitude
    await state.update_data(lat=lat, lon=lon)

    # Avtomatik bazaga saqlab, so'ramasdan davom etish
    data   = await state.get_data()
    loc_id = data.get("location_id")
    dom    = data.get("dom_number", "")
    kvartal = data.get("kvartal", "")
    if loc_id and lat and lon:
        bid = await db.add_building(loc_id, dom, lat, lon, kvartal)
        await state.update_data(building_id=bid)

    await msg.answer("✅ Joylashuv qabul qilindi!", reply_markup=remove_kb())
    await _ask_video(msg, state)


@router.message(SellerStates.loc_manual)
async def loc_manual_wrong(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        return
    if msg.text == "➡️ O'tkazib yuborish":
        await msg.answer("Davom etamiz 👍", reply_markup=remove_kb())
        await _ask_video(msg, state)
        return
    await msg.answer("❗ Joylashuvni yuborish uchun tugmani bosing yoki o'tkazib yuboring 👇")


# ── Ortga navigatsiya ────────────────────────────────────────
@router.callback_query(F.data.startswith("back:"))
async def seller_back(cb: CallbackQuery, state: FSMContext):
    target = cb.data.split(":")[1]
    current_state = await state.get_state()

    # Faqat seller oqimida ishlaydi
    seller_states = {s.state for s in SellerStates.__state_items__}
    if current_state not in seller_states:
        await cb.answer()
        return

    data = await state.get_data()

    if target == "video":
        await cb.message.edit_reply_markup(reply_markup=None)
        await _ask_video(cb.message, state)

    elif target == "xonalar":
        await cb.message.edit_text(
            f"{make_progress(4, 6)}\n\n🛏 Nechta xona?",
            reply_markup=xonalar_kb(prefix="xon"),
        )
        await state.set_state(SellerStates.xonalar)

    elif target == "floor":
        xon = data.get("xonalar", "?")
        await cb.message.edit_text(
            f"🛏 Xonalar: {xon} ta ✅\n\n🏗 Nechanchi qavatda?",
            reply_markup=floor_kb(prefix="fl"),
        )
        await state.set_state(SellerStates.floor)

    elif target == "total_floors":
        floor = data.get("floor", "?")
        await cb.message.edit_text(
            f"🏗 Qavat: {floor} ✅\n\n🏢 Bino jami necha qavatli?",
            reply_markup=floor_kb(prefix="tf"),
        )
        await state.set_state(SellerStates.total_floors)

    elif target == "area":
        total = data.get("total_floors", "?")
        await cb.message.edit_text(
            f"🏢 Jami qavatlar: {total} ✅\n\n📐 Maydon (kv.m)?",
            reply_markup=area_kb(prefix="area"),
        )
        await state.set_state(SellerStates.area)

    elif target == "renovation":
        await cb.message.edit_text("Remont turi?", reply_markup=renovation_kb())
        await state.set_state(SellerStates.renovation)

    elif target == "landmark":
        await cb.message.edit_reply_markup(reply_markup=None)
        await cb.message.answer(
            "📌 Mo'ljal (ixtiyoriy):\n"
            "Yaqin yerda nima bor? Masalan: Korzinka yaqini, Metro...\n\n"
            "Bilmasangiz — o'tkazib yuboring 👇",
            reply_markup=skip_kb(),
        )
        await state.set_state(SellerStates.landmark)

    elif target == "price_currency":
        await cb.message.edit_text("Narx valyutasi?", reply_markup=currency_kb())
        await state.set_state(SellerStates.price_currency)

    await cb.answer()


# ── 3. Video ─────────────────────────────────────────────────
async def _ask_video(msg, state: FSMContext):
    await msg.answer(
        f"{make_progress(3, 6)}\n\n"
        "🎙 _Uyingizni 3 daqiqagacha video qilib yuboring._\n\n"
        "📹 Video yuboring:",
        reply_markup=cancel_kb(),
        parse_mode="Markdown",
    )
    await state.set_state(SellerStates.video)


@router.message(SellerStates.video, F.video)
async def got_video(msg: Message, state: FSMContext):
    v = msg.video
    if v.duration and v.duration > 180:
        await msg.answer("❗ Video 3 daqiqadan uzun. Iltimos, qisqaroq video yuboring.")
        return

    wait = await msg.answer("⏳ Video qabul qilindi, tekshirilmoqda...")

    # Taqiqlangan so'z — caption da tekshirish (haqiqiy AI moderation v2 da)
    if msg.caption:
        banned = check_banned(msg.caption)
        if banned:
            await wait.delete()
            await msg.answer(
                f"❌ Video qabul qilinmadi.\n\n"
                f"Sabab: Taqiqlangan so'z aniqlandi (`{banned}`).\n\n"
                "Faqat mulk haqida gapiradigan yangi video yuboring.",
                parse_mode="Markdown",
            )
            return

    # Videoni media kanalga forward qilib, doimiy file_id olish
    permanent_file_id = v.file_id  # fallback
    if MEDIA_CHANNEL_ID:
        try:
            sent = await msg.bot.forward_message(
                chat_id=MEDIA_CHANNEL_ID,
                from_chat_id=msg.chat.id,
                message_id=msg.message_id,
            )
            if sent.video:
                permanent_file_id = sent.video.file_id
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Media kanalga forward qilishda xato: {e}")

    await state.update_data(video_file_id=permanent_file_id)
    await wait.delete()
    await msg.answer("✅ Video qabul qilindi!")
    await _ask_xonalar(msg, state)


@router.message(SellerStates.video)
async def video_wrong(msg: Message):
    if msg.text == "❌ Bekor qilish":
        return
    await msg.answer("❗ Iltimos, *video* yuboring (rasm emas).", parse_mode="Markdown")


# ── 4. Xonalar ───────────────────────────────────────────────
async def _ask_xonalar(msg, state: FSMContext):
    await msg.answer(
        f"{make_progress(4, 6)}\n\n"
        "🛏 Nechta xona?",
        reply_markup=xonalar_kb(prefix="xon"),
    )
    await state.set_state(SellerStates.xonalar)


@router.callback_query(SellerStates.xonalar, F.data.startswith("xon:"))
async def seller_xonalar(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]

    if val.startswith("p"):
        page = int(val[1:])
        await cb.message.edit_reply_markup(reply_markup=xonalar_kb(prefix="xon", page=page))
        await cb.answer()
        return

    xon = int(val)
    await state.update_data(xonalar=xon)
    await cb.message.edit_text(
        f"🛏 Xonalar: {xon} ta ✅\n\n🏗 Nechanchi qavatda?",
        reply_markup=floor_kb(prefix="fl"),
    )
    await state.set_state(SellerStates.floor)
    await cb.answer()


# ── 4b. Qavat ────────────────────────────────────────────────
@router.callback_query(SellerStates.floor, F.data.startswith("fl:"))
async def seller_floor(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]

    if val.startswith("p"):
        page = int(val[1:])
        await cb.message.edit_reply_markup(reply_markup=floor_kb(prefix="fl", page=page))
        await cb.answer()
        return

    floor = int(val)
    await state.update_data(floor=floor)
    await cb.message.edit_text(
        f"🏗 Qavat: {floor} ✅\n\n🏢 Bino jami necha qavatli?",
        reply_markup=floor_kb(prefix="tf"),
    )
    await state.set_state(SellerStates.total_floors)
    await cb.answer()


# ── 4c. Jami qavatlar ────────────────────────────────────────
@router.callback_query(SellerStates.total_floors, F.data.startswith("tf:"))
async def seller_total_floors(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]

    if val.startswith("p"):
        page = int(val[1:])
        await cb.message.edit_reply_markup(reply_markup=floor_kb(prefix="tf", page=page))
        await cb.answer()
        return

    total = int(val)
    await state.update_data(total_floors=total)
    await cb.message.edit_text(
        f"🏢 Jami qavatlar: {total} ✅\n\n📐 Maydon (kv.m)?",
        reply_markup=area_kb(prefix="area"),
    )
    await state.set_state(SellerStates.area)
    await cb.answer()


@router.callback_query(SellerStates.area, F.data.startswith("area:"))
async def seller_area_cb(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]

    if val.startswith("p"):
        page = int(val[1:])
        await cb.message.edit_reply_markup(reply_markup=area_kb(prefix="area", page=page))
        await cb.answer()
        return

    if val == "manual":
        await cb.message.edit_text("📐 Maydonni yozing (kv.m):\nMasalan: 72")
        await cb.answer()
        return

    area = float(val)
    await state.update_data(area=area)
    await cb.message.edit_text(
        f"📐 Maydon: {int(area)} m² ✅\n\nRemont turi?",
        reply_markup=renovation_kb(),
    )
    await state.set_state(SellerStates.renovation)
    await cb.answer()


@router.message(SellerStates.area)
async def seller_area_msg(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        return
    try:
        area = float(msg.text.strip().replace(",", "."))
        if area <= 0 or area > 5000:
            raise ValueError
    except ValueError:
        await msg.answer("Kechirasiz, faqat raqam kiriting, masalan: 72")
        return
    await state.update_data(area=area)
    await msg.answer("Remont turi?", reply_markup=renovation_kb())
    await state.set_state(SellerStates.renovation)


@router.callback_query(SellerStates.renovation, F.data.startswith("renov:"))
async def seller_renovation(cb: CallbackQuery, state: FSMContext):
    renov = cb.data.split(":")[1]
    await state.update_data(renovation=renov)
    await cb.message.edit_text(
        "🏗 *Balkon bormi?*\nO'lchamini tanlang:",
        reply_markup=balkon_kb(),
        parse_mode="Markdown",
    )
    await state.set_state(SellerStates.balkon)
    await cb.answer()


@router.callback_query(SellerStates.balkon, F.data.startswith("blk:"))
async def seller_balkon(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]
    await state.update_data(balkon=None if val == "yoq" else val)
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(
        "📌 Mo'ljal (ixtiyoriy):\n"
        "Yaqin yerda nima bor? Masalan: Korzinka yaqini, Metro, Maktab...\n\n"
        "Bilmasangiz — o'tkazib yuboring 👇",
        reply_markup=skip_kb(),
    )
    await state.set_state(SellerStates.landmark)
    await cb.answer()


@router.message(SellerStates.landmark)
async def seller_landmark(msg: Message, state: FSMContext):
    if not msg.text:
        await msg.answer("Iltimos, matn yozing yoki o'tkazib yuboring 👇")
        return
    if msg.text == "❌ Bekor qilish":
        return
    landmark = "" if msg.text.strip() in ("➡️ O'tkazib yuborish", "O'tkazib yuborish") else msg.text.strip()
    await state.update_data(landmark=landmark)

    data = await state.get_data()
    user = await db.get_user(msg.from_user.id)
    role = user.get("role", "") if user else ""

    # Arenda → jihoz so'raymiz
    if data.get("transaction_type") == "arenda":
        await msg.answer(
            "🛋 *Uyda nima bor? Jihoz tanlang:*\n_(Bir nechta tanlash mumkin)_",
            reply_markup=jihoz_kb(set()),
            parse_mode="Markdown",
        )
        await state.update_data(jihoz_selected=[])
        await state.set_state(SellerStates.jihoz)
    # Makler → komisyon so'raymiz
    elif role == "makler":
        await msg.answer(
            "💼 *Vositachilik haqi bormi?*",
            reply_markup=commission_kb(),
            parse_mode="Markdown",
        )
        await state.set_state(SellerStates.commission)
    else:
        await msg.answer("Narx valyutasi?", reply_markup=currency_kb())
        await state.set_state(SellerStates.price_currency)


@router.callback_query(SellerStates.jihoz, F.data.startswith("jh:"))
async def seller_jihoz(cb: CallbackQuery, state: FSMContext):
    val = cb.data.split(":")[1]
    data = await state.get_data()
    selected = set(data.get("jihoz_selected") or [])

    if val == "done":
        import json
        await state.update_data(jihoz=json.dumps(list(selected), ensure_ascii=False))
        user = await db.get_user(cb.from_user.id)
        role = user.get("role", "") if user else ""
        if role == "makler":
            await cb.message.edit_text(
                "💼 *Vositachilik haqi bormi?*",
                reply_markup=commission_kb(),
                parse_mode="Markdown",
            )
            await state.set_state(SellerStates.commission)
        else:
            await cb.message.edit_reply_markup(reply_markup=None)
            await cb.message.answer("Narx valyutasi?", reply_markup=currency_kb())
            await state.set_state(SellerStates.price_currency)
    else:
        if val in selected:
            selected.remove(val)
        else:
            selected.add(val)
        await state.update_data(jihoz_selected=list(selected))
        await cb.message.edit_reply_markup(reply_markup=jihoz_kb(selected))

    await cb.answer()


@router.callback_query(SellerStates.commission, F.data.startswith("com:"))
async def seller_commission(cb: CallbackQuery, state: FSMContext):
    await state.update_data(has_commission=(cb.data == "com:yes"))
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer("Narx valyutasi?", reply_markup=currency_kb())
    await state.set_state(SellerStates.price_currency)
    await cb.answer()


@router.callback_query(SellerStates.price_currency, F.data.startswith("cur:"))
async def seller_currency(cb: CallbackQuery, state: FSMContext):
    cur = cb.data.split(":")[1]
    await state.update_data(price_currency=cur)
    data = await state.get_data()

    await _ask_price_amount(cb.message, state, cur)
    await cb.answer()


async def _ask_price_amount(msg, state: FSMContext, cur: str):
    if cur == "usd":
        hint = "_Masalan: 500 (500 dollar)_"
    else:
        hint = "_Masalan: 3 (3 million so'm)_"

    await msg.edit_text(
        f"💰 Narxni kiriting:\n{hint}",
        reply_markup=None,
        parse_mode="Markdown",
    )
    await msg.answer("👇", reply_markup=cancel_kb())
    await state.set_state(SellerStates.price_amount)


@router.message(SellerStates.price_amount)
async def seller_price(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        return
    data = await state.get_data()
    cur  = data.get("price_currency", "usd")

    if cur == "usd":
        amount = parse_price_usd(msg.text)
    else:
        amount = parse_price_som(msg.text)

    if not amount or amount <= 0:
        await msg.answer("Kechirasiz, faqat raqam kiriting, masalan: 47500")
        return

    display = format_price(amount, cur)
    await state.update_data(price_amount=amount, price_display=display)

    data2 = await state.get_data()
    if data2.get("transaction_type") == "arenda":
        await msg.answer(
            "👥 *Ijara kimlarga mo'ljallangan?*",
            reply_markup=rent_for_kb(),
            parse_mode="Markdown",
        )
        await state.set_state(SellerStates.rent_for)
    else:
        await _show_review(msg, state)


@router.callback_query(SellerStates.rent_for, F.data.startswith("rf:"))
async def seller_rent_for(cb: CallbackQuery, state: FSMContext):
    await state.update_data(rent_for=cb.data.split(":")[1])
    await cb.message.edit_text(
        "🛋 *Uyda nima bor? Jihoz tanlang:*\n_(Bir nechta tanlash mumkin)_",
        reply_markup=jihoz_kb(set()),
        parse_mode="Markdown",
    )
    await state.update_data(jihoz_selected=[])
    await state.set_state(SellerStates.jihoz)
    await cb.answer()


# ── 5. Ko'rib chiqish ────────────────────────────────────────
async def _show_review(msg: Message, state: FSMContext):
    data  = await state.get_data()
    loc   = await db.get_location(data.get("location_id")) if data.get("location_id") else None
    user  = await db.get_user(msg.from_user.id)
    phone = user.get("phone", "") if user else ""

    ptype = PROPERTY_LABELS.get(data.get("property_type", ""), "🏠")
    dtype = DOM_TYPE_LABELS.get(data.get("dom_type", ""), "")
    renov = RENOVATION_LABELS.get(data.get("renovation", ""), "")

    loc_str = ""
    if loc:
        loc_str = f"{loc['viloyat']}, {loc['tuman']}, {loc['mahalla']}"

    trx   = "🔑 Ijara" if data.get("transaction_type") == "arenda" else "🏷 Sotish"

    text = (
        f"{make_progress(5, 6)}\n\n"
        f"📋 *E'loningiz:*\n\n"
        f"{trx} | {ptype}" + (f" · {dtype}" if dtype else "") + "\n"
        f"📹 Video: ✅\n"
    )
    if data.get("xonalar"):      text += f"🛏 Xonalar: {data['xonalar']}\n"
    if data.get("floor"):        text += f"🏗 Qavat: {data['floor']}/{data.get('total_floors')}\n"
    if data.get("area"):         text += f"📐 Maydon: {int(data['area'])} m²\n"
    if renov:                    text += f"🔨 Remont: {renov}\n"
    if data.get("balkon"):       text += f"🏗 Balkon: {data['balkon']} m\n"
    if data.get("landmark"):     text += f"📌 Mo'ljal: {data['landmark']}\n"
    if loc_str:                  text += f"📍 {loc_str}\n"
    if data.get("price_display"):text += f"💰 Narx: *{data['price_display']}*\n"

    RENT_FOR_LABELS = {
        "oila": "👨‍👩‍👧 Oila", "chet_ellik": "🌍 Chet ellik",
        "yigitlar": "👦 Yigitlar", "qizlar": "👧 Qizlar", "farqi_yoq": "✅ Farqi yo'q",
    }
    if data.get("rent_for"):
        text += f"👥 Kimlar uchun: {RENT_FOR_LABELS.get(data['rent_for'], '')}\n"

    if data.get("jihoz_selected"):
        from keyboards.inline import JIHOZ_LIST
        jihoz_labels = {k: v for v, k in JIHOZ_LIST}
        names = [jihoz_labels.get(j, j) for j in data["jihoz_selected"]]
        text += f"🛋 Jihoz: {', '.join(names)}\n"

    if data.get("has_commission"):
        text += "💼 Vositachilik haqi: ✅ Bor\n"

    await msg.answer(text, reply_markup=confirm_publish_kb(), parse_mode="Markdown")
    await state.set_state(SellerStates.review)


@router.callback_query(SellerStates.review, F.data == "pub:yes")
async def publish_listing(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = await db.get_user(cb.from_user.id)

    listing_data = {
        "seller_id":      cb.from_user.id,
        "property_type":  data.get("property_type"),
        "dom_type":       data.get("dom_type"),
        "location_id":    data.get("location_id"),
        "building_id":    data.get("building_id"),
        "lat":            data.get("lat"),
        "lon":            data.get("lon"),
        "video_file_id":  data.get("video_file_id"),
        "xonalar":        data.get("xonalar"),
        "renovation":     data.get("renovation"),
        "floor":          data.get("floor"),
        "total_floors":   data.get("total_floors"),
        "area":           data.get("area"),
        "landmark":       data.get("landmark"),
        "price_amount":   data.get("price_amount"),
        "price_currency": data.get("price_currency"),
        "price_display":    data.get("price_display"),
        "transaction_type": data.get("transaction_type", "sotish"),
        "rent_for":         data.get("rent_for"),
        "balkon":           data.get("balkon"),
        "jihoz":            __import__("json").dumps(data.get("jihoz_selected") or [], ensure_ascii=False) if data.get("jihoz_selected") else None,
        "has_commission":   data.get("has_commission", False),
        "phone":            user.get("phone") if user else "",
    }

    listing_id = await db.add_listing(listing_data)
    await db.increment_daily_count(cb.from_user.id)

    # Obunachilarga xabar yuborish
    subscribers = await db.get_matching_subscribers(listing_data)
    for sub_id in subscribers:
        if sub_id != cb.from_user.id:
            try:
                await cb.bot.send_message(
                    sub_id,
                    f"🔔 *Siz qidirayotgan hududda yangi e'lon!*\n\n"
                    f"#{listing_id} · {data.get('price_display', '')}",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    from config import ADMIN_IDS
    from keyboards.inline import kb as ikb

    await cb.message.edit_text(
        f"{make_progress(6, 6)}\n\n"
        f"✅ *E'lon #{listing_id} joylashtirildi!*\n\n"
        "Biz uni tekshirib chiqamiz — tez orada faollashtiriladi.",
        parse_mode="Markdown",
    )

    # Adminga yangi e'lon haqida xabar
    all_admin_ids = ADMIN_IDS[:]
    try:
        import database as _db
        db_admins = await _db.get_admin_ids()
        all_admin_ids = list(set(ADMIN_IDS + db_admins))
    except Exception:
        pass

    for admin_id in all_admin_ids:
        try:
            await cb.bot.send_message(
                admin_id,
                f"📥 <b>Yangi e'lon #{listing_id}</b>\n"
                f"Sotuvchi: @{cb.from_user.username or cb.from_user.id}\n"
                f"Tur: {listing_data.get('property_type')} | {listing_data.get('transaction_type')}\n"
                f"Narx: {listing_data.get('price_display', '—')}",
                reply_markup=ikb(
                    [(f"✅ Faollashtirish", f"adm_lst:approve:{listing_id}"),
                     (f"❌ Rad etish",       f"adm_lst:reject:{listing_id}")],
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass

    await cb.message.answer("Nima qilmoqchisiz?", reply_markup=main_menu_kb("seller"))
    await state.clear()
    await cb.answer()


@router.callback_query(F.data.startswith("donat:"))
async def donat_cb(cb: CallbackQuery):
    if cb.data == "donat:yes":
        from config import DONATION_CARD
        await cb.message.edit_text(
            f"💳 Karta raqami:\n\n`{DONATION_CARD}`\n\nRahmat! Sizning yordamingiz loyihani rivojlantiradi 🙏",
            parse_mode="Markdown",
        )
    else:
        await cb.message.delete()
    await cb.answer()


@router.callback_query(SellerStates.review, F.data == "pub:edit")
async def edit_listing(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cur = data.get("price_currency", "usd")
    if cur == "usd":
        hint = "Masalan: 47.500 (47 ming 500 dollar)"
    else:
        hint = "Masalan: 350 (350 mln so'm) yoki 1250 (1 mlrd 250 mln)"
    await cb.message.edit_text(
        f"✏️ Narxni qaytadan kiriting:\n{hint}",
    )
    await cb.message.answer("👇", reply_markup=cancel_kb())
    await state.set_state(SellerStates.price_amount)
    await cb.answer()


# ── Mening e'lonlarim ────────────────────────────────────────
async def _send_my_listings(chat_msg: Message, user_id: int, offset: int = 0):
    """E'lonlarni sahifalab chiqarish."""
    from aiogram.types import InlineKeyboardMarkup
    listings = await db.get_seller_listings(user_id)

    if not listings:
        await chat_msg.answer(
            "📭 Sizda hozircha e'lonlar yo'q.\n\n"
            "E'lon joylashtirish uchun: *➕ E'lon joylash*",
            parse_mode="Markdown",
        )
        return

    total  = len(listings)
    chunk  = listings[offset:offset + 5]
    STATUS = {"active": "✅ Faol", "pending": "⏳ Kutilmoqda",
              "sold": "🤝 Sotildi", "deleted": "❌ O'chirilgan"}

    await chat_msg.answer(
        f"📋 *Sizning e'lonlaringiz:* {total} ta\n"
        f"_({offset+1}–{min(offset+5, total)} ko'rsatilmoqda)_",
        parse_mode="Markdown",
    )

    for lst in chunk:
        loc = await db.get_location(lst["location_id"]) if lst.get("location_id") else None
        status_label = STATUS.get(lst.get("status", ""), "❓")

        text = (
            f"{status_label} | *E'lon #{lst['id']}*\n"
            f"{listing_full_card(lst, loc)}\n\n"
            f"👁 Ko'rishlar: {lst.get('views_count', 0)}   "
            f"📞 Aloqa: {lst.get('contact_count', 0)}"
        )
        can_manage = lst.get("status") in ("active", "pending")
        reply_kb = listing_manage_kb(lst["id"]) if can_manage else None

        try:
            await chat_msg.answer_video(
                video=lst["video_file_id"],
                caption=text,
                reply_markup=reply_kb,
                parse_mode="Markdown",
            )
        except Exception:
            await chat_msg.answer(text, reply_markup=reply_kb, parse_mode="Markdown")

    # Paginatsiya
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(
            text="⬆️ Oldingi", callback_data=f"mylst:page:{offset-5}"))
    if offset + 5 < total:
        nav.append(InlineKeyboardButton(
            text=f"⬇️ Ko'proq ({total - offset - 5} ta)",
            callback_data=f"mylst:page:{offset+5}"))
    if nav:
        await chat_msg.answer(
            f"_{offset+1}–{min(offset+5, total)} / {total}_",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[nav]),
            parse_mode="Markdown",
        )


@router.message(F.text == "📋 Mening e'lonlarim")
async def my_listings(msg: Message, state: FSMContext):
    await state.clear()
    await _send_my_listings(msg, msg.from_user.id, offset=0)


@router.callback_query(F.data.startswith("mylst:page:"))
async def my_listings_page(cb: CallbackQuery):
    offset = int(cb.data.split(":")[2])
    await cb.answer()
    await _send_my_listings(cb.message, cb.from_user.id, offset=offset)


# ── Sotildi / O'chirish ──────────────────────────────────────
@router.callback_query(F.data.startswith("lst:"))
async def manage_listing(cb: CallbackQuery):
    parts = cb.data.split(":")
    action, listing_id = parts[1], int(parts[2])

    if action == "sold":
        await db.update_listing_status(listing_id, "sold")
        try:
            await cb.message.edit_caption(
                cb.message.caption + "\n\n✅ *SOTILDI* deb belgilandi.",
                parse_mode="Markdown",
            )
        except Exception:
            pass
        await cb.answer("✅ Tabriklaymiz!")

        # Donat taklifi
        from config import DONATION_CARD
        from keyboards.inline import kb as ikb
        if DONATION_CARD:
            await cb.message.answer(
                "🎉 Tabriklaymiz! Uyingiz sotildi!\n\n"
                "💛 *Loyiha rivoji uchun ixtiyoriy donat:*\n\n"
                f"💳 `{DONATION_CARD}`\n\n"
                "_Har qanday miqdor qabul. Rahmat!_ 🙏",
                reply_markup=ikb(
                    [("💳 Karta raqamini ko'rish", "donat:yes"),
                     ("➡️ O'tkazib yuborish",       "donat:skip")],
                ),
                parse_mode="Markdown",
            )

        # Notariat taklifi
        await cb.message.answer(
            "📜 *Notariat xizmati kerakmi?*\n\n"
            "Uy sotish shartnomasi, meros yoki boshqa hujjatlarni "
            "notarial tasdiqlash uchun tugmani bosing:",
            reply_markup=ikb(
                [("📜 Uy hujjatlarini tekshirish", "lst:notary_start")],
                [("➡️ Keyinroq",              "lst:notary_skip")],
            ),
            parse_mode="Markdown",
        )
    elif action == "notary_start":
        # Notariat botini boshlash
        from handlers.notary import notary_start
        from aiogram.fsm.context import FSMContext
        # FSMContext yo'q bu yerda, shuning uchun to'g'ridan-to'g'ri xabar yuboramiz
        await cb.message.answer(
            "📜 Notariat xizmatini boshlash uchun /notary buyrug'ini yuboring.",
        )
        await cb.message.delete()
        await cb.answer()
    elif action == "notary_skip":
        await cb.message.delete()
        await cb.answer()
    elif action == "del":
        await db.update_listing_status(listing_id, "deleted")
        await cb.message.edit_caption(
            cb.message.caption + "\n\n🗑 E'lon o'chirildi.",
            parse_mode="Markdown",
        )
        await cb.answer("O'chirildi.")
