import asyncio
import json
import logging
import time
from datetime import datetime, timedelta

from config import (
    BUSINESS_TIMEZONE,
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_SHEETS_CONSULTATIONS_WORKSHEET_NAME,
    GOOGLE_SHEETS_SPREADSHEET_ID,
    GOOGLE_SHEETS_SYSTEM_WORKSHEET_NAME,
)


logger = logging.getLogger(__name__)
CONSULTATION_HEADERS = [
    "id",
    "user_id",
    "username",
    "specialist",
    "consultation_type",
    "city",
    "date",
    "time",
    "status",
    "created_at",
]
SYSTEM_HEADERS = [
    "key",
    "owner",
    "expires_at",
    "updated_at",
]
POLLING_LOCK_KEY = "polling_lock"
CONSULTATIONS_CACHE_TTL_SECONDS = 20
POLLING_LOCK_TTL_SECONDS = 75
_consultations_cache: dict[str, object] = {
    "records": None,
    "expires_at": 0.0,
}
_spreadsheet_cache = None
_worksheet_cache: dict[str, object] = {}
_headers_initialized: set[str] = set()


def _is_configured() -> bool:
    return bool(GOOGLE_SHEETS_SPREADSHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON)


def is_google_sheets_consultations_enabled() -> bool:
    return _is_configured()


