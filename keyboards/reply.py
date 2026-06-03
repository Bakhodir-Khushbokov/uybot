from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
    )


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📲 Raqamimni yuborish", request_contact=True)],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )


def location_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Joylashuvni ulashish", request_location=True)],
            [KeyboardButton(text="➡️ O'tkazib yuborish")],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )


def main_menu_kb(role: str = "buyer") -> ReplyKeyboardMarkup:
    if role == "seller":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="➕ E'lon joylash")],
                [KeyboardButton(text="📋 Mening e'lonlarim"), KeyboardButton(text="🔍 Qidirish")],
                [KeyboardButton(text="❤️ Sevimlilar"),        KeyboardButton(text="❓ Yordam")],
            ],
            resize_keyboard=True,
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Uy qidirish")],
            [KeyboardButton(text="❤️ Sevimlilar"), KeyboardButton(text="📂 Qidiruv tarixi")],
            [KeyboardButton(text="➕ E'lon joylash"), KeyboardButton(text="❓ Yordam")],
        ],
        resize_keyboard=True,
    )


def skip_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➡️ O'tkazib yuborish")],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )
