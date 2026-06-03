from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from handlers.states import SellerStates
from keyboards.inline import (
    property_type_kb, dom_type_kb, viloyat_kb, tuman_kb,
    mahalla_kb, buildings_kb, loc_confirm_kb, loc_save_kb,
    renovation_kb, currency_kb, confirm_publish_kb, listing_manage_kb,
    xonalar_kb, floor_kb,
)
from keyboards.reply import cancel_kb, location_kb, skip_kb, main_menu_kb, remove_kb
import database as db
from utils.helpers import (
    format_price, parse_price_usd, parse_price_som,
    check_banned, listing_full_card, make_progress,
    PROPERTY_LABELS, DOM_TYPE_LABELS, RENOVATION_LABELS,
)
from config import DAILY_LISTING_LIMIT

router = Router()
PAGE = 8  # Mahalla per page


# ── E'lon joylash (boshlash) ─────────────────────────────────
@router.message(F.text == "➕ E'lon joylash")
async def start_listing(msg: Message, state: FSMContext):
    await state.clear()

    # Kun limitini tekshirish
    count = await db.get_daily_count(msg.from_user.id)
    user  = await db.get_user(msg.from_user.id)
    if user and user.get("role") != "makler" and count >= DAILY_LISTING_LIMIT:
        await msg.answer(
            f"❗ Bugun {DAILY_LISTING_LIMIT} ta e'lon joylash limitiga yetdingiz.\n"
            "Ertaga qayta urinib ko'ring."
        )
        return

    await msg.answer(
        f"{make_progress(1, 6)}\n\n"
        "🎙 _Nima sotmoqchisiz?_\n\n"
        "Mulk turini tanlang:",
        reply_markup=property_type_kb("pt"),
        parse_mode="Markdown",
    )
    await msg.answer("Bekor qilish uchun:", reply_markup=cancel_kb())
    await state.set_state(SellerStates.property_type)


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

    data = await state.get_data()
    dom  = data.get("dom_number", "")
    await msg.answer(
        f"✅ Joylashuv qabul qilindi!\n\n"
        f"*{dom}* ni bazaga saqlasinmi?\n"
        "_(Keyingi sotuvchilar uchun avtomatik topiladi)_",
        reply_markup=loc_save_kb(),
        parse_mode="Markdown",
    )
    await state.set_state(SellerStates.loc_save)


