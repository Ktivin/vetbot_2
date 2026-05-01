import asyncio
import json
import logging
import time
from datetime import datetime

from config import (
    BUSINESS_TIMEZONE,
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_SHEETS_CHATS_WORKSHEET_NAME,
    GOOGLE_SHEETS_CHAT_ASSIGNMENTS_WORKSHEET_NAME,
    GOOGLE_SHEETS_EVENTS_WORKSHEET_NAME,
    GOOGLE_SHEETS_REMINDERS_WORKSHEET_NAME,
    GOOGLE_SHEETS_SPREADSHEET_ID,
)


logger = logging.getLogger(__name__)

CHAT_HEADERS = ["id", "user_id", "direction", "admin_id", "message", "created_at"]
CHAT_ASSIGNMENT_HEADERS = ["user_id", "assigned_admin_id", "status", "updated_at"]
EVENT_HEADERS = ["id", "event_type", "user_id", "admin_id", "record_id", "details", "created_at"]
REMINDER_HEADERS = ["record_id", "reminder_type", "sent_at"]

_spreadsheet_cache = None
_worksheet_cache: dict[str, object] = {}
_headers_initialized: set[str] = set()


def _is_configured() -> bool:
    return bool(GOOGLE_SHEETS_SPREADSHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON)


def is_google_sheets_crm_enabled() -> bool:
    return _is_configured()


def _is_retryable_error(error: Exception) -> bool:
    error_text = str(error)
    return any(
        marker in error_text
        for marker in ("[429]", "Quota exceeded", "503", "500", "timed out", "temporarily unavailable")
    )


def _run_with_retries_sync(operation, context: str, attempts: int = 3):
    delay_seconds = 1.0
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as error:
            if attempt >= attempts or not _is_retryable_error(error):
                raise
            logger.warning(
                "%s тимчасово недоступний (%s). Повторюю спробу %s/%s через %.1f с.",
                context,
                error,
                attempt + 1,
                attempts,
                delay_seconds,
            )
            time.sleep(delay_seconds)
            delay_seconds *= 2


def _column_letter(index: int) -> str:
    result = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _get_spreadsheet_sync():
    global _spreadsheet_cache
    if _spreadsheet_cache is not None:
        return _spreadsheet_cache

    import gspread

    credentials = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    client = gspread.service_account_from_dict(credentials)
    spreadsheet = _run_with_retries_sync(
        lambda: client.open_by_key(GOOGLE_SHEETS_SPREADSHEET_ID),
        "Підключення до Google Sheets",
    )
    _spreadsheet_cache = spreadsheet
    return spreadsheet


def _get_worksheet_sync(title: str, headers: list[str], rows: int = 1000, cols: int = 20):
    import gspread

    worksheet = _worksheet_cache.get(title)
    if worksheet is None:
        spreadsheet = _get_spreadsheet_sync()
        try:
            worksheet = _run_with_retries_sync(
                lambda: spreadsheet.worksheet(title),
                f"Отримання вкладки {title}",
            )
        except gspread.WorksheetNotFound:
            worksheet = _run_with_retries_sync(
                lambda: spreadsheet.add_worksheet(title=title, rows=rows, cols=cols),
                f"Створення вкладки {title}",
            )
        _worksheet_cache[title] = worksheet

    if title not in _headers_initialized:
        existing_headers = _run_with_retries_sync(
            lambda: worksheet.row_values(1),
            f"Читання заголовків вкладки {title}",
        )
        if existing_headers != headers:
            header_range = f"A1:{_column_letter(len(headers))}1"
            if existing_headers:
                _run_with_retries_sync(
                    lambda: worksheet.update(header_range, [headers]),
                    f"Оновлення заголовків вкладки {title}",
                )
            else:
                _run_with_retries_sync(
                    lambda: worksheet.append_row(headers),
                    f"Запис заголовків вкладки {title}",
                )
        _headers_initialized.add(title)

    return worksheet


def _next_id(records: list[dict]) -> int:
    next_id = 1
    for record in records:
        try:
            next_id = max(next_id, int(record.get("id", 0)) + 1)
        except (TypeError, ValueError):
            continue
    return next_id


def _normalize_chat_message(record: dict) -> dict:
    normalized = dict(record)
    normalized["id"] = int(normalized.get("id") or 0)
    normalized["user_id"] = int(normalized.get("user_id") or 0)
    normalized["admin_id"] = int(normalized.get("admin_id") or 0)
    normalized["direction"] = str(normalized.get("direction") or "")
    normalized["message"] = str(normalized.get("message") or "")
    normalized["created_at"] = str(normalized.get("created_at") or "")
    return normalized


