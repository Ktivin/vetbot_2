from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN_USER_IDS, BUSINESS_TIMEZONE
from database import (
    get_client_profile,
    get_consultation_by_id,
    get_consultations_for_user,
    update_consultation_status,
)
from formatting import format_date_for_display, format_status, format_username
from texts import (
    ADMIN_RECORD_NOT_FOUND,
    USER_BOOKING_CANCELLED_SUCCESS,
    USER_BOOKING_CANCEL_CONFIRM,
    USER_BOOKING_CANCEL_NOT_AVAILABLE,
    USER_BOOKING_CARD_TITLE,
    USER_BOOKING_CARD_TYPE,
    USER_BOOKING_CARD_SPECIALIST,
    USER_BOOKING_CARD_DATE,
    USER_BOOKING_CARD_TIME,
    USER_BOOKING_CARD_STATUS,
    USER_BOOKING_CARD_CITY,
    USER_BOOKING_CARD_ISSUE,
    USER_BOOKINGS_BACK_BUTTON,
    USER_BOOKINGS_CANCEL_BUTTON,
    USER_BOOKINGS_EMPTY,
    USER_BOOKINGS_LIST_TITLE,
    USER_BOOKINGS_MENU_BUTTON,
)


router = Router()


def _record_datetime(record: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(f"{record['date']}T{record['time']}:00").replace(
            tzinfo=BUSINESS_TIMEZONE
        )
    except (KeyError, ValueError):
        return None


def _sort_user_bookings(records: list[dict]) -> list[dict]:
    def sort_key(record: dict):
        record_dt = _record_datetime(record)
        return (
            record_dt or datetime.min.replace(tzinfo=BUSINESS_TIMEZONE),
            record.get("id", 0),
        )

    return sorted(records, key=sort_key)


def _is_cancellable(record: dict) -> bool:
    if record.get("status") not in {"pending", "confirmed"}:
        return False
    record_dt = _record_datetime(record)
    return record_dt is not None and record_dt >= datetime.now(BUSINESS_TIMEZONE)


def _bookings_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=USER_BOOKINGS_MENU_BUTTON, callback_data="home:main")],
        ]
    )


