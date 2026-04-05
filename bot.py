import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import BOT_TOKEN, BUSINESS_TIMEZONE
from database import delete_old_consultations, init_db
from handlers import admin, specialist, start
from handlers.errors import register_global_error_handler


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    await init_db()
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    register_global_error_handler(dp)

    # Порядок важливий.
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(specialist.router)

    # === Налаштування планувальника ===
    scheduler = AsyncIOScheduler(timezone=BUSINESS_TIMEZONE)
    scheduler.add_job(
        delete_old_consultations,
        CronTrigger(hour=3, minute=0),
        id="cleanup_old_records",
    )
    scheduler.start()
    logger.info("Автоочистку записів заплановано щодня о 03:00.")

    try:
        logger.info("Бот запущено.")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    except KeyboardInterrupt:
        logger.info("Бот зупинено вручну.")
    except Exception:
        logger.exception("Бот завершив роботу через неочікувану помилку.")
        raise
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
