"""
Uy Bozori Bot — kirish nuqtasi.
Ishga tushirish: python main.py
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from database import init_db
from handlers import main_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    # DB ni ishga tushir
    await init_db()
    logger.info("✅ Database tayyor.")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Bot username ni watermark uchun o'rnatish
    bot_info = await bot.get_me()
    from utils.watermark import set_watermark_text
    set_watermark_text(f"@{bot_info.username}")
    logger.info(f"🖼 Watermark: @{bot_info.username}")

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(main_router)

    logger.info("🤖 Bot ishga tushdi. Ctrl+C bilan to'xtating.")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