def _user_bookings_keyboard(records: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for record in records[:8]:
        rows.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"{format_date_for_display(record['date'])}, {record['time']} • "
                        f"{record['specialist']}"
                    ),
                    callback_data=f"user:booking:{record['id']}",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text=USER_BOOKINGS_MENU_BUTTON, callback_data="home:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _user_booking_keyboard(record: dict) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if _is_cancellable(record):
        rows.append(
            [
                InlineKeyboardButton(
                    text=USER_BOOKINGS_CANCEL_BUTTON,
                    callback_data=f"user:cancel_prompt:{record['id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=USER_BOOKINGS_BACK_BUTTON, callback_data="user:bookings")])
    rows.append([InlineKeyboardButton(text=USER_BOOKINGS_MENU_BUTTON, callback_data="home:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _user_cancel_confirm_keyboard(record_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=USER_BOOKINGS_CANCEL_BUTTON,
                    callback_data=f"user:cancel:{record_id}",
                )
            ],
            [InlineKeyboardButton(text=USER_BOOKINGS_BACK_BUTTON, callback_data=f"user:booking:{record_id}")],
            [InlineKeyboardButton(text=USER_BOOKINGS_MENU_BUTTON, callback_data="home:main")],
        ]
    )


def _booking_card_text(record: dict) -> str:
    lines = [
        USER_BOOKING_CARD_TITLE,
        "",
        f"{USER_BOOKING_CARD_SPECIALIST}: {record['specialist']}",
        f"{USER_BOOKING_CARD_TYPE}: {record['consultation_type']}",
        f"{USER_BOOKING_CARD_DATE}: {format_date_for_display(record['date'])}",
        f"{USER_BOOKING_CARD_TIME}: {record['time']}",
        f"{USER_BOOKING_CARD_STATUS}: {format_status(record['status'])}",
    ]
    if record.get("city"):
        lines.append(f"{USER_BOOKING_CARD_CITY}: {record['city']}")
    client_issue = (record.get("client") or {}).get("issue_description", "")
    if client_issue:
        lines.append(f"{USER_BOOKING_CARD_ISSUE}: {client_issue}")
    return "\n".join(lines)


async def _render_user_bookings(target_message, user_id: int, flash_message: str | None = None):
    records = _sort_user_bookings(await get_consultations_for_user(user_id))
    lines: list[str] = []
    if flash_message:
        lines.append(flash_message)
        lines.append("")

    if not records:
        lines.append(USER_BOOKINGS_EMPTY)
        await target_message.edit_text("\n".join(lines), reply_markup=_bookings_menu_keyboard())
        return

    lines.append(USER_BOOKINGS_LIST_TITLE)
    await target_message.edit_text("\n".join(lines), reply_markup=_user_bookings_keyboard(records))


@router.callback_query(F.data == "user:bookings")
async def user_bookings(callback: CallbackQuery):
    await callback.answer()
    await _render_user_bookings(callback.message, callback.from_user.id)


@router.callback_query(lambda callback: callback.data.startswith("user:booking:"))
async def user_booking_card(callback: CallbackQuery):
    await callback.answer()
    _, _, record_id_str = callback.data.split(":")
    record = await get_consultation_by_id(int(record_id_str))
    if not record or record["user_id"] != callback.from_user.id:
        await callback.answer(ADMIN_RECORD_NOT_FOUND, show_alert=True)
        return
    record["client"] = await get_client_profile(callback.from_user.id) or {}

    await callback.message.edit_text(
        _booking_card_text(record),
        reply_markup=_user_booking_keyboard(record),
    )


@router.callback_query(lambda callback: callback.data.startswith("user:cancel_prompt:"))
async def user_cancel_prompt(callback: CallbackQuery):
    await callback.answer()
    _, _, record_id_str = callback.data.split(":")
    record = await get_consultation_by_id(int(record_id_str))
    if not record or record["user_id"] != callback.from_user.id:
        await callback.answer(ADMIN_RECORD_NOT_FOUND, show_alert=True)
        return
    record["client"] = await get_client_profile(callback.from_user.id) or {}
    if not _is_cancellable(record):
        await callback.answer(USER_BOOKING_CANCEL_NOT_AVAILABLE, show_alert=True)
        return

    await callback.message.edit_text(
        f"{_booking_card_text(record)}\n\n{USER_BOOKING_CANCEL_CONFIRM}",
        reply_markup=_user_cancel_confirm_keyboard(record["id"]),
    )


@router.callback_query(lambda callback: callback.data.startswith("user:cancel:"))
async def user_cancel_booking(callback: CallbackQuery):
    await callback.answer()
    _, _, record_id_str = callback.data.split(":")
    record = await get_consultation_by_id(int(record_id_str))
    if not record or record["user_id"] != callback.from_user.id:
        await callback.answer(ADMIN_RECORD_NOT_FOUND, show_alert=True)
        return
    if not _is_cancellable(record):
        await callback.answer(USER_BOOKING_CANCEL_NOT_AVAILABLE, show_alert=True)
        return

    updated = await update_consultation_status(record["id"], "cancelled")
    if not updated:
        await callback.answer(USER_BOOKING_CANCEL_NOT_AVAILABLE, show_alert=True)
        return

    admin_message = (
        f"Запис #{record['id']}\n\n"
        f"Користувач самостійно скасував запис.\n"
        f"Користувач: {format_username(record.get('username'))} (ID: {record['user_id']})\n"
        f"Спеціаліст: {record['specialist']}\n"
        f"Тип: {record['consultation_type']}\n"
        f"Дата: {format_date_for_display(record['date'])} о {record['time']}"
    )
    if record.get("city"):
        admin_message += f"\nМісто: {record['city']}"

    for admin_id in ADMIN_USER_IDS:
        try:
            await callback.bot.send_message(admin_id, admin_message)
        except Exception:
            pass

    await _render_user_bookings(
        callback.message,
        callback.from_user.id,
        USER_BOOKING_CANCELLED_SUCCESS,
    )
