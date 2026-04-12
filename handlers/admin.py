import logging
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import ADMIN_USER_IDS, BUSINESS_TIMEZONE
from database import (
    delete_client_profile,
    get_admin_counts,
    get_all_client_profiles,
    get_client_profile,
    get_consultation_by_id,
    get_consultations,
    get_consultations_for_user,
    is_slot_available_for_update,
    search_client_profiles,
    update_consultation_schedule,
    update_consultation_status,
)
from formatting import (
    format_date_for_button,
    format_date_for_display,
    format_datetime_for_display,
    format_status,
    format_username,
    get_available_times,
)
from texts import (
    ADMIN_ACTION_CANCEL,
    ADMIN_ACTION_CLIENTS,
    ADMIN_ACTION_BACK_TO_CLIENT,
    ADMIN_ACTION_COMPLETE,
    ADMIN_ACTION_CONFIRM,
    ADMIN_ACTION_NEXT,
    ADMIN_ACTION_OPEN_CLIENT,
    ADMIN_ACTION_OPEN_BOOKINGS,
    ADMIN_ACTION_OPEN_NEXT_BOOKING,
    ADMIN_ACTION_OPEN_LAST_BOOKING,
    ADMIN_ACTION_PREVIOUS,
    ADMIN_ACTION_RESCHEDULE,
    ADMIN_ACTION_RESET_BACK,
    ADMIN_ACTION_RESET_CONFIRM,
    ADMIN_ACTION_RESET_PROFILE,
    ADMIN_ACCESS_DENIED,
    ADMIN_CARD_CITY,
    ADMIN_CARD_CLIENT_ACTIVITY,
    ADMIN_CARD_CREATED_AT,
    ADMIN_CARD_DATE,
    ADMIN_CARD_FILTER,
    ADMIN_CARD_FULL_NAME,
    ADMIN_CARD_ISSUE,
    ADMIN_CARD_PET_AGE,
    ADMIN_CARD_PET_BREED,
    ADMIN_CARD_PET_NAME,
    ADMIN_CARD_PET_WEIGHT,
    ADMIN_CARD_PHONE,
    ADMIN_CARD_PROFILE,
    ADMIN_CARD_SPECIALIST,
    ADMIN_CARD_STATUS,
    ADMIN_CARD_TIME,
    ADMIN_CARD_TITLE,
    ADMIN_CARD_TYPE,
    ADMIN_CARD_UPDATED_AT,
    ADMIN_CARD_USER,
    ADMIN_CARD_NEXT_BOOKING,
    ADMIN_CLIENT_NEXT_BOOKING_EMPTY,
    ADMIN_CLIENT_RESET_CONFIRM_TEXT,
    ADMIN_CLIENT_RESET_ERROR,
    ADMIN_CLIENT_RESET_SUCCESS,
    ADMIN_CLIENTS_EMPTY,
    ADMIN_CLIENT_BOOKINGS_EMPTY,
    ADMIN_CLIENT_BOOKINGS_TITLE,
    ADMIN_CLIENT_HISTORY_EMPTY,
    ADMIN_CLIENT_HISTORY_TITLE,
    ADMIN_CLIENT_STATS_ACTIVE,
    ADMIN_CLIENT_STATS_CANCELLED,
    ADMIN_CLIENT_STATS_COMPLETED,
    ADMIN_CLIENT_STATS_CONFIRMED,
    ADMIN_CLIENT_STATS_TITLE,
    ADMIN_CLIENT_STATS_TOTAL,
    ADMIN_FILTER_ALL,
    ADMIN_FILTER_CANCELLED,
    ADMIN_FILTER_COMPLETED,
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
    ADMIN_RESCHEDULE_ERROR,
    ADMIN_RESCHEDULE_NO_TIMES,
    ADMIN_RESCHEDULE_SUCCESS,
    ADMIN_RESCHEDULE_TIME_TITLE,
    ADMIN_RESCHEDULE_TITLE,
    ADMIN_SEARCH_EMPTY,
    ADMIN_SEARCH_TITLE,
    ADMIN_SEARCH_TOO_MANY,
    ADMIN_SEARCH_USAGE,
    ADMIN_STATUS_ALREADY_SET,
    ADMIN_STATUS_UPDATED,
    ADMIN_STATUS_UPDATE_ERROR,
    USER_BOOKING_CANCELLED,
    USER_BOOKING_COMPLETED,
    USER_BOOKING_CONFIRMED,
    USER_BOOKING_RESCHEDULED,
)


