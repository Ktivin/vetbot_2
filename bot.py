import asyncio
import logging
import os
import socket

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import BOT_TOKEN, BUSINESS_TIMEZONE
from database import delete_old_consultations, init_db
from handlers import admin, specialist, start
from handlers.errors import register_global_error_handler
from integrations.google_sheets_consultations import (
    acquire_polling_lock,
    release_polling_lock,
    refresh_polling_lock,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def _polling_lock_heartbeat(owner: str, interval_seconds: int = 45) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        refreshed = await refresh_polling_lock(owner)
        if not refreshed:
            logger.error("Р СњР Вµ Р Р†Р Т‘Р В°Р В»Р С•РЎРѓРЎРЏ Р С—РЎР‚Р С•Р Т‘Р С•Р Р†Р В¶Р С‘РЎвЂљР С‘ polling lock Р Т‘Р В»РЎРЏ РЎвЂ“Р Р…РЎРѓРЎвЂљР В°Р Р…РЎРѓРЎС“ %s.", owner)


async def main():
    await init_db()
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    register_global_error_handler(dp)

    # Р СџР С•РЎР‚РЎРЏР Т‘Р С•Р С” Р Р†Р В°Р В¶Р В»Р С‘Р Р†Р С‘Р в„–.
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(specialist.router)

    # === Р СњР В°Р В»Р В°РЎв‚¬РЎвЂљРЎС“Р Р†Р В°Р Р…Р Р…РЎРЏ Р С—Р В»Р В°Р Р…РЎС“Р Р†Р В°Р В»РЎРЉР Р…Р С‘Р С”Р В° ===
    scheduler = AsyncIOScheduler(timezone=BUSINESS_TIMEZONE)
    scheduler.add_job(
        delete_old_consultations,
        CronTrigger(hour=3, minute=0),
        id="cleanup_old_records",
    )
    scheduler.start()
    logger.info("Р С’Р Р†РЎвЂљР С•Р С•РЎвЂЎР С‘РЎРѓРЎвЂљР С”РЎС“ Р В·Р В°Р С—Р С‘РЎРѓРЎвЂ“Р Р† Р В·Р В°Р С—Р В»Р В°Р Р…Р С•Р Р†Р В°Р Р…Р С• РЎвЂ°Р С•Р Т‘Р Р…РЎРЏ Р С• 03:00.")
    instance_owner = f"{socket.gethostname()}:{os.getpid()}"
    has_lock = await acquire_polling_lock(instance_owner)
    if not has_lock:
        logger.error(
            "Р—Р°РїСѓСЃРє Р·СѓРїРёРЅРµРЅРѕ: С–РЅС€РёР№ С–РЅСЃС‚Р°РЅСЃ СѓР¶Рµ РѕР±СЂРѕР±Р»СЏС” polling РґР»СЏ С†СЊРѕРіРѕ Р±РѕС‚Р°. "
            "Р—Р°Р»РёС€С‚Рµ Р°РєС‚РёРІРЅРёРј Р»РёС€Рµ РѕРґРёРЅ Р·Р°РїСѓСЃРє."
        )
        scheduler.shutdown(wait=False)
        await bot.session.close()
        return

    heartbeat_task = asyncio.create_task(_polling_lock_heartbeat(instance_owner))


    try:
        logger.info("Р вЂР С•РЎвЂљ Р В·Р В°Р С—РЎС“РЎвЂ°Р ВµР Р…Р С•.")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    except KeyboardInterrupt:
        logger.info("Р вЂР С•РЎвЂљ Р В·РЎС“Р С—Р С‘Р Р…Р ВµР Р…Р С• Р Р†РЎР‚РЎС“РЎвЂЎР Р…РЎС“.")
    except Exception:
        logger.exception("Р вЂР С•РЎвЂљ Р В·Р В°Р Р†Р ВµРЎР‚РЎв‚¬Р С‘Р Р† РЎР‚Р С•Р В±Р С•РЎвЂљРЎС“ РЎвЂЎР ВµРЎР‚Р ВµР В· Р Р…Р ВµР С•РЎвЂЎРЎвЂ“Р С”РЎС“Р Р†Р В°Р Р…РЎС“ Р С—Р С•Р СР С‘Р В»Р С”РЎС“.")
        raise
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        await release_polling_lock(instance_owner)
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
