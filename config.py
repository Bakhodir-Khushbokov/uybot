import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
DB_PATH     = os.getenv("DB_PATH", "uy_bot.db")
ADMIN_IDS   = [int(i) for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip().isdigit()]

# E'lon limiti (oddiy foydalanuvchi)
DAILY_LISTING_LIMIT = 3

# Taqiqlangan so'zlar (katta-kichik harf farqi yo'q)
BANNED_WORDS = [
    "ipoteka", "ипотека",
    "kredit", "кредит", "credit",
    "bank", "банк",
    "cherez bank", "через банк",
    "рассрочка", "rassrochka",
]
