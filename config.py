import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
DB_PATH     = os.getenv("DB_PATH", "uy_bot.db")
ADMIN_IDS        = [int(i) for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip().isdigit()]
OWNER_IDS        = [int(i) for i in os.getenv("OWNER_IDS", os.getenv("ADMIN_IDS", "")).split(",") if i.strip().isdigit()]
MEDIA_CHANNEL_ID    = int(os.getenv("MEDIA_CHANNEL_ID",    "0"))  # eski, backwards compat
LISTINGS_CHANNEL_ID = int(os.getenv("LISTINGS_CHANNEL_ID", os.getenv("MEDIA_CHANNEL_ID", "0")))
NOTARY_CHANNEL_ID   = int(os.getenv("NOTARY_CHANNEL_ID",   os.getenv("MEDIA_CHANNEL_ID", "0")))
ORGS_CHANNEL_ID     = int(os.getenv("ORGS_CHANNEL_ID",     os.getenv("MEDIA_CHANNEL_ID", "0")))
DONATION_CARD    = os.getenv("DONATION_CARD", "")

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
