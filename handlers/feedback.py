"""
Foydalanuvchilardan fikr, taklif, shikoyat qabul qilish.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
from keyboards.inline import kb
from keyboards.reply import cancel_kb, main_menu_kb
import database as db

router = Router()


class FeedbackStates(StatesGroup):
    choose_type = State()
    writing     = State()


FEEDBACK_TYPES = {
    "fikr":    "💬 Fikr / Taassurot",
    "taklif":  "💡 Taklif",
    "shikoyat":"🚨 Shikoyat",
    "loyiha":  "🚀 Loyiha uchun g'oya",
}


def feedback_type_kb():
    return kb(
        [("💬 Fikr / Taassurot", "fb:fikr")],
        [("💡 Taklif",           "fb:taklif")],
        [("🚨 Shikoyat",         "fb:shikoyat")],
        [("🚀 Loyiha uchun g'oya","fb:loyiha")],
    )


@router.message(F.text == "💬 Fikr va takliflar")
async def feedback_start(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer(
        "💬 <b>Fikr va takliflar</b>\n\n"
        "Qaysi mavzuda xabar yubormoqchisiz?",
        reply_markup=feedback_type_kb(),
        parse_mode="HTML",
    )
    await state.set_state(FeedbackStates.choose_type)


@router.callback_query(FeedbackStates.choose_type, F.data.startswith("fb:"))
async def feedback_type_chosen(cb: CallbackQuery, state: FSMContext):
    ftype = cb.data.split(":")[1]
    label = FEEDBACK_TYPES.get(ftype, "Xabar")
    await state.update_data(feedback_type=ftype, feedback_label=label)
    await cb.message.edit_text(
        f"{label}\n\n✍️ Xabaringizni yozing:",
    )
    await cb.message.answer("Bekor qilish uchun:", reply_markup=cancel_kb())
    await state.set_state(FeedbackStates.writing)
    await cb.answer()


@router.message(FeedbackStates.writing)
async def feedback_text(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        from aiogram.utils.keyboard import ReplyKeyboardRemove
        await msg.answer("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
        return

    data = await state.get_data()
    label = data.get("feedback_label", "Xabar")
    sender = f"@{msg.from_user.username}" if msg.from_user.username else f"#{msg.from_user.id}"

    # DB ga saqlash
    await db.save_feedback(msg.from_user.id, sender, label, msg.text)

    # Adminga yuborish (config + DB adminlar)
    admin_text = (
        f"📨 <b>{label}</b>\n"
        f"Kim: {sender} | {msg.from_user.full_name}\n\n"
        f"{msg.text}"
    )
    db_admin_ids = await db.get_admin_ids()
    all_admin_ids = list(set(ADMIN_IDS + db_admin_ids))
    for admin_id in all_admin_ids:
        try:
            await msg.bot.send_message(admin_id, admin_text, parse_mode="HTML")
        except Exception:
            pass

    await msg.answer(
        "✅ Xabaringiz adminga yuborildi!\n\nRahmat, fikringiz bizga muhim 🙏",
        reply_markup=cancel_kb(),
    )
    await state.clear()
