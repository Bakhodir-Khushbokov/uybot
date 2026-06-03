"""
Admin panel — faqat ADMIN_IDS ro'yxatidagi foydalanuvchilar uchun.

Funksiyalar:
  • Viloyat / tuman / mahalla qo'shish va o'chirish
  • Bino (building) qo'shish: lokatsiya tanlash → dom № + koordinata
  • Binoni o'chirish

/admin buyrug'i bilan kirish.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from handlers.states import AdminStates
from keyboards.inline import kb
from keyboards.reply import cancel_kb, main_menu_kb, remove_kb
import database as db

router = Router()


# ── Guard filter ──────────────────────────────────────────────────
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── Admin menu keyboard ───────────────────────────────────────────
def admin_menu_kb():
    return kb(
        [("🗺 Viloyat qo'sh",   "adm:add_viloyat"),
         ("🏙 Tuman qo'sh",     "adm:add_tuman")],
        [("🏘 Mahalla qo'sh",   "adm:add_mahalla"),
         ("🏢 Bino qo'sh",      "adm:add_bino")],
        [("❌ Viloyat/tuman/mahalla o'chir", "adm:del_loc")],
        [("🗑 Binoni o'chir",   "adm:del_bld")],
        [("📊 Statistika",      "adm:stats")],
    )


# ── /admin ────────────────────────────────────────────────────────
@router.message(Command("admin"))
async def cmd_admin(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await msg.answer("⛔️ Ruxsat yo'q.")
        return
    await state.clear()
    await msg.answer(
        "👨‍💼 <b>Admin panel</b>\n\nNimani qilmoqchisiz?",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.menu)


# ── Statistika ────────────────────────────────────────────────────
@router.callback_query(AdminStates.menu, F.data == "adm:stats")
async def admin_stats(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    stats = await db.get_stats()
    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"👤 Foydalanuvchilar: <b>{stats.get('users', 0)}</b>\n"
        f"🏠 E'lonlar: <b>{stats.get('listings', 0)}</b>\n"
        f"📍 Lokatsiyalar: <b>{stats.get('locations', 0)}</b>\n"
        f"🏢 Binolar: <b>{stats.get('buildings', 0)}</b>\n"
    )
    await cb.message.edit_text(text, reply_markup=admin_menu_kb(), parse_mode="HTML")
    await cb.answer()


# ═══════════════════════════════════════════════════════════════════
#  LOKATSIYA QO'SHISH
# ═══════════════════════════════════════════════════════════════════

# ── Viloyat qo'sh ─────────────────────────────────────────────────
@router.callback_query(AdminStates.menu, F.data == "adm:add_viloyat")
async def adm_add_viloyat_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    await cb.message.edit_text(
        "🗺 Yangi viloyat nomini yozing:\n"
        "<i>Masalan: Toshkent shahri</i>",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.add_viloyat)
    await cb.answer()


@router.message(AdminStates.add_viloyat)
async def adm_add_viloyat(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    if msg.text == "❌ Bekor qilish":
        await _back_to_menu(msg, state)
        return
    name = msg.text.strip()
    await db.add_location(viloyat=name)
    await msg.answer(f"✅ <b>{name}</b> viloyati qo'shildi!", parse_mode="HTML")
    await _back_to_menu(msg, state)


# ── Tuman qo'sh ───────────────────────────────────────────────────
@router.callback_query(AdminStates.menu, F.data == "adm:add_tuman")
async def adm_add_tuman_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    viloyatlar = await db.get_viloyatlar()
    if not viloyatlar:
        await cb.answer("Avval viloyat qo'shing!", show_alert=True)
        return

    rows = []
    for v in viloyatlar:
        rows.append([(v, f"adm:tv:{v}")])
    rows.append([("🔙 Orqaga", "adm:back")])
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=r[0][0], callback_data=r[0][1])] for r in rows]
    )
    await cb.message.edit_text("Qaysi viloyatga tuman qo'shilsin?", reply_markup=markup)
    await state.set_state(AdminStates.add_tuman)
    await cb.answer()


@router.callback_query(AdminStates.add_tuman, F.data.startswith("adm:tv:"))
async def adm_tuman_viloyat_pick(cb: CallbackQuery, state: FSMContext):
    viloyat = cb.data[len("adm:tv:"):]
    await state.update_data(adm_viloyat=viloyat)
    await cb.message.edit_text(
        f"🏙 <b>{viloyat}</b>\n\nYangi tuman nomini yozing:",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminStates.add_tuman)
async def adm_add_tuman(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    if msg.text == "❌ Bekor qilish":
        await _back_to_menu(msg, state)
        return
    data = await state.get_data()
    viloyat = data.get("adm_viloyat")
    if not viloyat:
        await msg.answer("Avval viloyatni tanlang.")
        return
    name = msg.text.strip()
    await db.add_location(viloyat=viloyat, tuman=name)
    await msg.answer(f"✅ <b>{name}</b> tumani qo'shildi!", parse_mode="HTML")
    await _back_to_menu(msg, state)


# ── Mahalla qo'sh ─────────────────────────────────────────────────
@router.callback_query(AdminStates.menu, F.data == "adm:add_mahalla")
async def adm_add_mahalla_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    await cb.message.edit_text(
        "🏘 Mahalla qo'shish.\n\n"
        "Viloyat nomini yozing (keyin tuman va mahalla so'raladi):",
    )
    await state.update_data(adm_step="viloyat")
    await state.set_state(AdminStates.add_mahalla)
    await cb.answer()


@router.message(AdminStates.add_mahalla)
async def adm_add_mahalla(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    if msg.text == "❌ Bekor qilish":
        await _back_to_menu(msg, state)
        return

    data = await state.get_data()
    step = data.get("adm_step", "viloyat")

    if step == "viloyat":
        await state.update_data(adm_viloyat=msg.text.strip(), adm_step="tuman")
        await msg.answer("Tuman nomini yozing:")

    elif step == "tuman":
        await state.update_data(adm_tuman=msg.text.strip(), adm_step="mahalla")
        await msg.answer("Mahalla nomini yozing:")

    elif step == "mahalla":
        v = data["adm_viloyat"]
        t = data["adm_tuman"]
        m = msg.text.strip()
        await db.add_location(viloyat=v, tuman=t, mahalla=m)
        await msg.answer(
            f"✅ <b>{v} › {t} › {m}</b> qo'shildi!",
            parse_mode="HTML",
        )
        await _back_to_menu(msg, state)

    elif step == "postal":
        # optional postal code step — not used in current flow
        await _back_to_menu(msg, state)


# ═══════════════════════════════════════════════════════════════════
#  BINO QO'SHISH
# ═══════════════════════════════════════════════════════════════════

@router.callback_query(AdminStates.menu, F.data == "adm:add_bino")
async def adm_add_bino_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    await cb.message.edit_text(
        "🏢 Bino qo'shish.\n\n"
        "Qidirish uchun mahalla ID sini yozing yoki mahalla nomini yozing:\n"
        "<i>(masalan: Chilonzor, Yunusobod...)</i>",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.search_loc)
    await cb.answer()


@router.message(AdminStates.search_loc)
async def adm_search_loc(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    if msg.text == "❌ Bekor qilish":
        await _back_to_menu(msg, state)
        return

    query = msg.text.strip()
    # Search by ID first
    if query.isdigit():
        loc = await db.get_location(int(query))
        if loc:
            await _adm_loc_found(msg, state, loc)
            return

    # Search by name
    results = await db.search_mahallalar("", "", query, limit=10, offset=0)
    if not results:
        await msg.answer("Topilmadi. Boshqa so'z bilan qidiring:")
        return

    rows = []
    for r in results:
        label = f"{r['viloyat']} › {r['tuman']} › {r['mahalla']}"
        rows.append([(label, f"adm:sloc:{r['id']}")])
    rows.append([("🔙 Orqaga", "adm:back_menu")])

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=r[0][0], callback_data=r[0][1])] for r in rows]
    )
    await msg.answer("Mahallani tanlang:", reply_markup=markup)
    await state.set_state(AdminStates.select_loc)


@router.callback_query(AdminStates.select_loc, F.data.startswith("adm:sloc:"))
async def adm_select_loc(cb: CallbackQuery, state: FSMContext):
    loc_id = int(cb.data.split(":")[2])
    loc = await db.get_location(loc_id)
    if not loc:
        await cb.answer("Topilmadi.", show_alert=True)
        return
    await _adm_loc_found(cb.message, state, loc)
    await cb.answer()


async def _adm_loc_found(msg, state, loc):
    await state.update_data(adm_loc_id=loc["id"])
    await msg.answer(
        f"📍 <b>{loc.get('viloyat')} › {loc.get('tuman')} › {loc.get('mahalla')}</b>\n\n"
        f"Dom (bino) raqamini yozing:\n"
        f"<i>Masalan: 12, 4A, 7/2</i>",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.add_dom)


@router.message(AdminStates.add_dom)
async def adm_add_dom(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    if msg.text == "❌ Bekor qilish":
        await _back_to_menu(msg, state)
        return

    dom_number = msg.text.strip()
    await state.update_data(adm_dom_number=dom_number)

    from keyboards.reply import location_kb
    await msg.answer(
        f"🏢 Dom <b>{dom_number}</b>\n\n"
        f"📍 Endi shu binoning joylashuvini yuboring.\n"
        f"Telegram da <b>📎 → Lokatsiya</b> tugmasini bosing.",
        reply_markup=location_kb(),
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.add_coords)


@router.message(AdminStates.add_coords, F.location)
async def adm_add_coords(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return

    lat = msg.location.latitude
    lon = msg.location.longitude
    data = await state.get_data()
    loc_id     = data.get("adm_loc_id")
    dom_number = data.get("adm_dom_number")
    kvartal    = data.get("adm_kvartal")

    bld_id = await db.add_building(loc_id, dom_number, lat, lon, kvartal)
    loc = await db.get_location(loc_id)
    loc_name = f"{loc.get('viloyat')} › {loc.get('tuman')} › {loc.get('mahalla')}" if loc else str(loc_id)

    await msg.answer(
        f"✅ Bino qo'shildi!\n\n"
        f"📍 {loc_name}\n"
        f"🏢 Dom #{dom_number}\n"
        f"🌐 {lat:.5f}, {lon:.5f}",
        reply_markup=remove_kb(),
        parse_mode="HTML",
    )
    await _back_to_menu(msg, state)


@router.message(AdminStates.add_coords)
async def adm_coords_not_location(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await _back_to_menu(msg, state)
        return
    await msg.answer("Iltimos, Telegram orqali joylashuv yuboring (📎 → Lokatsiya).")


# ═══════════════════════════════════════════════════════════════════
#  LOKATSIYA O'CHIRISH
# ═══════════════════════════════════════════════════════════════════

@router.callback_query(AdminStates.menu, F.data == "adm:del_loc")
async def adm_del_loc_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    await cb.message.edit_text(
        "❌ O'chirish uchun mahalla/tuman/viloyat nomini yozing yoki ID kiriting:"
    )
    await state.set_state(AdminStates.del_loc_search)
    await cb.answer()


@router.message(AdminStates.del_loc_search)
async def adm_del_loc_search(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    if msg.text == "❌ Bekor qilish":
        await _back_to_menu(msg, state)
        return

    query = msg.text.strip()
    if query.isdigit():
        loc = await db.get_location(int(query))
        results = [loc] if loc else []
    else:
        results = await db.search_mahallalar("", "", query, limit=8, offset=0)

    if not results:
        await msg.answer("Topilmadi. Boshqa so'z bilan qidiring:")
        return

    rows = []
    for r in results:
        label = f"❌ {r.get('viloyat','')} › {r.get('tuman','')} › {r.get('mahalla','')} (#{r['id']})"
        rows.append([(label, f"adm:dloc:{r['id']}")])
    rows.append([("🔙 Orqaga", "adm:back_menu")])

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=r[0][0], callback_data=r[0][1])] for r in rows]
    )
    await msg.answer("O'chiriladigan lokatsiyani tanlang:", reply_markup=markup)


@router.callback_query(F.data.startswith("adm:dloc:"))
async def adm_del_loc_confirm(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    loc_id = int(cb.data.split(":")[2])
    loc = await db.get_location(loc_id)
    name = f"{loc.get('viloyat')} › {loc.get('tuman')} › {loc.get('mahalla')}" if loc else str(loc_id)

    confirm_kb = kb(
        [(f"✅ Ha, o'chir", f"adm:dloc_ok:{loc_id}"),
         ("❌ Yo'q", "adm:back_menu")],
    )
    await cb.message.answer(
        f"⚠️ <b>{name}</b> ni o'chirishni tasdiqlaysizmi?\n"
        f"Bu bilan bog'liq barcha binolar ham o'chadi!",
        reply_markup=confirm_kb,
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("adm:dloc_ok:"))
async def adm_del_loc_ok(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    loc_id = int(cb.data.split(":")[2])
    await db.delete_location(loc_id)
    await cb.message.edit_text(f"✅ Lokatsiya #{loc_id} o'chirildi.")
    await cb.answer()
    await _back_to_menu_cb(cb, state)


# ═══════════════════════════════════════════════════════════════════
#  BINO O'CHIRISH
# ═══════════════════════════════════════════════════════════════════

@router.callback_query(AdminStates.menu, F.data == "adm:del_bld")
async def adm_del_bld_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    await cb.message.edit_text(
        "🗑 O'chirish uchun bino ID sini yoki dom raqamini yozing:"
    )
    await state.set_state(AdminStates.del_bld_search)
    await cb.answer()


@router.message(AdminStates.del_bld_search)
async def adm_del_bld_search(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    if msg.text == "❌ Bekor qilish":
        await _back_to_menu(msg, state)
        return

    query = msg.text.strip()
    buildings = await db.find_buildings(location_id=None, query=query, limit=10)

    if not buildings:
        await msg.answer("Topilmadi. Boshqa raqam bilan qidiring:")
        return

    rows = []
    for b in buildings:
        loc = await db.get_location(b["location_id"]) if b.get("location_id") else {}
        loc_name = f"{loc.get('mahalla','?')}" if loc else "?"
        label = f"🗑 {loc_name} · Dom #{b['dom_number']} (#{b['id']})"
        rows.append([(label, f"adm:dbld:{b['id']}")])
    rows.append([("🔙 Orqaga", "adm:back_menu")])

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=r[0][0], callback_data=r[0][1])] for r in rows]
    )
    await msg.answer("O'chiriladigan binoni tanlang:", reply_markup=markup)


@router.callback_query(F.data.startswith("adm:dbld:"))
async def adm_del_bld_ok(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    bld_id = int(cb.data.split(":")[2])
    await db.delete_building(bld_id)
    await cb.message.edit_text(f"✅ Bino #{bld_id} o'chirildi.")
    await cb.answer()


# ═══════════════════════════════════════════════════════════════════
#  YORDAMCHI FUNKSIYALAR
# ═══════════════════════════════════════════════════════════════════

async def _back_to_menu(msg: Message, state: FSMContext):
    await state.set_state(AdminStates.menu)
    await msg.answer(
        "👨‍💼 <b>Admin panel</b>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )


async def _back_to_menu_cb(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.menu)
    await cb.message.answer(
        "👨‍💼 <b>Admin panel</b>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm:back_menu")
async def adm_back_menu(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminStates.menu)
    await cb.message.edit_text(
        "👨‍💼 <b>Admin panel</b>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data == "adm:back")
async def adm_back(cb: CallbackQuery, state: FSMContext):
    await adm_back_menu(cb, state)