router = Router()
logger = logging.getLogger(__name__)
FILTER_LABELS = {
    "pending": ADMIN_FILTER_PENDING,
    "confirmed": ADMIN_FILTER_CONFIRMED,
    "cancelled": ADMIN_FILTER_CANCELLED,
    "completed": ADMIN_FILTER_COMPLETED,
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


def _admin_menu_keyboard(counts: dict[str, int], clients_count: int) -> InlineKeyboardMarkup:
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
                    text=f"{ADMIN_FILTER_CANCELLED} ({counts.get('cancelled', 0)})",
                    callback_data="admin:list:cancelled:0",
                ),
                InlineKeyboardButton(
                    text=f"{ADMIN_FILTER_COMPLETED} ({counts.get('completed', 0)})",
                    callback_data="admin:list:completed:0",
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
            [
                InlineKeyboardButton(
                    text=f"{ADMIN_ACTION_CLIENTS} ({clients_count})",
                    callback_data="admin:clients:0",
                )
            ],
        ]
    )


def _admin_record_text(
    record: dict,
    page: int,
    total: int,
    filter_name: str,
    user_records: list[dict] | None = None,
) -> str:
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
    if user_records is not None:
        active_count = sum(1 for item in user_records if item["status"] in {"pending", "confirmed"})
        lines.append(
            f"📚 {ADMIN_CARD_CLIENT_ACTIVITY}: {len(user_records)} • активних: {active_count}"
        )

    return "\n".join(lines)


