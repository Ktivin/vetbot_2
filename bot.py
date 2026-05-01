import asyncio
import logging
import os
import socket
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import BOT_TOKEN, BUSINESS_TIMEZONE
from database import (
    delete_old_consultations,
    get_consultations,
    has_reminder_sent,
    init_db,
    mark_reminder_sent,
)
from handlers import admin, client, specialist, start
from handlers.errors import register_global_error_handler
from integrations.google_sheets_consultations import (
    acquire_polling_lock,
    get_polling_lock_details,
    release_polling_lock,
    refresh_polling_lock,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def send_due_booking_reminders(bot: Bot) -> None:
    current_time = datetime.now(BUSINESS_TIMEZONE)
    try:
        records = await get_consultations("all")
    except Exception:
        logger.exception("Не вдалося отримати записи для нагадувань.")
        return

    for record in records:
        if record.get("status") not in {"pending", "confirmed"}:
            continue
        try:
            record_dt = datetime.fromisoformat(f"{record['date']}T{record['time']}:00").replace(
                tzinfo=BUSINESS_TIMEZONE
            )
        except (KeyError, ValueError):
            continue

        delta = record_dt - current_time
        reminder_type = ""
        if timedelta(hours=23, minutes=30) <= delta <= timedelta(hours=24, minutes=30):
            reminder_type = "24h"
        elif timedelta(hours=2, minutes=30) <= delta <= timedelta(hours=3, minutes=30):
            reminder_type = "3h"
        if not reminder_type:
            continue

        if await has_reminder_sent(record["id"], reminder_type):
            continue

        reminder_text = (
            "Нагадуємо про запис.\n\n"
            f"Фахівець: {record['specialist']}\n"
            f"Дата: {record['date']}\n"
            f"Час: {record['time']}\n\n"
            "Якщо потрібно уточнити деталі, відкрийте чат з адміністратором."
        )
        try:
            await bot.send_message(record["user_id"], reminder_text)
            await mark_reminder_sent(record["id"], reminder_type)
        except Exception:
            logger.exception("Не вдалося надіслати нагадування для запису %s.", record.get("id"))


async def _polling_lock_heartbeat(owner: str, interval_seconds: int = 45) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        refreshed = await refresh_polling_lock(owner)
        if not refreshed:
            logger.error("Не вдалося продовжити polling lock для інстансу %s.", owner)
            return


async def main():
    await init_db()
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    register_global_error_handler(dp)

    # Порядок роутерів важливий.
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(client.router)
    dp.include_router(specialist.router)

    # Планувальник для щоденної автоочистки записів.
    scheduler = AsyncIOScheduler(timezone=BUSINESS_TIMEZONE)
    scheduler.add_job(
        delete_old_consultations,
        CronTrigger(hour=3, minute=0),
        id="cleanup_old_records",
    )
    scheduler.add_job(
        send_due_booking_reminders,
        "interval",
        minutes=30,
        id="booking_reminders",
        args=[bot],
    )
    instance_owner = f"{socket.gethostname()}:{os.getpid()}"
    has_lock = await acquire_polling_lock(instance_owner)
    if not has_lock:
        lock_details = await get_polling_lock_details()
        current_owner = (lock_details or {}).get("owner", "")
        expires_at = (lock_details or {}).get("expires_at", "")
        logger.error(
            "Запуск зупинено: інший інстанс уже обробляє polling для цього бота. "
            "Поточний власник lock: %s. Lock активний до: %s.",
            current_owner or "невідомо",
            expires_at or "невідомо",
        )
        await bot.session.close()
        return

    heartbeat_task = asyncio.create_task(_polling_lock_heartbeat(instance_owner))
    scheduler_started = False

    try:
        scheduler.start()
        scheduler_started = True
        logger.info("Автоочистку записів заплановано щодня о 03:00.")
        logger.info("Бота запущено.")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    except KeyboardInterrupt:
        logger.info("Бота зупинено вручну.")
    except Exception:
        logger.exception("Бот завершив роботу через неочікувану помилку.")
        raise
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        await release_polling_lock(instance_owner)
        if scheduler_started:
            scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
