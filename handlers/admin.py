import logging

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import ADMIN_USER_IDS
from database import (
    get_admin_counts,
    get_client_profile,
    get_consultation_by_id,
    get_consultations,
    update_consultation_status,
)
from formatting import format_date_for_display, format_status, format_username
from texts import (
    ADMIN_ACTION_CANCEL,
    ADMIN_ACTION_COMPLETE,
    ADMIN_ACTION_CONFIRM,
    ADMIN_ACTION_NEXT,
    ADMIN_ACTION_PREVIOUS,
    ADMIN_ACCESS_DENIED,
    ADMIN_CARD_CITY,
    ADMIN_CARD_DATE,
    ADMIN_CARD_FILTER,
    ADMIN_CARD_ISSUE,
    ADMIN_CARD_PET_AGE,
    ADMIN_CARD_PET_BREED,
    ADMIN_CARD_PET_NAME,
    ADMIN_CARD_PET_WEIGHT,
    ADMIN_CARD_PHONE,
    ADMIN_CARD_SPECIALIST,
    ADMIN_CARD_STATUS,
    ADMIN_CARD_TIME,
    ADMIN_CARD_TITLE,
    ADMIN_CARD_TYPE,
    ADMIN_CARD_USER,
    ADMIN_FILTER_ALL,
    ADMIN_FILTER_CONFIRMED,
    ADMIN_FILTER_EMPTY,
    ADMIN_FILTER_PENDING,
    ADMIN_FILTER_TODAY,
    ADMIN_FILTER_TOMORROW,
    ADMIN_LOAD_ERROR,
    ADMIN_MENU_BUTTON,
    ADMIN_NO_RECORDS,
    ADMIN_PANEL_TITLE,
    ADMIN_RECORD_NOT_FOUND,
    ADMIN_STATUS_ALREADY_SET,
    ADMIN_STATUS_UPDATED,
    ADMIN_STATUS_UPDATE_ERROR,
    USER_BOOKING_CANCELLED,
    USER_BOOKING_COMPLETED,
    USER_BOOKING_CONFIRMED,
)


router = Router()
logger = logging.getLogger(__name__)
FILTER_LABELS = {
    "pending": ADMIN_FILTER_PENDING,
    "confirmed": ADMIN_FILTER_CONFIRMED,
    "today": ADMIN_FILTER_TODAY,
    "tomorrow": ADMIN_FILTER_TOMORROW,
    "all": ADMIN_FILTER_ALL,
}
ACTION_STATUS_MAP = {
    "confirm": "confirmed",
    "cancel": "cancelled",
    "complete": "completed",
}


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS


def _admin_menu_keyboard(counts: dict[str, int]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{ADMIN_FILTER_PENDING} ({counts.get('pending', 0)})",
                    callback_data="admin:list:pending:0",
                ),
                InlineKeyboardButton(
                    text=f"{ADMIN_FILTER_CONFIRMED} ({counts.get('confirmed', 0)})",
                    callback_data="admin:list:confirmed:0",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"{ADMIN_FILTER_TODAY} ({counts.get('today', 0)})",
                    callback_data="admin:list:today:0",
                ),
                InlineKeyboardButton(
                    text=f"{ADMIN_FILTER_TOMORROW} ({counts.get('tomorrow', 0)})",
                    callback_data="admin:list:tomorrow:0",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"{ADMIN_FILTER_ALL} ({counts.get('all', 0)})",
                    callback_data="admin:list:all:0",
                )
            ],
        ]
    )


def _admin_record_text(record: dict, page: int, total: int, filter_name: str) -> str:
    client = record.get("client", {})
    lines = [
        f"{ADMIN_CARD_TITLE} {page + 1} із {total}",
        f"{ADMIN_CARD_FILTER}: {FILTER_LABELS[filter_name]}",
        "",
        f"🆔 ID: {record['id']}",
        f"👤 {ADMIN_CARD_USER}: {format_username(record['username'])} (ID: {record['user_id']})",
        f"📞 {ADMIN_CARD_PHONE}: {client.get('phone_number', '—') or '—'}",
        f"🐾 {ADMIN_CARD_PET_NAME}: {client.get('pet_name', '—') or '—'}",
        f"🧬 {ADMIN_CARD_PET_BREED}: {client.get('pet_breed', '—') or '—'}",
        f"🎂 {ADMIN_CARD_PET_AGE}: {client.get('pet_age', '—') or '—'}",
        f"⚖️ {ADMIN_CARD_PET_WEIGHT}: {client.get('pet_weight', '—') or '—'}",
        f"👨‍⚕️ {ADMIN_CARD_SPECIALIST}: {record['specialist']}",
        f"📝 {ADMIN_CARD_TYPE}: {record['consultation_type']}",
        f"📅 {ADMIN_CARD_DATE}: {format_date_for_display(record['date'])}",
        f"🕒 {ADMIN_CARD_TIME}: {record['time']}",
        f"📌 {ADMIN_CARD_STATUS}: {format_status(record['status'])}",
    ]

    if record["city"]:
        lines.append(f"🏙️ {ADMIN_CARD_CITY}: {record['city']}")
    if client.get("issue_description"):
        lines.append(f"💬 {ADMIN_CARD_ISSUE}: {client['issue_description']}")

    return "\n".join(lines)