@router.message(SellerStates.loc_manual)
async def loc_manual_wrong(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        return
    if msg.text == "➡️ O'tkazib yuborish":
        # Lokatsiyasiz davom etish
        await msg.answer("Davom etamiz 👍", reply_markup=remove_kb())
        await _ask_video(msg, state)
        return
    await msg.answer("❗ Joylashuvni yuborish uchun tugmani bosing yoki o'tkazib yuboring 👇")


@router.callback_query(SellerStates.loc_save, F.data.startswith("locsave:"))
async def loc_save_cb(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if cb.data == "locsave:yes":
        loc_id  = data.get("location_id")
        dom     = data.get("dom_number", "")
        lat     = data.get("lat")
        lon     = data.get("lon")
        kvartal = data.get("kvartal", "")
        if loc_id and lat and lon:
            bid = await db.add_building(loc_id, dom, lat, lon, kvartal)
            await state.update_data(building_id=bid)
        await cb.message.edit_text("✅ Bazaga saqlandi! Rahmat.")
    else:
        await cb.message.edit_text("Davom etamiz.")

    await _ask_video(cb.message, state)
    await cb.answer()


# ── 3. Video ─────────────────────────────────────────────────
async def _ask_video(msg, state: FSMContext):
    await msg.answer(
        f"{make_progress(3, 6)}\n\n"
        "🎙 _Uyingizni 3 daqiqagacha video qilib yuboring._\n"
        "_Telefonni yotig'icha tuting — uy kengroq ko'rinadi._\n\n"
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

    await state.update_data(video_file_id=v.file_id)
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

    if val == "more":
        await cb.message.edit_reply_markup(reply_markup=xonalar_kb(prefix="xon", extended=True))
        await cb.answer()
        return
    if val == "less":
        await cb.message.edit_reply_markup(reply_markup=xonalar_kb(prefix="xon", extended=False))
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

    if val == "more":
        await cb.message.edit_reply_markup(reply_markup=floor_kb(prefix="fl", extended=True))
        await cb.answer()
        return
    if val == "less":
        await cb.message.edit_reply_markup(reply_markup=floor_kb(prefix="fl", extended=False))
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

    if val == "more":
        await cb.message.edit_reply_markup(reply_markup=floor_kb(prefix="tf", extended=True))
        await cb.answer()
        return
    if val == "less":
        await cb.message.edit_reply_markup(reply_markup=floor_kb(prefix="tf", extended=False))
        await cb.answer()
        return

    total = int(val)
    await state.update_data(total_floors=total)
    await cb.message.edit_text(
        f"🏢 Jami qavatlar: {total} ✅\n\n📐 Maydon (kv.m)?\nRaqam yozing, masalan: 72",
    )
    await state.set_state(SellerStates.area)
    await cb.answer()


@router.message(SellerStates.area)
async def seller_area(msg: Message, state: FSMContext):
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
    await cb.message.edit_reply_markup(reply_markup=None)   # inline tugmalarni yopish
    await cb.message.answer(
        "📌 Oriëntir (ixtiyoriy):\n"
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
    await msg.answer("Narx valyutasi?", reply_markup=currency_kb())
    await state.set_state(SellerStates.price_currency)


@router.callback_query(SellerStates.price_currency, F.data.startswith("cur:"))
async def seller_currency(cb: CallbackQuery, state: FSMContext):
    cur = cb.data.split(":")[1]
    await state.update_data(price_currency=cur)
    if cur == "usd":
        hint = "_Masalan: 47.500 (47 ming 500 dollar)_"
    else:
        hint = "_Masalan: 350 (350 million so'm)_"
    await cb.message.edit_text(
        f"Narxni kiriting:\n{hint}",
        reply_markup=None,
        parse_mode="Markdown",
    )
    await cb.message.answer("👇", reply_markup=cancel_kb())
    await state.set_state(SellerStates.price_amount)
    await cb.answer()


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
        await msg.answer("Kechirasiz, faqat raqam kiriting, masalan: 47.500")
        return

    display = format_price(amount, cur)
    await state.update_data(price_amount=amount, price_display=display)
    await _show_review(msg, state)


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

    text = (
        f"{make_progress(5, 6)}\n\n"
        f"📋 *E'loningiz:*\n\n"
        f"🏠 Tur: {ptype}" + (f" · {dtype}" if dtype else "") + "\n"
        f"📹 Video: ✅\n"
    )
    if data.get("xonalar"):      text += f"🛏 Xonalar: {data['xonalar']}\n"
    if data.get("floor"):        text += f"🏗 Qavat: {data['floor']}/{data.get('total_floors')}\n"
    if data.get("area"):         text += f"📐 Maydon: {int(data['area'])} m²\n"
    if renov:                    text += f"🔨 Remont: {renov}\n"
    if data.get("landmark"):     text += f"📌 Oriëntir: {data['landmark']}\n"
    if loc_str:                  text += f"📍 {loc_str}\n"
    if data.get("price_display"):text += f"💰 Narx: *{data['price_display']}*\n"

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
        "price_display":  data.get("price_display"),
        "phone":          user.get("phone") if user else "",
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

    await cb.message.edit_text(
        f"{make_progress(6, 6)}\n\n"
        f"✅ *E'lon #{listing_id} joylashtirildi!*\n\n"
        "Biz uni tekshirib chiqamiz — tez orada faollashtiriladi.",
        parse_mode="Markdown",
    )
    await cb.message.answer(
        "Nima qilmoqchisiz?",
        reply_markup=main_menu_kb("seller"),
    )
    await state.clear()
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
@router.message(F.text == "📋 Mening e'lonlarim")
async def my_listings(msg: Message, state: FSMContext):
    await state.clear()
    listings = await db.get_seller_listings(msg.from_user.id)
    if not listings:
        await msg.answer(
            "Sizda hozircha e'lonlar yo'q.\n\n"
            "E'lon joylashtirish uchun: *➕ E'lon joylash*",
            parse_mode="Markdown",
        )
        return

    await msg.answer(f"📋 *Sizning e'lonlaringiz ({len(listings)} ta):*", parse_mode="Markdown")
    for lst in listings[:5]:
        loc = await db.get_location(lst["location_id"]) if lst.get("location_id") else None
        status_icon = {"active": "✅", "pending": "⏳", "sold": "🤝", "deleted": "❌"}.get(
            lst.get("status", ""), "❓")

        text = (
            f"{status_icon} *E'lon #{lst['id']}*\n"
            f"{listing_full_card(lst, loc)}\n\n"
            f"👁 Ko'rishlar: {lst.get('views_count', 0)}  "
            f"📞 Raqam: {lst.get('contact_count', 0)}"
        )
        try:
            await msg.answer_video(
                video=lst["video_file_id"],
                caption=text,
                reply_markup=listing_manage_kb(lst["id"]) if lst.get("status") == "active" else None,
                parse_mode="Markdown",
            )
        except Exception:
            await msg.answer(text, reply_markup=listing_manage_kb(lst["id"]), parse_mode="Markdown")


# ── Sotildi / O'chirish ──────────────────────────────────────
@router.callback_query(F.data.startswith("lst:"))
async def manage_listing(cb: CallbackQuery):
    parts = cb.data.split(":")
    action, listing_id = parts[1], int(parts[2])

    if action == "sold":
        await db.update_listing_status(listing_id, "sold")
        await cb.message.edit_caption(
            cb.message.caption + "\n\n✅ *SOTILDI* deb belgilandi.",
            parse_mode="Markdown",
        )
        await cb.answer("✅ Tabriklaymiz!")
    elif action == "del":
        await db.update_listing_status(listing_id, "deleted")
        await cb.message.edit_caption(
            cb.message.caption + "\n\n🗑 E'lon o'chirildi.",
            parse_mode="Markdown",
        )
        await cb.answer("O'chirildi.")
