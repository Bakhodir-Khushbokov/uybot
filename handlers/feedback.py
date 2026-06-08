"""
Foydalanuvchilardan fikr, taklif, shikoyat qabul qilish.

Oqim:
  Foydalanuvchi → yozadi → feedback kanaliga tushadi + ownerga xabar
  Owner → "💬 Javob berish" tugmasi → javob yozadi → foydalanuvchiga boradi
"""
import datetime
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import OWNER_IDS, FEEDBACK_CHANNEL_ID
from keyboards.inline import kb
from keyboards.reply import cancel_kb, main_menu_kb
import database as db

router = Router()


class FeedbackStates(StatesGroup):
    choose_type = State()
    writing     = State()


class FeedbackReplyStates(StatesGroup):
    replying = State()   # owner javob yozmoqda


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


# ── Foydalanuvchi oqimi ───────────────────────────────────────

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
    await cb.message.edit_text(f"{label}\n\n✍️ Xabaringizni yozing:")
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

    data  = await state.get_data()
    label = data.get("feedback_label", "Xabar")
    sender = f"@{msg.from_user.username}" if msg.from_user.username else f"ID:{msg.from_user.id}"
    now   = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')

    # DB ga saqlash
    await db.save_feedback(msg.from_user.id, sender, label, msg.text)

    # Feedback kanaliga yuborish (javob tugmasi bilan)
    channel_text = (
        f"{label}\n"
        f"👤 {sender} | {msg.from_user.full_name}\n"
        f"🕐 {now}\n\n"
        f"{msg.text}"
    )
    reply_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💬 Javob berish",
            callback_data=f"fb_reply:{msg.from_user.id}"
        )]
    ])

    if FEEDBACK_CHANNEL_ID:
        try:
            await msg.bot.send_message(
                FEEDBACK_CHANNEL_ID,
                channel_text,
                reply_markup=reply_btn,
                parse_mode=None,
            )
        except Exception:
            pass

    # Faqat ownerlarga xabar
    for owner_id in OWNER_IDS:
        try:
            await msg.bot.send_message(
                owner_id,
                f"📨 <b>Yangi {label}</b>\n"
                f"👤 {sender} | {msg.from_user.full_name}\n\n"
                f"{msg.text}",
                reply_markup=reply_btn,
                parse_mode="HTML",
            )
        except Exception:
            pass

    user = await db.get_user(msg.from_user.id)
    role = user["role"] if user else "buyer"
    await msg.answer(
        "✅ Xabaringiz yuborildi!\n\nRahmat, fikringiz bizga muhim 🙏",
        reply_markup=main_menu_kb(role),
    )
    await state.clear()


# ── Owner javob oqimi ─────────────────────────────────────────

@router.callback_query(F.data.startswith("fb_reply:"))
async def fb_reply_start(cb: CallbackQuery, state: FSMContext):
    user_id = int(cb.data.split(":")[1])

    # Faqat ownerlar javob bera oladi
    if cb.from_user.id not in OWNER_IDS:
        await cb.answer("Sizda ruxsat yo'q.", show_alert=True)
        return

    await state.update_data(reply_to_user_id=user_id)
    await state.set_state(FeedbackReplyStates.replying)
    await cb.message.answer(
        "✍️ Javob matnini yozing:\n\n"
        "(Foydalanuvchiga bot nomidan yuboriladi)",
        reply_markup=cancel_kb(),
    )
    await cb.answer()


@router.message(FeedbackReplyStates.replying)
async def fb_reply_send(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi.", reply_markup=cancel_kb())
        return

    data = await state.get_data()
    user_id = data.get("reply_to_user_id")

    try:
        await msg.bot.send_message(
            user_id,
            f"📩 <b>UyJoy botidan xabar:</b>\n\n"
            f"{msg.text}",
            parse_mode="HTML",
        )
        await msg.answer("✅ Javob yuborildi!")
    except Exception:
        await msg.answer("❌ Foydalanuvchiga yuborib bo'lmadi (bot bloklangan bo'lishi mumkin).")

    await state.clear()