def _admin_record_keyboard(record: dict, filter_name: str, page: int, total: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    status = record["status"]

    if status == "pending":
        rows.append(
            [
                InlineKeyboardButton(
                    text=ADMIN_ACTION_CONFIRM,
                    callback_data=f"admin:action:{record['id']}:confirm:{filter_name}:{page}",
                ),
                InlineKeyboardButton(
                    text=ADMIN_ACTION_CANCEL,
                    callback_data=f"admin:action:{record['id']}:cancel:{filter_name}:{page}",
                ),
            ]
        )
    elif status == "confirmed":
        rows.append(
            [
                InlineKeyboardButton(
                    text=ADMIN_ACTION_COMPLETE,
                    callback_data=f"admin:action:{record['id']}:complete:{filter_name}:{page}",
                ),
                InlineKeyboardButton(
                    text=ADMIN_ACTION_CANCEL,
                    callback_data=f"admin:action:{record['id']}:cancel:{filter_name}:{page}",
                ),
            ]
        )

    if total > 1:
        nav_row: list[InlineKeyboardButton] = []
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(
                    text=ADMIN_ACTION_PREVIOUS,
                    callback_data=f"admin:list:{filter_name}:{page - 1}",
                )
            )
        if page < total - 1:
            nav_row.append(
                InlineKeyboardButton(
                    text=ADMIN_ACTION_NEXT,
                    callback_data=f"admin:list:{filter_name}:{page + 1}",
                )
            )
        if nav_row:
            rows.append(nav_row)

    rows.append([InlineKeyboardButton(text=ADMIN_MENU_BUTTON, callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _user_status_message(record: dict, new_status: str) -> str | None:
    details = [
        "",
        f"Спеціаліст: {record['specialist']}",
        f"Тип консультації: {record['consultation_type']}",
        f"Дата: {format_date_for_display(record['date'])}",
        f"Час: {record['time']}",
    ]
    if record["city"]:
        details.append(f"Місто: {record['city']}")

    if new_status == "confirmed":
        return USER_BOOKING_CONFIRMED + "\n" + "\n".join(details)
    if new_status == "cancelled":
        return USER_BOOKING_CANCELLED + "\n" + "\n".join(details)
    if new_status == "completed":
        return USER_BOOKING_COMPLETED + "\n" + "\n".join(details)
    return None


async def _render_admin_menu(target_message: Message):
    counts = await get_admin_counts()
    await target_message.edit_text(ADMIN_PANEL_TITLE, reply_markup=_admin_menu_keyboard(counts))


async def _render_admin_list(
    target_message: Message,
    filter_name: str,
    requested_page: int,
):
    records = await get_consultations(filter_name)
    if not records:
        await target_message.edit_text(
            ADMIN_FILTER_EMPTY,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=ADMIN_MENU_BUTTON, callback_data="admin:menu")]
                ]
            ),
        )
        return

    page = max(0, min(requested_page, len(records) - 1))
    record = records[page]
    record["client"] = await get_client_profile(record["user_id"]) or {}
    await target_message.edit_text(
        _admin_record_text(record, page, len(records), filter_name),
        reply_markup=_admin_record_keyboard(record, filter_name, page, len(records)),
    )


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not _is_admin(message.from_user.id):
        await message.answer(ADMIN_ACCESS_DENIED)
        return

    try:
        counts = await get_admin_counts()
    except Exception:
        logger.exception("Не вдалося отримати записи для адмін-панелі.")
        await message.answer(ADMIN_LOAD_ERROR)
        return

    if counts.get("all", 0) == 0:
        await message.answer(ADMIN_NO_RECORDS)
        return

    await message.answer(ADMIN_PANEL_TITLE, reply_markup=_admin_menu_keyboard(counts))


@router.callback_query(lambda callback: callback.data == "admin:menu")
async def admin_menu(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    try:
        await _render_admin_menu(callback.message)
        await callback.answer()
    except TelegramBadRequest:
        await callback.answer()
    except Exception:
        logger.exception("Не вдалося відкрити меню адміністратора.")
        await callback.answer()
        await callback.message.answer(ADMIN_LOAD_ERROR)


@router.callback_query(lambda callback: callback.data.startswith("admin:list:"))
async def admin_list(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    _, _, filter_name, page_str = callback.data.split(":")

    try:
        await _render_admin_list(callback.message, filter_name, int(page_str))
        await callback.answer()
    except Exception:
        logger.exception("Не вдалося відкрити список записів для фільтра %s.", filter_name)
        await callback.answer()
        await callback.message.answer(ADMIN_LOAD_ERROR)


@router.callback_query(lambda callback: callback.data.startswith("admin:action:"))
async def admin_action(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    _, _, record_id_str, action_name, filter_name, page_str = callback.data.split(":")
    record_id = int(record_id_str)
    page = int(page_str)
    new_status = ACTION_STATUS_MAP[action_name]

    try:
        record = await get_consultation_by_id(record_id)
        if not record:
            await callback.answer(ADMIN_RECORD_NOT_FOUND, show_alert=True)
            await _render_admin_list(callback.message, filter_name, page)
            return

        if record["status"] == new_status:
            await callback.answer(ADMIN_STATUS_ALREADY_SET, show_alert=True)
            return

        updated = await update_consultation_status(record_id, new_status)
        if not updated:
            await callback.answer(ADMIN_STATUS_UPDATE_ERROR, show_alert=True)
            return

        user_message = _user_status_message(record, new_status)
        if user_message:
            try:
                await callback.bot.send_message(record["user_id"], user_message)
            except Exception:
                logger.exception(
                    "Не вдалося надіслати користувачу повідомлення про зміну статусу запису %s.",
                    record_id,
                )

        await callback.answer(ADMIN_STATUS_UPDATED)
        await _render_admin_list(callback.message, filter_name, page)
    except Exception:
        logger.exception("Не вдалося оновити статус запису %s.", record_id)
        await callback.answer(ADMIN_STATUS_UPDATE_ERROR, show_alert=True)