def _admin_record_keyboard(
    record: dict,
    filter_name: str,
    page: int,
    total: int,
    next_active_record_id: int | None = None,
) -> InlineKeyboardMarkup:
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
        rows.append(
            [
                InlineKeyboardButton(
                    text=ADMIN_ACTION_RESCHEDULE,
                    callback_data=f"admin:reschedule:{record['id']}:{filter_name}:{page}",
                )
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
        rows.append(
            [
                InlineKeyboardButton(
                    text=ADMIN_ACTION_RESCHEDULE,
                    callback_data=f"admin:reschedule:{record['id']}:{filter_name}:{page}",
                )
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

    quick_row = [
        InlineKeyboardButton(
            text=ADMIN_ACTION_OPEN_CLIENT,
            callback_data=f"admin:client:{record['user_id']}",
        ),
        InlineKeyboardButton(
            text=ADMIN_ACTION_OPEN_BOOKINGS,
            callback_data=f"admin:client_bookings:{record['user_id']}:-1",
        ),
    ]
    rows.append(quick_row)

    if next_active_record_id is not None and next_active_record_id != record["id"]:
        rows.append(
            [
                InlineKeyboardButton(
                    text=ADMIN_ACTION_OPEN_NEXT_BOOKING,
                    callback_data=f"admin:open_booking:{next_active_record_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=ADMIN_MENU_BUTTON, callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _client_full_name(profile: dict) -> str:
    first_name = (profile.get("first_name") or "").strip()
    last_name = (profile.get("last_name") or "").strip()
    full_name = " ".join(part for part in (first_name, last_name) if part)
    return full_name or "—"


def _client_record_text(profile: dict, page: int, total: int) -> str:
    lines = [
        f"{ADMIN_CARD_PROFILE} {page + 1} із {total}",
        "",
        f"👤 {ADMIN_CARD_FULL_NAME}: {_client_full_name(profile)}",
        f"🆔 ID: {profile['user_id']}",
        f"🔗 {ADMIN_CARD_USER}: {format_username(profile.get('username'))} (ID: {profile['user_id']})",
        f"📞 {ADMIN_CARD_PHONE}: {profile.get('phone_number', '—') or '—'}",
        f"🐾 {ADMIN_CARD_PET_NAME}: {profile.get('pet_name', '—') or '—'}",
        f"🧬 {ADMIN_CARD_PET_BREED}: {profile.get('pet_breed', '—') or '—'}",
        f"🎂 {ADMIN_CARD_PET_AGE}: {profile.get('pet_age', '—') or '—'}",
        f"⚖️ {ADMIN_CARD_PET_WEIGHT}: {profile.get('pet_weight', '—') or '—'}",
        f"🗓️ {ADMIN_CARD_CREATED_AT}: {format_datetime_for_display(profile.get('created_at'))}",
        f"♻️ {ADMIN_CARD_UPDATED_AT}: {format_datetime_for_display(profile.get('updated_at'))}",
    ]

    if profile.get("issue_description"):
        lines.append(f"💬 {ADMIN_CARD_ISSUE}: {profile['issue_description']}")

    return "\n".join(lines)


def _client_history_lines(records: list[dict], limit: int = 5) -> list[str]:
    if not records:
        return [f"🗂️ {ADMIN_CLIENT_HISTORY_TITLE}: {ADMIN_CLIENT_HISTORY_EMPTY}"]

    lines = [f"🗂️ {ADMIN_CLIENT_HISTORY_TITLE}:"]
    for record in records[:limit]:
        city_suffix = f", {record['city']}" if record.get("city") else ""
        lines.append(
            f"• {format_date_for_display(record['date'])}, {record['time']} — "
            f"{record['specialist']} ({format_status(record['status'])}{city_suffix})"
        )
    return lines


def _client_stats_lines(records: list[dict]) -> list[str]:
    active_count = sum(1 for record in records if record["status"] in {"pending", "confirmed"})
    confirmed_count = sum(1 for record in records if record["status"] == "confirmed")
    completed_count = sum(1 for record in records if record["status"] == "completed")
    cancelled_count = sum(1 for record in records if record["status"] == "cancelled")

    return [
        f"📊 {ADMIN_CLIENT_STATS_TITLE}:",
        f"• {ADMIN_CLIENT_STATS_TOTAL}: {len(records)}",
        f"• {ADMIN_CLIENT_STATS_ACTIVE}: {active_count}",
        f"• {ADMIN_CLIENT_STATS_CONFIRMED}: {confirmed_count}",
        f"• {ADMIN_CLIENT_STATS_COMPLETED}: {completed_count}",
        f"• {ADMIN_CLIENT_STATS_CANCELLED}: {cancelled_count}",
    ]


def _record_datetime(record: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(f"{record['date']}T{record['time']}:00").replace(
            tzinfo=BUSINESS_TIMEZONE
        )
    except (KeyError, ValueError):
        return None


def _next_active_booking(records: list[dict]) -> dict | None:
    now = datetime.now(BUSINESS_TIMEZONE)
    active_records: list[tuple[datetime, dict]] = []

    for record in records:
        if record.get("status") not in {"pending", "confirmed"}:
            continue
        record_dt = _record_datetime(record)
        if record_dt is None:
            continue
        if record_dt >= now:
            active_records.append((record_dt, record))

    if not active_records:
        return None

    active_records.sort(key=lambda item: item[0])
    return active_records[0][1]


def _next_active_booking_lines(record: dict | None) -> list[str]:
    if not record:
        return [f"🟢 {ADMIN_CARD_NEXT_BOOKING}: {ADMIN_CLIENT_NEXT_BOOKING_EMPTY}"]

    city_suffix = f", {record['city']}" if record.get("city") else ""
    return [
        f"🟢 {ADMIN_CARD_NEXT_BOOKING}:",
        f"• {format_date_for_display(record['date'])}, {record['time']}",
        f"• {record['specialist']} ({format_status(record['status'])}{city_suffix})",
    ]


def _client_record_keyboard(
    profile: dict,
    page: int,
    total: int,
    next_active_record_id: int | None = None,
    latest_record_id: int | None = None,
    has_bookings: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=ADMIN_ACTION_RESET_PROFILE,
                callback_data=f"admin:client_reset_prompt:{profile['user_id']}:{page}",
            )
        ]
    ]

    if next_active_record_id is not None:
        rows.insert(
            0,
            [
                InlineKeyboardButton(
                    text=ADMIN_ACTION_OPEN_NEXT_BOOKING,
                    callback_data=f"admin:open_booking:{next_active_record_id}",
                )
            ],
        )

    if latest_record_id is not None and latest_record_id != next_active_record_id:
        rows.insert(
            1 if next_active_record_id is not None else 0,
            [
                InlineKeyboardButton(
                    text=ADMIN_ACTION_OPEN_LAST_BOOKING,
                    callback_data=f"admin:open_booking:{latest_record_id}",
                )
            ],
        )

    if has_bookings:
        rows.insert(
            1 if latest_record_id is not None else 0,
            [
                InlineKeyboardButton(
                    text=ADMIN_ACTION_OPEN_BOOKINGS,
                    callback_data=f"admin:client_bookings:{profile['user_id']}:{page}",
                )
            ],
        )

    if total > 1:
        nav_row: list[InlineKeyboardButton] = []
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(
                    text=ADMIN_ACTION_PREVIOUS,
                    callback_data=f"admin:clients:{page - 1}",
                )
            )
        if page < total - 1:
            nav_row.append(
                InlineKeyboardButton(
                    text=ADMIN_ACTION_NEXT,
                    callback_data=f"admin:clients:{page + 1}",
                )
            )
        if nav_row:
            rows.append(nav_row)

    rows.append([InlineKeyboardButton(text=ADMIN_MENU_BUTTON, callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _client_reset_confirmation_keyboard(user_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ADMIN_ACTION_RESET_CONFIRM,
                    callback_data=f"admin:client_reset:{user_id}:{page}",
                ),
                InlineKeyboardButton(
                    text=ADMIN_ACTION_RESET_BACK,
                    callback_data=f"admin:clients:{page}",
                ),
            ],
            [InlineKeyboardButton(text=ADMIN_MENU_BUTTON, callback_data="admin:menu")],
        ]
    )


def _search_results_keyboard(results: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for profile in results:
        pet_name = profile.get("pet_name", "").strip() or "без імені"
        phone = profile.get("phone_number", "").strip() or "без телефону"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{pet_name} • {phone}",
                    callback_data=f"admin:client:{profile['user_id']}",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text=ADMIN_MENU_BUTTON, callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _client_bookings_keyboard(user_id: int, client_page: int, records: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for record in records[:10]:
        label = (
            f"{record['date']} {record['time']} • "
            f"{record['specialist']} • {format_status(record['status'])}"
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"admin:open_booking:{record['id']}",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=ADMIN_ACTION_BACK_TO_CLIENT,
                callback_data=f"admin:client:{user_id}:{client_page}",
            )
        ]
    )
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


def _admin_reschedule_date_keyboard(record_id: int, filter_name: str, page: int) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    today = datetime.now(BUSINESS_TIMEZONE)
    row: list[InlineKeyboardButton] = []

    for offset in range(7):
        date_value = today + timedelta(days=offset)
        date_str = date_value.strftime("%Y-%m-%d")
        row.append(
            InlineKeyboardButton(
                text=format_date_for_button(date_value),
                callback_data=f"admin:reschedule_date:{record_id}:{filter_name}:{page}:{date_str}",
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append(
        [
            InlineKeyboardButton(
                text=ADMIN_ACTION_PREVIOUS,
                callback_data=f"admin:list:{filter_name}:{page}",
            ),
            InlineKeyboardButton(text=ADMIN_MENU_BUTTON, callback_data="admin:menu"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _admin_reschedule_time_keyboard(
    record_id: int,
    filter_name: str,
    page: int,
    date_value: str,
    available_times: list[str],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []
    for time_value in available_times:
        time_key = time_value.replace(":", ".")
        current_row.append(
            InlineKeyboardButton(
                text=time_value,
                callback_data=f"admin:reschedule_time:{record_id}:{filter_name}:{page}:{date_value}:{time_key}",
            )
        )
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []

    if current_row:
        rows.append(current_row)

    rows.append(
        [
            InlineKeyboardButton(
                text=ADMIN_ACTION_PREVIOUS,
                callback_data=f"admin:reschedule:{record_id}:{filter_name}:{page}",
            ),
            InlineKeyboardButton(text=ADMIN_MENU_BUTTON, callback_data="admin:menu"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _get_admin_available_times(record: dict, date_value: str) -> list[str]:
    candidate_times = get_available_times(date_value)
    available_times: list[str] = []
    for time_value in candidate_times:
        is_available = await is_slot_available_for_update(
            record["id"],
            record["specialist"],
            date_value,
            time_value,
            record.get("city", ""),
        )
        if is_available:
            available_times.append(time_value)
    return available_times


async def _render_admin_menu(target_message: Message):
    counts = await get_admin_counts()
    clients = await get_all_client_profiles()
    panel_text = ADMIN_PANEL_TITLE
    if counts.get("all", 0) == 0:
        panel_text = f"{ADMIN_PANEL_TITLE}\n\n{ADMIN_NO_RECORDS}"
    await target_message.edit_text(
        panel_text,
        reply_markup=_admin_menu_keyboard(counts, len(clients)),
    )


async def _render_admin_list(target_message: Message, filter_name: str, requested_page: int):
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
    user_records = await get_consultations_for_user(record["user_id"])
    next_active_record = _next_active_booking(user_records)
    await target_message.edit_text(
        _admin_record_text(record, page, len(records), filter_name, user_records),
        reply_markup=_admin_record_keyboard(
            record,
            filter_name,
            page,
            len(records),
            next_active_record_id=next_active_record["id"] if next_active_record else None,
        ),
    )


async def _render_clients_list(target_message: Message, requested_page: int):
    clients = await get_all_client_profiles()
    if not clients:
        await target_message.edit_text(
            ADMIN_CLIENTS_EMPTY,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=ADMIN_MENU_BUTTON, callback_data="admin:menu")]
                ]
            ),
        )
        return

    page = max(0, min(requested_page, len(clients) - 1))
    profile = clients[page]
    consultations = await get_consultations_for_user(profile["user_id"], limit=5)
    all_consultations = await get_consultations_for_user(profile["user_id"])
    next_active_record = _next_active_booking(all_consultations)
    latest_record_id = consultations[0]["id"] if consultations else None
    await target_message.edit_text(
        _client_record_text(profile, page, len(clients))
        + "\n\n"
        + "\n".join(_client_stats_lines(all_consultations))
        + "\n\n"
        + "\n".join(_next_active_booking_lines(next_active_record))
        + "\n\n"
        + "\n".join(_client_history_lines(consultations)),
        reply_markup=_client_record_keyboard(
            profile,
            page,
            len(clients),
            next_active_record_id=next_active_record["id"] if next_active_record else None,
            latest_record_id=latest_record_id,
            has_bookings=bool(consultations),
        ),
    )


async def _render_client_reset_prompt(target_message: Message, user_id: int, page: int):
    clients = await get_all_client_profiles()
    if not clients:
        await target_message.edit_text(
            ADMIN_CLIENTS_EMPTY,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=ADMIN_MENU_BUTTON, callback_data="admin:menu")]
                ]
            ),
        )
        return

    resolved_page = max(0, min(page, len(clients) - 1))
    profile = next((item for item in clients if item["user_id"] == user_id), None)
    if profile is None:
        profile = clients[resolved_page]
        resolved_page = next(
            index for index, item in enumerate(clients) if item["user_id"] == profile["user_id"]
        )
    consultations = await get_consultations_for_user(profile["user_id"], limit=5)
    all_consultations = await get_consultations_for_user(profile["user_id"])
    next_active_record = _next_active_booking(all_consultations)

    await target_message.edit_text(
        _client_record_text(profile, resolved_page, len(clients))
        + "\n\n"
        + "\n".join(_client_stats_lines(all_consultations))
        + "\n\n"
        + "\n".join(_next_active_booking_lines(next_active_record))
        + "\n\n"
        + "\n".join(_client_history_lines(consultations))
        + "\n\n"
        + ADMIN_CLIENT_RESET_CONFIRM_TEXT,
        reply_markup=_client_reset_confirmation_keyboard(user_id, resolved_page),
    )


async def _render_client_bookings(target_message: Message, user_id: int, client_page: int):
    clients = await get_all_client_profiles()
    profile = next((item for item in clients if item["user_id"] == user_id), None)
    bookings = await get_consultations_for_user(user_id)

    if profile is None:
        await target_message.edit_text(
            ADMIN_RECORD_NOT_FOUND,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=ADMIN_MENU_BUTTON, callback_data="admin:menu")]
                ]
            ),
        )
        return

    resolved_page = next(
        (index for index, item in enumerate(clients) if item["user_id"] == user_id),
        max(client_page, 0),
    )

    if not bookings:
        await target_message.edit_text(
            f"{ADMIN_CLIENT_BOOKINGS_TITLE}: {_client_full_name(profile)}\n\n{ADMIN_CLIENT_BOOKINGS_EMPTY}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=ADMIN_ACTION_BACK_TO_CLIENT,
                            callback_data=f"admin:client:{user_id}:{resolved_page}",
                        )
                    ],
                    [InlineKeyboardButton(text=ADMIN_MENU_BUTTON, callback_data="admin:menu")],
                ]
            ),
        )
        return

    title = [
        f"{ADMIN_CLIENT_BOOKINGS_TITLE}: {_client_full_name(profile)}",
        f"🆔 ID: {user_id}",
        "",
    ]
    await target_message.edit_text(
        "\n".join(title + _client_history_lines(bookings, limit=10)),
        reply_markup=_client_bookings_keyboard(user_id, resolved_page, bookings),
    )


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not _is_admin(message.from_user.id):
        await message.answer(ADMIN_ACCESS_DENIED)
        return

    try:
        counts = await get_admin_counts()
        clients = await get_all_client_profiles()
    except Exception:
        logger.exception("Не вдалося отримати дані для адмін-панелі.")
        await message.answer(ADMIN_LOAD_ERROR)
        return

    panel_text = ADMIN_PANEL_TITLE
    if counts.get("all", 0) == 0:
        panel_text = f"{ADMIN_PANEL_TITLE}\n\n{ADMIN_NO_RECORDS}"

    await message.answer(panel_text, reply_markup=_admin_menu_keyboard(counts, len(clients)))