def _normalize_assignment(record: dict) -> dict:
    normalized = dict(record)
    normalized["user_id"] = int(normalized.get("user_id") or 0)
    normalized["assigned_admin_id"] = int(normalized.get("assigned_admin_id") or 0)
    normalized["status"] = str(normalized.get("status") or "open")
    normalized["updated_at"] = str(normalized.get("updated_at") or "")
    return normalized


def _add_chat_message_sync(data: dict) -> dict:
    worksheet = _get_worksheet_sync(
        GOOGLE_SHEETS_CHATS_WORKSHEET_NAME,
        CHAT_HEADERS,
        rows=3000,
        cols=20,
    )
    records = _run_with_retries_sync(
        lambda: worksheet.get_all_records(expected_headers=CHAT_HEADERS),
        "Читання історії чату",
    )
    record = {
        "id": _next_id(records),
        "user_id": int(data["user_id"]),
        "direction": data["direction"],
        "admin_id": int(data.get("admin_id") or 0),
        "message": data["message"],
        "created_at": data.get("created_at") or datetime.now(BUSINESS_TIMEZONE).isoformat(),
    }
    row = [str(record.get(header, "")) for header in CHAT_HEADERS]
    _run_with_retries_sync(lambda: worksheet.append_row(row), "Запис повідомлення чату")
    return record


async def add_chat_message_to_google_sheets(data: dict) -> dict:
    if not _is_configured():
        raise RuntimeError("Google Sheets не налаштовано для історії чату.")
    return await asyncio.to_thread(_add_chat_message_sync, data)


def _get_chat_messages_sync(user_id: int, limit: int = 8) -> list[dict]:
    worksheet = _get_worksheet_sync(
        GOOGLE_SHEETS_CHATS_WORKSHEET_NAME,
        CHAT_HEADERS,
        rows=3000,
        cols=20,
    )
    records = _run_with_retries_sync(
        lambda: worksheet.get_all_records(expected_headers=CHAT_HEADERS),
        "Читання історії чату",
    )
    messages = [
        _normalize_chat_message(record)
        for record in records
        if str(record.get("user_id") or "") == str(user_id)
    ]
    messages.sort(key=lambda item: (item["created_at"], item["id"]))
    return messages[-limit:]


async def get_chat_messages_from_google_sheets(user_id: int, limit: int = 8) -> list[dict]:
    if not _is_configured():
        return []
    return await asyncio.to_thread(_get_chat_messages_sync, user_id, limit)


def _set_chat_assignment_sync(user_id: int, admin_id: int, status: str = "open") -> dict:
    worksheet = _get_worksheet_sync(
        GOOGLE_SHEETS_CHAT_ASSIGNMENTS_WORKSHEET_NAME,
        CHAT_ASSIGNMENT_HEADERS,
        rows=1000,
        cols=10,
    )
    records = _run_with_retries_sync(
        lambda: worksheet.get_all_records(expected_headers=CHAT_ASSIGNMENT_HEADERS),
        "Читання закріплень чатів",
    )
    updated_at = datetime.now(BUSINESS_TIMEZONE).isoformat()
    row = [str(user_id), str(admin_id), status, updated_at]
    for index, record in enumerate(records, start=2):
        if str(record.get("user_id") or "") == str(user_id):
            _run_with_retries_sync(
                lambda: worksheet.update(f"A{index}:D{index}", [row]),
                "Оновлення закріплення чату",
            )
            return _normalize_assignment(
                {
                    "user_id": user_id,
                    "assigned_admin_id": admin_id,
                    "status": status,
                    "updated_at": updated_at,
                }
            )
    _run_with_retries_sync(lambda: worksheet.append_row(row), "Створення закріплення чату")
    return _normalize_assignment(
        {
            "user_id": user_id,
            "assigned_admin_id": admin_id,
            "status": status,
            "updated_at": updated_at,
        }
    )


async def set_chat_assignment_in_google_sheets(user_id: int, admin_id: int, status: str = "open") -> dict:
    if not _is_configured():
        raise RuntimeError("Google Sheets не налаштовано для закріплення чатів.")
    return await asyncio.to_thread(_set_chat_assignment_sync, user_id, admin_id, status)


def _get_chat_assignment_sync(user_id: int) -> dict | None:
    worksheet = _get_worksheet_sync(
        GOOGLE_SHEETS_CHAT_ASSIGNMENTS_WORKSHEET_NAME,
        CHAT_ASSIGNMENT_HEADERS,
        rows=1000,
        cols=10,
    )
    records = _run_with_retries_sync(
        lambda: worksheet.get_all_records(expected_headers=CHAT_ASSIGNMENT_HEADERS),
        "Читання закріплень чатів",
    )
    for record in records:
        if str(record.get("user_id") or "") == str(user_id):
            return _normalize_assignment(record)
    return None


async def get_chat_assignment_from_google_sheets(user_id: int) -> dict | None:
    if not _is_configured():
        return None
    return await asyncio.to_thread(_get_chat_assignment_sync, user_id)


