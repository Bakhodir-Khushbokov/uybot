from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from handlers.states import RegStates, SellerStates
from keyboards.inline import lang_kb, role_kb
from keyboards.reply  import phone_kb, main_menu_kb, cancel_kb
from config import OWNER_IDS
import database as db

router = Router()

WELCOME = (
    "Assalomu alaykum! 👋 <b>Uy Bozori</b> botiga xush kelibsiz!\n\n"
    "Здравствуйте! 👋 Добро пожаловать в бот <b>Uy Bozori</b>!"
)


# ── /start ────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(msg.from_user.id)
    if user and user.get("phone"):
        role = user.get("role", "buyer")
        await msg.answer(
            f"Xush kelibsiz, <b>{msg.from_user.first_name}</b>! 👋",
            reply_markup=main_menu_kb(role, is_owner=msg.from_user.id in OWNER_IDS),
        )
        return

    await msg.answer(WELCOME, reply_markup=lang_kb(), parse_mode="HTML")
    await state.set_state(RegStates.language)


# ── Til tanlash ──────────────────────────────────────────────
@router.callback_query(RegStates.language, F.data.startswith("lang:"))
async def choose_lang(cb: CallbackQuery, state: FSMContext):
    lang = cb.data.split(":")[1]
    await state.update_data(language=lang)
    await db.upsert_user(cb.from_user.id, language=lang,
                         full_name=cb.from_user.full_name,
                         username=cb.from_user.username)
    await cb.message.edit_text(
        "📱 Telefon raqamingizni yuboring.\n"
        "Quyidagi tugmani bosing — bot avtomatik oladi.",
        parse_mode="HTML",
    )
    await cb.message.answer("👇", reply_markup=phone_kb())
    await state.set_state(RegStates.phone)
    await cb.answer()


# ── Telefon ──────────────────────────────────────────────────
@router.message(RegStates.phone, F.contact)
async def got_phone(msg: Message, state: FSMContext):
    phone = msg.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    await state.update_data(phone=phone)
    await db.upsert_user(msg.from_user.id, phone=phone)
    await msg.answer(
        "✅ Raqam saqlandi!\n\nSiz kim sifatida keldingiz?",
        reply_markup=role_kb(),
    )
    await state.set_state(RegStates.role)


@router.message(RegStates.phone)
async def phone_not_shared(msg: Message):
    if msg.text == "❌ Bekor qilish":
        return
    await msg.answer("Raqamsiz davom etib bo'lmaydi. Iltimos, tugmani bosing 👇")


# ── Rol ──────────────────────────────────────────────────────
@router.callback_query(RegStates.role, F.data.startswith("role:"))
async def choose_role(cb: CallbackQuery, state: FSMContext):
    role = cb.data.split(":")[1]
    await db.upsert_user(cb.from_user.id, role=role)
    await state.update_data(role=role)
    await state.clear()

    await cb.message.edit_text("✅ Ro'yxatdan o'tdingiz!")
    await cb.message.answer(
        "Asosiy menyu 👇",
        reply_markup=main_menu_kb(role, is_owner=cb.from_user.id in OWNER_IDS),
    )
    await cb.answer()


# ── Bekor qilish ─────────────────────────────────────────────
@router.message(F.text == "❌ Bekor qilish")
async def cancel_any(msg: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(msg.from_user.id)
    role = user.get("role", "buyer") if user else "buyer"
    await msg.answer("Bekor qilindi.", reply_markup=main_menu_kb(role, is_owner=msg.from_user.id in OWNER_IDS))


# ── /help ────────────────────────────────────────────────────
@router.message(Command("help"))
@router.message(F.text == "❓ Yordam")
async def cmd_help(msg: Message):
    await msg.answer(
        "ℹ️ <b>Uy Bozori Bot</b>\n\n"
        "🏷 E'lon joylash uchun: <b>➕ E'lon joylash</b>\n"
        "🔍 Qidirish uchun: <b>🔍 Uy qidirish</b>\n"
        "❤️ Sevimlilar: <b>❤️ Sevimlilar</b>\n\n"
        "Muammo bo'lsa — /start bosing.",
        parse_mode="HTML",
    )


# ── Yordam callback ──────────────────────────────────────────
@router.callback_query(F.data.startswith("help:"))
async def help_cb(cb: CallbackQuery):
    topic = cb.data.split(":")[1]
    texts = {
        "property_type": "Nima sotmoqchisiz? Hovli, kvartira, ofis yoki yer — birini tanlang.",
        "dom_type":      "Novostroyka — yangi qurilish. Eski dom — ilgari odamlar yashagan.",
        "location":      "Uyingiz qayerda? Viloyat → Tuman → Mahalla tartibida tanlang.",
        "renovation":    "Evro — yuqori sifat. O'rta — oddiy. Qora — ta'mirsiz. Muallim — yangi qurilish ta'mirsiz.",
        "price":         "Dollar: 47.500 yozing — bot 47.500$ ko'rsatadi.\nSo'm: 350 yozing — bot 350 mln ko'rsatadi.",
        "xonalar":       "Nechta xona bor? 1, 2, 3, 4 yoki 4+ dan birini tanlang.",
    }
    await cb.answer(texts.get(topic, "Yordam mavjud emas."), show_alert=True)


# ── Ismni tahrirlash ─────────────────────────────────────────
@router.message(F.text == "✏️ Ismni tahrirlash")
async def edit_name_start(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("✏️ Yangi ismingizni yozing (masalan: Ali yoki Ali Karimov):")
    await state.set_state(SellerStates.display_name_edit)
