"""
Tashkilotlar katalogi moduli.

Foydalanuvchi:
  "🏢 Tashkilotlar" → kategoriya → ro'yxat → batafsil (rasm, manzil, ish vaqti, telefon)

Admin (/org_add buyrug'i):
  Yangi tashkilot qo'shish: kategoriya → nom → manzil → telefon → ish vaqti → rasm → tavsif
  /org_list  — ro'yxat + o'chirish
"""
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

from config import ADMIN_IDS, OWNER_IDS
import database as db
from keyboards.reply import cancel_kb, main_menu_kb

router = Router()

# ── Kategoriyalar (emoji + nom) ──────────────────────────────
ORG_CATEGORIES = {
    "notarius":   "📜 Notariuslar",
    "bank":       "🏦 Banklar",
    "makler":     "🤝 Maklerlik agentliklari",
    "qurilish":   "🏗 Qurilish kompaniyalari",
    "yurist":     "⚖️ Yuridik xizmatlar",
    "boshqa":     "🏢 Boshqa tashkilotlar",
}

CAT_ICONS = {k: v.split()[0] for k, v in ORG_CATEGORIES.items()}


class OrgAdminStates(StatesGroup):
    category    = State()
    name        = State()
    address     = State()
    phone       = State()
    work_hours  = State()
    photo       = State()
    description = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS or user_id in OWNER_IDS