def _is_retryable_error(error: Exception) -> bool:
    error_text = str(error)
    return any(
        marker in error_text
        for marker in (
            "[429]",
            "Quota exceeded",
            "503",
            "500",
            "timed out",
            "temporarily unavailable",
        )
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


def _get_cached_consultations() -> list[dict] | None:
    records = _consultations_cache.get("records")
    expires_at = float(_consultations_cache.get("expires_at", 0.0) or 0.0)
    if not records or time.monotonic() >= expires_at:
        return None
    return [dict(record) for record in records]  # return a copy for safety


def _set_cached_consultations(records: list[dict], ttl_seconds: int = CONSULTATIONS_CACHE_TTL_SECONDS) -> None:
    _consultations_cache["records"] = [dict(record) for record in records]
    _consultations_cache["expires_at"] = time.monotonic() + ttl_seconds


def _invalidate_consultations_cache() -> None:
    _consultations_cache["records"] = None
    _consultations_cache["expires_at"] = 0.0


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


def _consultation_to_row(record: dict) -> list[str]:
    return [
        str(record.get("id", "")),
        str(record.get("user_id", "")),
        record.get("username", ""),
        record.get("specialist", ""),
        record.get("consultation_type", ""),
        record.get("city", ""),
        record.get("date", ""),
        record.get("time", ""),
        record.get("status", "pending"),
        record.get("created_at", ""),
    ]


def _normalize_consultation(record: dict) -> dict:
    normalized = dict(record)
    normalized["id"] = int(normalized["id"])
    normalized["user_id"] = int(normalized["user_id"])
    normalized["username"] = normalized.get("username", "") or ""
    normalized["city"] = normalized.get("city", "") or ""
    normalized["status"] = normalized.get("status", "pending") or "pending"
    return normalized


def _read_all_consultations_sync() -> list[dict]:
    worksheet = _get_worksheet_sync(
        GOOGLE_SHEETS_CONSULTATIONS_WORKSHEET_NAME,
        CONSULTATION_HEADERS,
        rows=2000,
        cols=20,
    )
    rows = _run_with_retries_sync(
        lambda: worksheet.get_all_records(expected_headers=CONSULTATION_HEADERS),
        "Читання записів консультацій",
    )
    records: list[dict] = []
    for row in rows:
        if not row.get("id"):
            continue
        records.append(_normalize_consultation(row))
    return records


async def get_consultations_from_google_sheets(filter_name: str = "all") -> list[dict]:
    if not _is_configured():
        return []

    cached_records = _get_cached_consultations()
    if cached_records is not None:
        records = cached_records
    else:
        try:
            records = await asyncio.to_thread(_read_all_consultations_sync)
            _set_cached_consultations(records)
        except Exception as error:
            stale_records = _consultations_cache.get("records")
            if stale_records and _is_retryable_error(error):
                logger.warning(
                    "Перевищено квоту або тимчасово недоступне читання Google Sheets. Використовую кешовані записи консультацій."
                )
                records = [dict(record) for record in stale_records]
            else:
                raise
    today = datetime.now(BUSINESS_TIMEZONE).date()

    if filter_name == "pending":
        records = [record for record in records if record["status"] == "pending"]
    elif filter_name == "confirmed":
        records = [record for record in records if record["status"] == "confirmed"]
    elif filter_name == "cancelled":
        records = [record for record in records if record["status"] == "cancelled"]
    elif filter_name == "completed":
        records = [record for record in records if record["status"] == "completed"]
    elif filter_name == "today":
        records = [record for record in records if record["date"] == today.isoformat()]
    elif filter_name == "tomorrow":
        records = [record for record in records if record["date"] == (today + timedelta(days=1)).isoformat()]

    records.sort(key=lambda item: (item["date"], item["time"], item["created_at"], item["id"]))
    return records


async def get_consultation_by_id_from_google_sheets(record_id: int) -> dict | None:
    records = await get_consultations_from_google_sheets("all")
    for record in records:
        if record["id"] == record_id:
            return record
    return None


def _add_consultation_sync(data: dict) -> int:
    worksheet = _get_worksheet_sync(
        GOOGLE_SHEETS_CONSULTATIONS_WORKSHEET_NAME,
        CONSULTATION_HEADERS,
        rows=2000,
        cols=20,
    )
    rows = _run_with_retries_sync(
        lambda: worksheet.get_all_records(expected_headers=CONSULTATION_HEADERS),
        "Читання записів перед додаванням консультації",
    )
    next_id = 1
    for row in rows:
        try:
            next_id = max(next_id, int(row.get("id", 0)) + 1)
        except (TypeError, ValueError):
            continue

    record = {
        "id": next_id,
        "user_id": data["user_id"],
        "username": data.get("username", ""),
        "specialist": data["specialist"],
        "consultation_type": data["consultation_type"],
        "city": data.get("city", ""),
        "date": data["date"],
        "time": data["time"],
        "status": data.get("status", "pending") or "pending",
        "created_at": datetime.now(BUSINESS_TIMEZONE).isoformat(),
    }
    _run_with_retries_sync(
        lambda: worksheet.append_row(_consultation_to_row(record)),
        "Запис консультації в Google Sheets",
    )
    cached_records = _consultations_cache.get("records")
    if cached_records:
        updated_records = [dict(item) for item in cached_records]
        updated_records.append(record)
        updated_records.sort(key=lambda item: (item["date"], item["time"], item["created_at"], item["id"]))
        _set_cached_consultations(updated_records)
    else:
        _invalidate_consultations_cache()
    logger.info(
        "Запис %s додано в Google Sheets (%s / %s).",
        next_id,
        GOOGLE_SHEETS_SPREADSHEET_ID,
        GOOGLE_SHEETS_CONSULTATIONS_WORKSHEET_NAME,
    )
    return next_id


async def add_consultation_to_google_sheets(data: dict) -> int:
    if not _is_configured():
        raise RuntimeError("Google Sheets не налаштовано для записів.")
    return await asyncio.to_thread(_add_consultation_sync, data)


def _find_consultation_row_index(worksheet, record_id: int) -> int | None:
    records = _run_with_retries_sync(
        lambda: worksheet.get_all_records(expected_headers=CONSULTATION_HEADERS),
        "Читання записів перед оновленням статусу",
    )
    for index, record in enumerate(records, start=2):
        try:
            if int(record.get("id", 0)) == record_id:
                return index
        except (TypeError, ValueError):
            continue
    return None


def _update_consultation_status_sync(record_id: int, new_status: str) -> bool:
    worksheet = _get_worksheet_sync(
        GOOGLE_SHEETS_CONSULTATIONS_WORKSHEET_NAME,
        CONSULTATION_HEADERS,
        rows=2000,
        cols=20,
    )
    row_index = _find_consultation_row_index(worksheet, record_id)
    if row_index is None:
        return False

    _run_with_retries_sync(
        lambda: worksheet.update(f"I{row_index}", [[new_status]]),
        f"Оновлення статусу запису {record_id}",
    )
    cached_records = _consultations_cache.get("records")
    if cached_records:
        updated_records = []
        for record in cached_records:
            updated_record = dict(record)
            if updated_record["id"] == record_id:
                updated_record["status"] = new_status
            updated_records.append(updated_record)
        _set_cached_consultations(updated_records)
    else:
        _invalidate_consultations_cache()
    logger.info(
        "Статус запису %s оновлено в Google Sheets: %s.",
        record_id,
        new_status,
    )
    return True


async def update_consultation_status_in_google_sheets(record_id: int, new_status: str) -> bool:
    if not _is_configured():
        return False
    return await asyncio.to_thread(_update_consultation_status_sync, record_id, new_status)


async def is_slot_available_in_google_sheets(
    specialist: str,
    date: str,
    time: str,
    city: str | None = None,
) -> bool:
    records = await get_consultations_from_google_sheets("all")
    normalized_city = (city or "").strip()
    for record in records:
        if record["specialist"] != specialist or record["date"] != date or record["time"] != time:
            continue
        if record["status"] not in {"pending", "confirmed"}:
            continue
        record_city = (record.get("city", "") or "").strip()
        if normalized_city:
            if record_city == normalized_city:
                return False
        else:
            if not record_city:
                return False
    return True


async def get_admin_counts_from_google_sheets() -> dict[str, int]:
    records = await get_consultations_from_google_sheets("all")
    today = datetime.now(BUSINESS_TIMEZONE).date().isoformat()
    tomorrow = (datetime.now(BUSINESS_TIMEZONE).date() + timedelta(days=1)).isoformat()
    return {
        "all": len(records),
        "pending": sum(1 for record in records if record["status"] == "pending"),
        "confirmed": sum(1 for record in records if record["status"] == "confirmed"),
        "cancelled": sum(1 for record in records if record["status"] == "cancelled"),
        "completed": sum(1 for record in records if record["status"] == "completed"),
        "today": sum(1 for record in records if record["date"] == today),
        "tomorrow": sum(1 for record in records if record["date"] == tomorrow),
    }


def _rewrite_consultations_sync(records: list[dict]) -> int:
    worksheet = _get_worksheet_sync(
        GOOGLE_SHEETS_CONSULTATIONS_WORKSHEET_NAME,
        CONSULTATION_HEADERS,
        rows=max(1000, len(records) + 10),
        cols=20,
    )
    all_rows = [CONSULTATION_HEADERS] + [_consultation_to_row(record) for record in records]
    _run_with_retries_sync(lambda: worksheet.clear(), "Очищення вкладки консультацій")
    _run_with_retries_sync(
        lambda: worksheet.update(f"A1:J{len(all_rows)}", all_rows),
        "Перезапис вкладки консультацій",
    )
    _set_cached_consultations(records)
    return len(records)


async def delete_old_consultations_in_google_sheets() -> int:
    if not _is_configured():
        return 0

    records = await get_consultations_from_google_sheets("all")
    today = datetime.now(BUSINESS_TIMEZONE).date().isoformat()
    fresh_records = [record for record in records if record["date"] >= today]
    deleted_count = len(records) - len(fresh_records)
    if deleted_count <= 0:
        return 0

    await asyncio.to_thread(_rewrite_consultations_sync, fresh_records)
    logger.info("Автоочистка Google Sheets завершена. Видалено %s застарілих записів.", deleted_count)
    return deleted_count


def _upsert_system_row_sync(key: str, owner: str, expires_at: str, updated_at: str) -> None:
    worksheet = _get_worksheet_sync(
        GOOGLE_SHEETS_SYSTEM_WORKSHEET_NAME,
        SYSTEM_HEADERS,
        rows=100,
        cols=10,
    )
    records = _run_with_retries_sync(
        lambda: worksheet.get_all_records(expected_headers=SYSTEM_HEADERS),
        "Читання системної вкладки",
    )
    for index, record in enumerate(records, start=2):
        if record.get("key") == key:
            _run_with_retries_sync(
                lambda: worksheet.update(f"A{index}:D{index}", [[key, owner, expires_at, updated_at]]),
                f"Оновлення системного ключа {key}",
            )
            return
    _run_with_retries_sync(
        lambda: worksheet.append_row([key, owner, expires_at, updated_at]),
        f"Створення системного ключа {key}",
    )


def _get_system_record_sync(key: str) -> dict | None:
    worksheet = _get_worksheet_sync(
        GOOGLE_SHEETS_SYSTEM_WORKSHEET_NAME,
        SYSTEM_HEADERS,
        rows=100,
        cols=10,
    )
    records = _run_with_retries_sync(
        lambda: worksheet.get_all_records(expected_headers=SYSTEM_HEADERS),
        "Читання системної вкладки",
    )
    for record in records:
        if record.get("key") == key:
            return record
    return None


def _parse_lock_expiration(raw_value: str, default_value: datetime) -> datetime:
    raw_value = raw_value.strip()
    if not raw_value:
        return default_value
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return default_value


def _acquire_polling_lock_sync(owner: str, ttl_seconds: int) -> bool:
    now = datetime.now(BUSINESS_TIMEZONE)
    record = _get_system_record_sync(POLLING_LOCK_KEY)
    if record:
        current_owner = (record.get("owner") or "").strip()
        expires_at = _parse_lock_expiration(
            str(record.get("expires_at") or ""),
            now - timedelta(seconds=1),
        )

        if current_owner and current_owner != owner and expires_at > now:
            return False

    _upsert_system_row_sync(
        POLLING_LOCK_KEY,
        owner,
        (now + timedelta(seconds=ttl_seconds)).isoformat(),
        now.isoformat(),
    )
    return True


async def acquire_polling_lock(owner: str, ttl_seconds: int = POLLING_LOCK_TTL_SECONDS) -> bool:
    if not _is_configured():
        return True
    try:
        return await asyncio.to_thread(_acquire_polling_lock_sync, owner, ttl_seconds)
    except Exception:
        logger.exception("Не вдалося отримати polling lock у Google Sheets.")
        return False


async def refresh_polling_lock(owner: str, ttl_seconds: int = POLLING_LOCK_TTL_SECONDS) -> bool:
    return await acquire_polling_lock(owner, ttl_seconds)


async def get_polling_lock_details() -> dict | None:
    if not _is_configured():
        return None
    try:
        return await asyncio.to_thread(_get_system_record_sync, POLLING_LOCK_KEY)
    except Exception:
        logger.exception("Не вдалося отримати деталі polling lock у Google Sheets.")
        return None


def _release_polling_lock_sync(owner: str) -> None:
    now = datetime.now(BUSINESS_TIMEZONE).isoformat()
    record = _get_system_record_sync(POLLING_LOCK_KEY)
    if not record:
        return
    if (record.get("owner") or "").strip() != owner:
        return
    _upsert_system_row_sync(POLLING_LOCK_KEY, "", "", now)


async def release_polling_lock(owner: str) -> None:
    if not _is_configured():
        return
    try:
        await asyncio.to_thread(_release_polling_lock_sync, owner)
    except Exception:
        logger.exception("Не вдалося звільнити polling lock у Google Sheets.")
