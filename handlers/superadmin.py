"""
Super-admin panel — faqat OWNER_IDS uchun.
/owner buyrug'i bilan kirish.

Imkoniyatlar:
  • Statistika (foydalanuvchilar, e'lonlar, adminlar)
  • Sub-admin qo'shish (ID yoki username orqali)
  • Sub-adminlarni ko'rish va o'chirish
  • Feedback/takliflarni ko'rish
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import OWNER_IDS
import database as db

router = Router()


class OwnerStates(StatesGroup):
    menu        = State()
    add_admin   = State()


def is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS


def owner_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika",           callback_data="ow:stats")],
        [InlineKeyboardButton(text="📜 Notariat zayavkalari", callback_data="ow:notary")],
        [InlineKeyboardButton(text="🏢 Tashkilotlar",         callback_data="ow:orgs")],
        [InlineKeyboardButton(text="👥 Adminlar ro'yxati",    callback_data="ow:admins")],
        [InlineKeyboardButton(text="➕ Admin qo'shish",       callback_data="ow:add_admin")],
        [InlineKeyboardButton(text="💬 Takliflar",             callback_data="ow:feedback")],
    ])


# ── /owner ───────────────────────────────────────────────────
@router.message(Command("owner"))
async def cmd_owner(msg: Message, state: FSMContext):
    if not is_owner(msg.from_user.id):
        await msg.answer("⛔️ Ruxsat yo'q.")
        return
    await state.clear()
    await msg.answer(
        "👑 <b>Super-admin panel</b>\n\nXush kelibsiz!",
        reply_markup=owner_menu_kb(),
        parse_mode="HTML",
    )
    await state.set_state(OwnerStates.menu)


# ── Statistika ───────────────────────────────────────────────
@router.callback_query(OwnerStates.menu, F.data == "ow:stats")
async def ow_stats(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    stats   = await db.get_stats()
    admins  = await db.get_all_admins()
    nstats  = await db.get_notary_stats()

    text = (
        "📊 <b>Statistika</b>\n\n"
        f"👤 Foydalanuvchilar: <b>{stats.get('users', 0)}</b>\n"
        f"🏠 E'lonlar jami: <b>{stats.get('listings', 0)}</b>\n"
        f"✅ Faol e'lonlar: <b>{stats.get('active_listings', 0)}</b>\n"
        f"⏳ Kutilmoqda: <b>{stats.get('pending_listings', 0)}</b>\n"
        f"📍 Lokatsiyalar: <b>{stats.get('locations', 0)}</b>\n"
        f"🏢 Binolar: <b>{stats.get('buildings', 0)}</b>\n"
        f"👨‍💼 Sub-adminlar: <b>{len(admins)}</b>\n\n"
        f"📜 <b>Notariat zayavkalari:</b>\n"
        f"   🆕 Yangi: <b>{nstats.get('new', 0)}</b>\n"
        f"   💳 To'lov tekshiruvida: <b>{nstats.get('payment_check', 0)}</b>\n"
        f"   ✅ Bajarildi: <b>{nstats.get('done', 0)}</b>\n"
        f"   ❌ Rad etildi: <b>{nstats.get('rejected', 0)}</b>\n"
        f"   📋 Jami: <b>{nstats.get('total', 0)}</b>\n"
    )
    await cb.message.edit_text(text, reply_markup=owner_menu_kb(), parse_mode="HTML")
    await cb.answer()


# ── Adminlar ro'yxati ────────────────────────────────────────
@router.callback_query(OwnerStates.menu, F.data == "ow:admins")
async def ow_admins(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    admins = await db.get_all_admins()
    if not admins:
        await cb.answer("Hozircha sub-admin yo'q.", show_alert=True)
        return

    rows = []
    for a in admins:
        name = a.get("full_name") or a.get("username") or str(a["telegram_id"])
        rows.append([
            InlineKeyboardButton(text=f"👤 {name}", callback_data=f"ow:noop"),
            InlineKeyboardButton(text="❌ O'chirish", callback_data=f"ow:del_admin:{a['telegram_id']}"),
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data="ow:back")])

    await cb.message.edit_text(
        f"👥 <b>Sub-adminlar ({len(admins)} ta):</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(OwnerStates.menu, F.data.startswith("ow:del_admin:"))
async def ow_del_admin(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    admin_id = int(cb.data.split(":")[2])
    await db.remove_admin(admin_id)
    try:
        await cb.bot.send_message(admin_id, "ℹ️ Sizning admin huquqingiz olib tashlandi.")
    except Exception:
        pass
    await cb.answer("✅ O'chirildi.", show_alert=True)
    # Ro'yxatni yangilash
    await ow_admins(cb)


# ── Admin qo'shish ───────────────────────────────────────────
@router.callback_query(OwnerStates.menu, F.data == "ow:add_admin")
async def ow_add_admin_start(cb: CallbackQuery, state: FSMContext):
    if not is_owner(cb.from_user.id): return
    await cb.message.edit_text(
        "➕ <b>Admin qo'shish</b>\n\n"
        "Yangi adminning <b>Telegram ID</b> raqamini yozing:\n\n"
        "<i>ID ni bilish uchun: @userinfobot ga yozing</i>",
        parse_mode="HTML",
    )
    await state.set_state(OwnerStates.add_admin)
    await cb.answer()


@router.message(OwnerStates.add_admin)
async def ow_add_admin(msg: Message, state: FSMContext):
    if not is_owner(msg.from_user.id): return
    if msg.text == "❌ Bekor qilish":
        await state.set_state(OwnerStates.menu)
        await msg.answer("Bekor qilindi.")
        return

    text = msg.text.strip().lstrip("@")
    if not text.isdigit():
        await msg.answer("❗ Faqat raqamli Telegram ID yozing.\nMasalan: <code>495165857</code>", parse_mode="HTML")
        return

    new_id = int(text)
    if new_id in OWNER_IDS:
        await msg.answer("Bu siz — owner siz allaqachon.")
        return

    # Foydalanuvchi ma'lumotini olishga urinish
    user = await db.get_user(new_id)
    full_name = user.get("full_name", "") if user else ""
    username  = user.get("username", "") if user else ""

    await db.add_admin(new_id, full_name, username, added_by=msg.from_user.id)

    # Yangi adminga xabar
    try:
        await msg.bot.send_message(
            new_id,
            "✅ Siz bot admini sifatida qo'shildingiz!\n\n"
            "/admin buyrug'i orqali admin panelga kiring.",
        )
    except Exception:
        pass

    name_display = f"@{username}" if username else (full_name or str(new_id))
    await msg.answer(
        f"✅ <b>{name_display}</b> admin sifatida qo'shildi!",
        parse_mode="HTML",
    )
    await state.set_state(OwnerStates.menu)
    await msg.answer("👑 Super-admin panel:", reply_markup=owner_menu_kb())


# ── Notariat zayavkalari ────────────────────────────────────
@router.callback_query(OwnerStates.menu, F.data == "ow:notary")
async def ow_notary(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return

    nstats = await db.get_notary_stats()
    orders = await db.get_notary_orders(limit=10)

    STATUS = {
        "new":           "🆕",
        "payment_check": "💳",
        "processing":    "⚙️",
        "done":          "✅",
        "rejected":      "❌",
    }

    text = (
        "📜 <b>Notariat zayavkalari</b>\n\n"
        f"🆕 Yangi: <b>{nstats['new']}</b>  "
        f"💳 To'lov: <b>{nstats['payment_check']}</b>  "
        f"✅ Bajarildi: <b>{nstats['done']}</b>\n\n"
    )

    rows = []
    for o in orders:
        icon   = STATUS.get(o["status"], "❓")
        doc    = o.get("doc_type", "")
        uid    = o.get("user_id", "")
        oid    = o["id"]
        text  += f"{icon} <b>#{oid}</b> — {doc} | user:{uid}\n"
        rows.append([
            InlineKeyboardButton(
                text=f"{icon} #{oid} — {doc}",
                callback_data=f"ow:not_detail:{oid}"
            )
        ])

    rows.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data="ow:back")])
    await cb.message.edit_text(
        text or "Zayavkalar yo'q.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(OwnerStates.menu, F.data.startswith("ow:not_detail:"))
async def ow_notary_detail(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    order_id = int(cb.data.split(":")[2])
    order = await db.get_notary_order(order_id)
    if not order:
        await cb.answer("Topilmadi.", show_alert=True); return

    admins = await db.get_all_admins()
    STATUS = {
        "new": "🆕 Yangi", "payment_check": "💳 To'lov tekshiruvida",
        "processing": "⚙️ Jarayonda", "done": "✅ Bajarildi", "rejected": "❌ Rad etildi",
    }
    text = (
        f"📜 <b>Zayavka #{order_id}</b>\n\n"
        f"👤 User ID: <code>{order['user_id']}</code>\n"
        f"📋 Hujjat turi: <b>{order.get('doc_type', '')}</b>\n"
        f"📊 Status: <b>{STATUS.get(order['status'], order['status'])}</b>\n"
        f"🔧 Tayinlangan: <code>{order.get('assigned_to') or '—'}</code>\n"
        f"📅 Sana: {order.get('created_at', '')[:16]}\n"
    )
    if order.get("admin_note"):
        text += f"📝 Izoh: {order['admin_note']}\n"

    # Tayinlash tugmalari
    assign_rows = []
    for a in admins:
        name = a.get("full_name") or a.get("username") or str(a["telegram_id"])
        assign_rows.append([
            InlineKeyboardButton(
                text=f"👤 {name} ga tayinlash",
                callback_data=f"ow:not_assign:{order_id}:{a['telegram_id']}"
            )
        ])

    action_rows = [
        [InlineKeyboardButton(text="✅ Qabul",   callback_data=f"ow:not_act:approve:{order_id}"),
         InlineKeyboardButton(text="❌ Rad",     callback_data=f"ow:not_act:reject:{order_id}")],
        [InlineKeyboardButton(text="✔️ Bajarildi", callback_data=f"ow:not_act:done:{order_id}")],
        [InlineKeyboardButton(text="⬅️ Ortga",  callback_data="ow:notary")],
    ]

    await cb.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=assign_rows + action_rows),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(OwnerStates.menu, F.data.startswith("ow:not_assign:"))
async def ow_notary_assign(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    parts    = cb.data.split(":")
    order_id = int(parts[2])
    admin_id = int(parts[3])

    await db.update_notary_order(order_id, "processing", assigned_to=admin_id)

    order = await db.get_notary_order(order_id)
    if order:
        try:
            await cb.bot.send_message(
                admin_id,
                f"📜 <b>Notariat zayavkasi #{order_id} sizga tayinlandi!</b>\n\n"
                f"Hujjat turi: <b>{order.get('doc_type', '')}</b>\n"
                f"User ID: <code>{order['user_id']}</code>\n\n"
                "Zayavkani ko'rib chiqib, foydalanuvchiga javob bering.",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await cb.answer(f"✅ Admin #{admin_id} ga tayinlandi!", show_alert=True)
    await ow_notary_detail(cb)


@router.callback_query(OwnerStates.menu, F.data.startswith("ow:not_act:"))
async def ow_notary_action(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    parts    = cb.data.split(":")
    action   = parts[2]
    order_id = int(parts[3])

    action_map = {
        "approve": ("payment_check", "✅ To'lov qabul qilindi"),
        "done":    ("done",          "✔️ Bajarildi"),
        "reject":  ("rejected",      "❌ Rad etildi"),
    }
    if action not in action_map:
        await cb.answer(); return

    new_status, label = action_map[action]
    await db.update_notary_order(order_id, new_status, assigned_to=cb.from_user.id)

    order = await db.get_notary_order(order_id)
    user_msgs = {
        "payment_check": f"✅ <b>Zayavka #{order_id}: to'lovingiz qabul qilindi!</b>\n\nHujjatingiz ko'rib chiqilmoqda.",
        "done":          f"✅ <b>Zayavka #{order_id} bajarildi!</b>\n\nHujjatingiz tayyor. Notarius siz bilan bog'lanadi.",
        "rejected":      f"❌ <b>Zayavka #{order_id} rad etildi.</b>\n\nQayta murojaat: /notary",
    }
    if order:
        try:
            await cb.bot.send_message(
                order["user_id"], user_msgs.get(new_status, ""), parse_mode="HTML"
            )
        except Exception:
            pass

    await cb.answer(label, show_alert=True)
    await ow_notary(cb)


# ── Tashkilotlar (owner dan boshqarish) ─────────────────────
@router.callback_query(OwnerStates.menu, F.data == "ow:orgs")
async def ow_orgs(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    orgs = await db.get_all_orgs()
    text = f"🏢 <b>Tashkilotlar ({len(orgs)} ta)</b>\n\n"
    if not orgs:
        text += "Hozircha yo'q.\n/org_add buyrug'i bilan qo'shing."
    else:
        from handlers.organizations import ORG_CATEGORIES, CAT_ICONS
        for o in orgs[:20]:
            icon   = CAT_ICONS.get(o.get("category",""), "🏢")
            status = "✅" if o.get("active") else "❌"
            text  += f"{status} {icon} <b>{o['name']}</b> — {o.get('address','')}\n"

    await cb.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Qo'shish (admin panelda /org_add)", callback_data="ow:noop")],
            [InlineKeyboardButton(text="⬅️ Ortga", callback_data="ow:back")],
        ]),
        parse_mode="HTML",
    )
    await cb.answer()


# ── Takliflar ────────────────────────────────────────────────
@router.callback_query(OwnerStates.menu, F.data == "ow:feedback")
async def ow_feedback(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    feedbacks = await db.get_feedback_list(limit=10)
    if not feedbacks:
        await cb.answer("Hozircha takliflar yo'q.", show_alert=True)
        return
    text = "💬 <b>So'nggi takliflar:</b>\n\n"
    for f in feedbacks:
        text += (
            f"<b>{f.get('label','')}</b> — {f.get('sender','')}\n"
            f"{f.get('text','')}\n"
            f"<i>{f.get('created_at','')}</i>\n\n"
        )
    await cb.message.edit_text(text, reply_markup=owner_menu_kb(), parse_mode="HTML")
    await cb.answer()


# ── Ortga ────────────────────────────────────────────────────
@router.callback_query(OwnerStates.menu, F.data == "ow:back")
async def ow_back(cb: CallbackQuery):
    await cb.message.edit_text("👑 <b>Super-admin panel</b>", reply_markup=owner_menu_kb(), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "ow:noop")
async def ow_noop(cb: CallbackQuery):
    await cb.answer()