# ── Inline klaviaturalar ─────────────────────────────────────
def category_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=label, callback_data=f"org_cat:{key}")]
            for key, label in ORG_CATEGORIES.items()]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def orgs_list_kb(orgs: list[dict], category: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
                text=o["name"],
                callback_data=f"org_view:{o['id']}"
             )] for o in orgs]
    rows.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data="org_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def org_detail_kb(org_id: int, has_location: bool = False,
                  is_adm: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if has_location:
        rows.append([InlineKeyboardButton(
            text="🗺 Xaritada ko'rish", callback_data=f"org_map:{org_id}"
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"org_back_list:{org_id}")])
    if is_adm:
        rows.append([InlineKeyboardButton(
            text="🗑 O'chirish", callback_data=f"org_del:{org_id}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_cat_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=label, callback_data=f"orga_cat:{key}")]
            for key, label in ORG_CATEGORIES.items()]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─────────────────────────────────────────────────────────────
#  FOYDALANUVCHI OQIMI
# ─────────────────────────────────────────────────────────────
@router.message(F.text == "🏢 Tashkilotlar")
async def orgs_start(msg: Message, state: FSMContext):
    await state.clear()
    cats = await db.get_org_categories()
    if not cats:
        await msg.answer(
            "🏢 <b>Tashkilotlar katalogi</b>\n\n"
            "Hozircha tashkilotlar qo'shilmagan.\n"
            "Tez orada to'ldiriladi!",
            parse_mode="HTML",
        )
        return
    await msg.answer(
        "🏢 <b>Tashkilotlar katalogi</b>\n\n"
        "Kategoriyani tanlang:",
        reply_markup=category_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("org_cat:"))
async def org_category_chosen(cb: CallbackQuery, state: FSMContext):
    cat = cb.data.split(":")[1]
    cat_label = ORG_CATEGORIES.get(cat, cat)
    orgs = await db.get_orgs_by_category(cat)

    if not orgs:
        await cb.answer(f"{cat_label} bo'yicha hozircha ma'lumot yo'q.", show_alert=True)
        return

    await state.update_data(current_category=cat)
    await cb.message.edit_text(
        f"{cat_label}\n\n📋 {len(orgs)} ta tashkilot topildi:",
        reply_markup=orgs_list_kb(orgs, cat),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("org_view:"))
async def org_detail(cb: CallbackQuery, state: FSMContext):
    org_id = int(cb.data.split(":")[1])
    org = await db.get_org(org_id)
    if not org:
        await cb.answer("Topilmadi.", show_alert=True); return

    cat_label = ORG_CATEGORIES.get(org.get("category", ""), org.get("category", ""))
    text = f"{cat_label}\n\n<b>{org['name']}</b>\n\n"

    if org.get("address"):
        text += f"📍 <b>Manzil:</b> {org['address']}\n"
    if org.get("work_hours"):
        text += f"🕐 <b>Ish vaqti:</b> {org['work_hours']}\n"
    if org.get("phone"):
        text += f"📞 <b>Telefon:</b> <code>{org['phone']}</code>\n"
    if org.get("description"):
        text += f"\n📝 {org['description']}\n"

    adm = is_admin(cb.from_user.id)
    kb  = org_detail_kb(org_id,
                        has_location=bool(org.get("lat") and org.get("lon")),
                        is_adm=adm)

    if org.get("photo_id"):
        try:
            await cb.message.delete()
            await cb.message.answer_photo(
                photo=org["photo_id"],
                caption=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
        except Exception:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data.startswith("org_map:"))
async def org_map(cb: CallbackQuery):
    org_id = int(cb.data.split(":")[1])
    org = await db.get_org(org_id)
    if org and org.get("lat") and org.get("lon"):
        await cb.message.answer_location(latitude=org["lat"], longitude=org["lon"])
        await cb.answer()
    else:
        await cb.answer("Lokatsiya mavjud emas.", show_alert=True)


@router.callback_query(F.data == "org_back")
async def org_back(cb: CallbackQuery):
    cats = await db.get_org_categories()
    if not cats:
        await cb.message.edit_text("Tashkilotlar yo'q.")
        await cb.answer(); return
    await cb.message.edit_text(
        "🏢 <b>Tashkilotlar katalogi</b>\n\nKategoriyani tanlang:",
        reply_markup=category_kb(),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("org_back_list:"))
async def org_back_list(cb: CallbackQuery, state: FSMContext):
    org_id = int(cb.data.split(":")[1])
    org = await db.get_org(org_id)
    if not org:
        await org_back(cb); return
    cat   = org.get("category", "")
    orgs  = await db.get_orgs_by_category(cat)
    label = ORG_CATEGORIES.get(cat, cat)
    try:
        await cb.message.delete()
        await cb.message.answer(
            f"{label}\n\n📋 {len(orgs)} ta tashkilot:",
            reply_markup=orgs_list_kb(orgs, cat),
            parse_mode="HTML",
        )
    except Exception:
        await cb.message.edit_text(
            f"{label}\n\n📋 {len(orgs)} ta tashkilot:",
            reply_markup=orgs_list_kb(orgs, cat),
            parse_mode="HTML",
        )
    await cb.answer()


# ─────────────────────────────────────────────────────────────
#  ADMIN OQIMI — tashkilot qo'shish
# ─────────────────────────────────────────────────────────────
@router.message(Command("org_add"))
async def cmd_org_add(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await msg.answer("⛔️ Ruxsat yo'q."); return
    await state.clear()
    await msg.answer(
        "🏢 <b>Yangi tashkilot qo'shish</b>\n\nKategoriyani tanlang:",
        reply_markup=admin_cat_kb(),
        parse_mode="HTML",
    )
    await state.set_state(OrgAdminStates.category)


@router.callback_query(OrgAdminStates.category, F.data.startswith("orga_cat:"))
async def org_admin_category(cb: CallbackQuery, state: FSMContext):
    cat = cb.data.split(":")[1]
    await state.update_data(category=cat)
    await cb.message.edit_text(
        f"✅ Kategoriya: <b>{ORG_CATEGORIES.get(cat, cat)}</b>\n\n"
        "📝 Tashkilot nomini yozing:",
        parse_mode="HTML",
    )
    await cb.message.answer("Bekor qilish:", reply_markup=cancel_kb())
    await state.set_state(OrgAdminStates.name)
    await cb.answer()


@router.message(OrgAdminStates.name)
async def org_admin_name(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish": await state.clear(); return
    await state.update_data(name=msg.text.strip())
    await msg.answer("📍 Manzilni yozing:\n<i>(ko'cha, bino, shahar)</i>", parse_mode="HTML")
    await state.set_state(OrgAdminStates.address)


@router.message(OrgAdminStates.address)
async def org_admin_address(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish": await state.clear(); return
    from keyboards.reply import skip_kb
    skip = "" if msg.text.strip() in ("➡️ O'tkazib yuborish",) else msg.text.strip()
    await state.update_data(address=skip or msg.text.strip())
    await msg.answer(
        "📞 Telefon raqami:\n<i>Masalan: +998 71 123 45 67</i>",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await state.set_state(OrgAdminStates.phone)


@router.message(OrgAdminStates.phone)
async def org_admin_phone(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish": await state.clear(); return
    await state.update_data(phone=msg.text.strip())
    await msg.answer(
        "🕐 Ish vaqti:\n<i>Masalan: Du-Ju 09:00–18:00, Sha 10:00–15:00</i>",
        parse_mode="HTML",
    )
    await state.set_state(OrgAdminStates.work_hours)


@router.message(OrgAdminStates.work_hours)
async def org_admin_hours(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish": await state.clear(); return
    await state.update_data(work_hours=msg.text.strip())
    await msg.answer(
        "🖼 Tashkilot rasmini yuboring:\n"
        "<i>Bino yoki logotip rasmi (ixtiyoriy)</i>\n\n"
        "O'tkazib yuborish uchun yozing: <b>skip</b>",
        parse_mode="HTML",
    )
    await state.set_state(OrgAdminStates.photo)


@router.message(OrgAdminStates.photo, F.photo)
async def org_admin_photo(msg: Message, state: FSMContext):
    await state.update_data(photo_id=msg.photo[-1].file_id)
    await msg.answer(
        "📝 Qisqacha tavsif yozing:\n"
        "<i>Xizmat turlari, imtiyozlar va h.k. (ixtiyoriy)</i>\n\n"
        "O'tkazib yuborish: <b>skip</b>",
        parse_mode="HTML",
    )
    await state.set_state(OrgAdminStates.description)


@router.message(OrgAdminStates.photo)
async def org_admin_photo_skip(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish": await state.clear(); return
    await state.update_data(photo_id=None)
    await msg.answer(
        "📝 Qisqacha tavsif yozing:\n"
        "<i>Xizmat turlari, imtiyozlar (ixtiyoriy)</i>\n\n"
        "O'tkazib yuborish: <b>skip</b>",
        parse_mode="HTML",
    )
    await state.set_state(OrgAdminStates.description)


@router.message(OrgAdminStates.description)
async def org_admin_description(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish": await state.clear(); return
    desc = "" if msg.text.strip().lower() == "skip" else msg.text.strip()
    await state.update_data(description=desc)
    data = await state.get_data()

    # Ko'rib chiqish
    cat_label = ORG_CATEGORIES.get(data.get("category", ""), "")
    preview = (
        f"📋 <b>Tekshirib ko'ring:</b>\n\n"
        f"🏷 Kategoriya: {cat_label}\n"
        f"🏢 Nom: <b>{data.get('name', '')}</b>\n"
        f"📍 Manzil: {data.get('address', '—')}\n"
        f"📞 Telefon: {data.get('phone', '—')}\n"
        f"🕐 Ish vaqti: {data.get('work_hours', '—')}\n"
        f"🖼 Rasm: {'✅' if data.get('photo_id') else '❌'}\n"
        f"📝 Tavsif: {data.get('description') or '—'}\n"
    )
    await msg.answer(
        preview,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Saqlash",        callback_data="orga:save")],
            [InlineKeyboardButton(text="❌ Bekor qilish",   callback_data="orga:cancel")],
        ]),
        parse_mode="HTML",
    )


@router.callback_query(OrgAdminStates.description, F.data == "orga:save")
async def org_admin_save(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    org_id = await db.add_org(data)
    await state.clear()
    await cb.message.edit_text(
        f"✅ <b>Tashkilot #{org_id} qo'shildi!</b>\n\n"
        f"Nom: {data.get('name')}",
        parse_mode="HTML",
    )
    await cb.answer("✅ Saqlandi!")


@router.callback_query(OrgAdminStates.description, F.data == "orga:cancel")
async def org_admin_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Bekor qilindi.")
    await cb.answer()


# ── Admin: ro'yxat va o'chirish ───────────────────────────────
@router.message(Command("org_list"))
async def cmd_org_list(msg: Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("⛔️ Ruxsat yo'q."); return
    orgs = await db.get_all_orgs()
    if not orgs:
        await msg.answer("Tashkilotlar yo'q. /org_add bilan qo'shing."); return

    rows = []
    for o in orgs:
        icon   = CAT_ICONS.get(o.get("category", ""), "🏢")
        active = "✅" if o.get("active") else "❌"
        rows.append([InlineKeyboardButton(
            text=f"{active} {icon} {o['name']}",
            callback_data=f"orga_view:{o['id']}"
        )])

    await msg.answer(
        f"🏢 <b>Barcha tashkilotlar ({len(orgs)} ta):</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("orga_view:"))
async def org_admin_view(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    org_id = int(cb.data.split(":")[1])
    org = await db.get_org(org_id)
    if not org:
        await cb.answer("Topilmadi.", show_alert=True); return

    cat_label = ORG_CATEGORIES.get(org.get("category", ""), "")
    status    = "✅ Faol" if org.get("active") else "❌ Yopiq"
    text = (
        f"{cat_label} — {status}\n\n"
        f"<b>{org['name']}</b>\n"
        f"📍 {org.get('address','—')}\n"
        f"📞 {org.get('phone','—')}\n"
        f"🕐 {org.get('work_hours','—')}\n"
        f"📝 {org.get('description') or '—'}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 O'chirish (arxiv)",
                              callback_data=f"orga_del:{org_id}")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="orga_back")],
    ])
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data.startswith("org_del:"))
@router.callback_query(F.data.startswith("orga_del:"))
async def org_delete(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    org_id = int(cb.data.split(":")[1])
    await db.delete_org(org_id)
    await cb.message.edit_text("🗑 Tashkilot arxivlandi.")
    await cb.answer("✅ O'chirildi.", show_alert=True)


@router.callback_query(F.data == "orga_back")
async def org_admin_back(cb: CallbackQuery):
    await cmd_org_list(cb.message)
    await cb.answer()
