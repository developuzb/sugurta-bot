import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import API_TOKEN
from database.db import init_db
from database.db import init_postgres
from handlers.start import router as start_router
from handlers.insurance import router as insurance_router
from handlers.bonus import router as bonus_router
from handlers.group import router as group_router
from handlers.common import router as common_router

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


# ---------------- BOT ----------------
bot = Bot(token=API_TOKEN)
dp = Dispatcher()


# ---------------- MAIN ----------------
async def main():
    try:
        await init_db()

        dp.include_router(start_router)
        dp.include_router(insurance_router)
        dp.include_router(bonus_router)
        dp.include_router(group_router)
        dp.include_router(common_router)
        
        logger.info("Bot ishga tushmoqda...")

        await init_postgres()
        
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"Main error: {e}", exc_info=True)


# ---------------- RUN ----------------
if __name__ == "__main__":
    asyncio.run(main())