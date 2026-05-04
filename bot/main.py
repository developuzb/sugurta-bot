import asyncio
import logging

from aiogram import Bot, Dispatcher
from handlers.nasiya import router as nasiya_router
from config import API_TOKEN
from database.db import init_db, init_postgres
from handlers.start import router as start_router
from handlers.insurance import router as insurance_router
from handlers.bonus import router as bonus_router
from handlers.group import router as group_router
from handlers.common import router as common_router
from handlers.stale_session import router as stale_router
from handlers.reminder import router as reminder_router        # ✅ YANGI

from middlewares.activity import ActivityMiddleware
from services.scheduler import reminder_scheduler              # ✅ YANGI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()


async def main():
    try:
        await init_db()

        # Middleware
        dp.message.middleware(ActivityMiddleware())
        dp.callback_query.middleware(ActivityMiddleware())

        # Router'lar — TARTIB MUHIM
        dp.include_router(stale_router)
        dp.include_router(start_router)
        dp.include_router(reminder_router)        # ✅ insurance dan oldin
        dp.include_router(insurance_router)
        dp.include_router(nasiya_router)
        dp.include_router(bonus_router)
        dp.include_router(group_router)
        dp.include_router(common_router)          # ⚠️ ENG OXIRIDA

        logger.info("Bot ishga tushmoqda...")
        await init_postgres()

        # ✅ Background scheduler — har soat tekshiradi
        asyncio.create_task(reminder_scheduler(bot))

        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"Main error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())