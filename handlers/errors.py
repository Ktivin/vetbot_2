import logging
from contextlib import suppress

from aiogram import Dispatcher
from aiogram.types import ErrorEvent, InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN_USER_IDS
from texts import ADMIN_MENU_BUTTON, GENERIC_ERROR_MESSAGE, USER_BOOKINGS_MENU_BUTTON


logger = logging.getLogger(__name__)


def _recovery_keyboard(user_id: int | None = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=USER_BOOKINGS_MENU_BUTTON, callback_data="home:main")]]
    if user_id in ADMIN_USER_IDS:
        rows.append([InlineKeyboardButton(text=ADMIN_MENU_BUTTON, callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def register_global_error_handler(dp: Dispatcher) -> None:
    @dp.error()
    async def global_error_handler(event: ErrorEvent):
        logger.error(
            "Необроблена помилка під час обробки оновлення.",
            exc_info=(
                type(event.exception),
                event.exception,
                event.exception.__traceback__,
            ),
        )

        if event.update.message:
            user_id = event.update.message.from_user.id if event.update.message.from_user else None
            with suppress(Exception):
                await event.update.message.answer(
                    GENERIC_ERROR_MESSAGE,
                    reply_markup=_recovery_keyboard(user_id),
                )
            return

        if event.update.callback_query:
            with suppress(Exception):
                await event.update.callback_query.answer()

            if event.update.callback_query.message:
                with suppress(Exception):
                    await event.update.callback_query.message.answer(
                        GENERIC_ERROR_MESSAGE,
                        reply_markup=_recovery_keyboard(event.update.callback_query.from_user.id),
                    )
