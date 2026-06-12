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


def main_menu_kb(role: str = "buyer", is_owner: bool = False) -> ReplyKeyboardMarkup:
    owner_row = [[KeyboardButton(text="👑 Boshqaruv paneli")]] if is_owner else []

    if role == "seller":
        return ReplyKeyboardMarkup(
            keyboard=owner_row + [
                [KeyboardButton(text="➕ E'lon joylash")],
                [KeyboardButton(text="📋 Mening e'lonlarim"), KeyboardButton(text="🔍 Qidirish")],
                [KeyboardButton(text="📜 Uy hujjatlarini tekshirish"), KeyboardButton(text="🏢 Tashkilotlar")],
                [KeyboardButton(text="❤️ Sevimlilar")],
                [KeyboardButton(text="💬 Fikr va takliflar")],
            ],
            resize_keyboard=True,
        )
    return ReplyKeyboardMarkup(
        keyboard=owner_row + [
            [KeyboardButton(text="🔍 Uy qidirish")],
            [KeyboardButton(text="❤️ Sevimlilar")],
            [KeyboardButton(text="➕ E'lon joylash")],
            [KeyboardButton(text="📜 Uy hujjatlarini tekshirish"), KeyboardButton(text="🏢 Tashkilotlar")],
            [KeyboardButton(text="💬 Fikr va takliflar")],
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