@router.message(Command("admin_find"))
async def admin_find_client(message: Message, command: CommandObject):
    if not _is_admin(message.from_user.id):
        await message.answer(ADMIN_ACCESS_DENIED)
        return

    query = (command.args or "").strip()
    if not query:
        await message.answer(ADMIN_SEARCH_USAGE)
        return

    try:
        results = await search_client_profiles(query)
    except Exception:
        logger.exception("Не вдалося виконати пошук клієнта за запитом %s.", query)
        await message.answer(ADMIN_LOAD_ERROR)
        return

    if not results:
        await message.answer(ADMIN_SEARCH_EMPTY)
        return

    text = ADMIN_SEARCH_TITLE
    if len(results) >= 8:
        text += f"\n\n{ADMIN_SEARCH_TOO_MANY}"
    await message.answer(text, reply_markup=_search_results_keyboard(results))


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


@router.callback_query(lambda callback: callback.data.startswith("admin:clients:"))
async def admin_clients(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    _, _, page_str = callback.data.split(":")

    try:
        await _render_clients_list(callback.message, int(page_str))
        await callback.answer()
    except Exception:
        logger.exception("Не вдалося відкрити список клієнтів.")
        await callback.answer()
        await callback.message.answer(ADMIN_LOAD_ERROR)


@router.callback_query(lambda callback: callback.data.startswith("admin:client:"))
async def admin_client_from_record(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    parts = callback.data.split(":")
    user_id_str = parts[2]
    preferred_page = int(parts[3]) if len(parts) > 3 else None

    try:
        clients = await get_all_client_profiles()
        if not clients:
            await callback.answer(ADMIN_CLIENTS_EMPTY, show_alert=True)
            return

        found_page = next(
            (index for index, profile in enumerate(clients) if profile["user_id"] == int(user_id_str)),
            None,
        )
        page = found_page if found_page is not None else (preferred_page or 0)
        await _render_clients_list(callback.message, page)
        await callback.answer()
    except Exception:
        logger.exception("Не вдалося відкрити анкету клієнта %s.", user_id_str)
        await callback.answer()
        await callback.message.answer(ADMIN_LOAD_ERROR)


@router.callback_query(lambda callback: callback.data.startswith("admin:client_bookings:"))
async def admin_client_bookings(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    _, _, user_id_str, client_page_str = callback.data.split(":")

    try:
        await _render_client_bookings(callback.message, int(user_id_str), int(client_page_str))
        await callback.answer()
    except Exception:
        logger.exception("Не вдалося відкрити список записів клієнта %s.", user_id_str)
        await callback.answer()
        await callback.message.answer(ADMIN_LOAD_ERROR)


@router.callback_query(lambda callback: callback.data.startswith("admin:open_booking:"))
async def admin_open_booking(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    _, _, record_id_str = callback.data.split(":")
    record_id = int(record_id_str)

    try:
        records = await get_consultations("all")
        if not records:
            await callback.answer(ADMIN_FILTER_EMPTY, show_alert=True)
            return

        page = next((index for index, record in enumerate(records) if record["id"] == record_id), None)
        if page is None:
            await callback.answer(ADMIN_RECORD_NOT_FOUND, show_alert=True)
            return

        await _render_admin_list(callback.message, "all", page)
        await callback.answer()
    except Exception:
        logger.exception("Не вдалося відкрити запис %s із картки клієнта.", record_id)
        await callback.answer()
        await callback.message.answer(ADMIN_LOAD_ERROR)


@router.callback_query(lambda callback: callback.data.startswith("admin:client_reset_prompt:"))
async def admin_client_reset_prompt(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    _, _, user_id_str, page_str = callback.data.split(":")

    try:
        await _render_client_reset_prompt(callback.message, int(user_id_str), int(page_str))
        await callback.answer()
    except Exception:
        logger.exception("Не вдалося відкрити підтвердження очищення анкети клієнта %s.", user_id_str)
        await callback.answer()
        await callback.message.answer(ADMIN_LOAD_ERROR)


@router.callback_query(lambda callback: callback.data.startswith("admin:client_reset:"))
async def admin_client_reset(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    _, _, user_id_str, page_str = callback.data.split(":")
    user_id = int(user_id_str)
    page = int(page_str)

    try:
        deleted = await delete_client_profile(user_id)
        if not deleted:
            await callback.answer(ADMIN_CLIENT_RESET_ERROR, show_alert=True)
            return

        await callback.answer(ADMIN_CLIENT_RESET_SUCCESS)
        await _render_clients_list(callback.message, page)
    except Exception:
        logger.exception("Не вдалося очистити анкету клієнта %s.", user_id)
        await callback.answer(ADMIN_CLIENT_RESET_ERROR, show_alert=True)


@router.callback_query(lambda callback: callback.data.startswith("admin:reschedule:"))
async def admin_reschedule_prompt(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    _, _, record_id_str, filter_name, page_str = callback.data.split(":")
    record = await get_consultation_by_id(int(record_id_str))
    if not record:
        await callback.answer(ADMIN_RECORD_NOT_FOUND, show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        f"{_admin_record_text(record, int(page_str), max(int(page_str) + 1, 1), filter_name)}\n\n{ADMIN_RESCHEDULE_TITLE}",
        reply_markup=_admin_reschedule_date_keyboard(record["id"], filter_name, int(page_str)),
    )


@router.callback_query(lambda callback: callback.data.startswith("admin:reschedule_date:"))
async def admin_reschedule_date(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    _, _, record_id_str, filter_name, page_str, date_value = callback.data.split(":")
    record = await get_consultation_by_id(int(record_id_str))
    if not record:
        await callback.answer(ADMIN_RECORD_NOT_FOUND, show_alert=True)
        return

    available_times = await _get_admin_available_times(record, date_value)
    if not available_times:
        await callback.answer()
        await callback.message.edit_text(
            f"{_admin_record_text(record, int(page_str), max(int(page_str) + 1, 1), filter_name)}\n\n"
            f"{ADMIN_RESCHEDULE_NO_TIMES}",
            reply_markup=_admin_reschedule_date_keyboard(record["id"], filter_name, int(page_str)),
        )
        return

    await callback.answer()
    await callback.message.edit_text(
        f"{_admin_record_text(record, int(page_str), max(int(page_str) + 1, 1), filter_name)}\n\n"
        f"{ADMIN_RESCHEDULE_TIME_TITLE.format(date=format_date_for_display(date_value))}",
        reply_markup=_admin_reschedule_time_keyboard(
            record["id"],
            filter_name,
            int(page_str),
            date_value,
            available_times,
        ),
    )


@router.callback_query(lambda callback: callback.data.startswith("admin:reschedule_time:"))
async def admin_reschedule_time(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    _, _, record_id_str, filter_name, page_str, date_value, time_key = callback.data.split(":")
    record_id = int(record_id_str)
    page = int(page_str)
    time_value = time_key.replace(".", ":")

    try:
        record = await get_consultation_by_id(record_id)
        if not record:
            await callback.answer(ADMIN_RECORD_NOT_FOUND, show_alert=True)
            return

        is_available = await is_slot_available_for_update(
            record_id,
            record["specialist"],
            date_value,
            time_value,
            record.get("city", ""),
        )
        if not is_available:
            available_times = await _get_admin_available_times(record, date_value)
            if not available_times:
                await callback.message.edit_text(
                    f"{_admin_record_text(record, page, max(page + 1, 1), filter_name)}\n\n"
                    f"{ADMIN_RESCHEDULE_NO_TIMES}",
                    reply_markup=_admin_reschedule_date_keyboard(record_id, filter_name, page),
                )
                await callback.answer()
                return

            await callback.message.edit_text(
                f"{_admin_record_text(record, page, max(page + 1, 1), filter_name)}\n\n"
                f"{ADMIN_RESCHEDULE_TIME_TITLE.format(date=format_date_for_display(date_value))}",
                reply_markup=_admin_reschedule_time_keyboard(
                    record_id,
                    filter_name,
                    page,
                    date_value,
                    available_times,
                ),
            )
            await callback.answer()
            return

        updated = await update_consultation_schedule(record_id, date_value, time_value)
        if not updated:
            await callback.answer(ADMIN_RESCHEDULE_ERROR, show_alert=True)
            return

        user_message = (
            USER_BOOKING_RESCHEDULED
            + "\n\n"
            + f"Спеціаліст: {record['specialist']}\n"
            + f"Тип консультації: {record['consultation_type']}\n"
            + f"Дата: {format_date_for_display(date_value)}\n"
            + f"Час: {time_value}"
        )
        if record.get("city"):
            user_message += f"\nМісто: {record['city']}"

        try:
            await callback.bot.send_message(record["user_id"], user_message)
        except Exception:
            logger.exception(
                "Не вдалося надіслати користувачу повідомлення про перенесення запису %s.",
                record_id,
            )

        await callback.answer(ADMIN_RESCHEDULE_SUCCESS)
        await _render_admin_list(callback.message, filter_name, page)
    except Exception:
        logger.exception("Не вдалося перенести запис %s.", record_id)
        await callback.answer(ADMIN_RESCHEDULE_ERROR, show_alert=True)


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
