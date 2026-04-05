import logging
from contextlib import suppress

from aiogram import Dispatcher
from aiogram.types import ErrorEvent

from texts import GENERIC_ERROR_MESSAGE


logger = logging.getLogger(__name__)


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
            with suppress(Exception):
                await event.update.message.answer(GENERIC_ERROR_MESSAGE)
            return

        if event.update.callback_query:
            with suppress(Exception):
                await event.update.callback_query.answer()

            if event.update.callback_query.message:
                with suppress(Exception):
                    await event.update.callback_query.message.answer(GENERIC_ERROR_MESSAGE)