def _get_chat_summaries_sync(limit: int = 10) -> list[dict]:
    messages_worksheet = _get_worksheet_sync(
        GOOGLE_SHEETS_CHATS_WORKSHEET_NAME,
        CHAT_HEADERS,
        rows=3000,
        cols=20,
    )
    assignments_worksheet = _get_worksheet_sync(
        GOOGLE_SHEETS_CHAT_ASSIGNMENTS_WORKSHEET_NAME,
        CHAT_ASSIGNMENT_HEADERS,
        rows=1000,
        cols=10,
    )
    messages = [
        _normalize_chat_message(record)
        for record in _run_with_retries_sync(
            lambda: messages_worksheet.get_all_records(expected_headers=CHAT_HEADERS),
            "Читання історії чату",
        )
        if record.get("user_id")
    ]
    assignments = {
        item["user_id"]: item
        for item in (
            _normalize_assignment(record)
            for record in _run_with_retries_sync(
                lambda: assignments_worksheet.get_all_records(expected_headers=CHAT_ASSIGNMENT_HEADERS),
                "Читання закріплень чатів",
            )
            if record.get("user_id")
        )
    }
    grouped: dict[int, dict] = {}
    for message in messages:
        grouped[message["user_id"]] = {
            "user_id": message["user_id"],
            "last_message": message["message"],
            "last_direction": message["direction"],
            "last_at": message["created_at"],
            "messages_count": grouped.get(message["user_id"], {}).get("messages_count", 0) + 1,
            "assigned_admin_id": assignments.get(message["user_id"], {}).get("assigned_admin_id", 0),
            "status": assignments.get(message["user_id"], {}).get("status", "open"),
        }
    summaries = list(grouped.values())
    summaries.sort(key=lambda item: item.get("last_at", ""), reverse=True)
    return summaries[:limit]


async def get_chat_summaries_from_google_sheets(limit: int = 10) -> list[dict]:
    if not _is_configured():
        return []
    return await asyncio.to_thread(_get_chat_summaries_sync, limit)


def _add_event_sync(data: dict) -> dict:
    worksheet = _get_worksheet_sync(
        GOOGLE_SHEETS_EVENTS_WORKSHEET_NAME,
        EVENT_HEADERS,
        rows=3000,
        cols=20,
    )
    records = _run_with_retries_sync(
        lambda: worksheet.get_all_records(expected_headers=EVENT_HEADERS),
        "Читання подій",
    )
    record = {
        "id": _next_id(records),
        "event_type": data["event_type"],
        "user_id": int(data.get("user_id") or 0),
        "admin_id": int(data.get("admin_id") or 0),
        "record_id": int(data.get("record_id") or 0),
        "details": data.get("details", ""),
        "created_at": data.get("created_at") or datetime.now(BUSINESS_TIMEZONE).isoformat(),
    }
    row = [str(record.get(header, "")) for header in EVENT_HEADERS]
    _run_with_retries_sync(lambda: worksheet.append_row(row), "Запис події")
    return record


async def add_event_to_google_sheets(data: dict) -> dict:
    if not _is_configured():
        raise RuntimeError("Google Sheets не налаштовано для подій.")
    return await asyncio.to_thread(_add_event_sync, data)


def _has_reminder_sync(record_id: int, reminder_type: str) -> bool:
    worksheet = _get_worksheet_sync(
        GOOGLE_SHEETS_REMINDERS_WORKSHEET_NAME,
        REMINDER_HEADERS,
        rows=2000,
        cols=10,
    )
    records = _run_with_retries_sync(
        lambda: worksheet.get_all_records(expected_headers=REMINDER_HEADERS),
        "Читання нагадувань",
    )
    for record in records:
        if str(record.get("record_id") or "") == str(record_id) and record.get("reminder_type") == reminder_type:
            return True
    return False


async def has_reminder_in_google_sheets(record_id: int, reminder_type: str) -> bool:
    if not _is_configured():
        return False
    return await asyncio.to_thread(_has_reminder_sync, record_id, reminder_type)


def _mark_reminder_sync(record_id: int, reminder_type: str) -> None:
    worksheet = _get_worksheet_sync(
        GOOGLE_SHEETS_REMINDERS_WORKSHEET_NAME,
        REMINDER_HEADERS,
        rows=2000,
        cols=10,
    )
    row = [str(record_id), reminder_type, datetime.now(BUSINESS_TIMEZONE).isoformat()]
    _run_with_retries_sync(lambda: worksheet.append_row(row), "Запис нагадування")


async def mark_reminder_in_google_sheets(record_id: int, reminder_type: str) -> None:
    if not _is_configured():
        return
    await asyncio.to_thread(_mark_reminder_sync, record_id, reminder_type)
