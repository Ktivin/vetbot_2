import asyncio
import json
import logging
import time

from config import (
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_SHEETS_SPREADSHEET_ID,
    GOOGLE_SHEETS_WORKSHEET_NAME,
)


logger = logging.getLogger(__name__)
CLIENT_HEADERS = [
    "user_id",
    "username",
    "first_name",
    "last_name",
    "phone_number",
    "pet_name",
    "pet_breed",
    "pet_age",
    "pet_weight",
    "issue_description",
    "created_at",
    "updated_at",
]
CLIENTS_CACHE_TTL_SECONDS = 20
_clients_cache: dict[str, object] = {
    "records": None,
    "expires_at": 0.0,
}
_spreadsheet_cache = None
_worksheet_cache = None
_headers_initialized = False


def _is_configured() -> bool:
    return bool(GOOGLE_SHEETS_SPREADSHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON)


def is_google_sheets_enabled() -> bool:
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


def _get_cached_profiles() -> list[dict] | None:
    records = _clients_cache.get("records")
    expires_at = float(_clients_cache.get("expires_at", 0.0) or 0.0)
    if not records or time.monotonic() >= expires_at:
        return None
    return [dict(record) for record in records]


def _set_cached_profiles(records: list[dict], ttl_seconds: int = CLIENTS_CACHE_TTL_SECONDS) -> None:
    _clients_cache["records"] = [dict(record) for record in records]
    _clients_cache["expires_at"] = time.monotonic() + ttl_seconds


def _invalidate_clients_cache() -> None:
    _clients_cache["records"] = None
    _clients_cache["expires_at"] = 0.0


def _get_worksheet_sync():
    global _spreadsheet_cache, _worksheet_cache, _headers_initialized
    if _worksheet_cache is not None and _headers_initialized:
        return _worksheet_cache

    import gspread

    if _spreadsheet_cache is None:
        credentials = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        client = gspread.service_account_from_dict(credentials)
        _spreadsheet_cache = _run_with_retries_sync(
            lambda: client.open_by_key(GOOGLE_SHEETS_SPREADSHEET_ID),
            "Підключення до Google Sheets",
        )
    spreadsheet = _spreadsheet_cache

    if _worksheet_cache is None:
        try:
            worksheet = _run_with_retries_sync(
                lambda: spreadsheet.worksheet(GOOGLE_SHEETS_WORKSHEET_NAME),
                f"Отримання вкладки {GOOGLE_SHEETS_WORKSHEET_NAME}",
            )
        except gspread.WorksheetNotFound:
            worksheet = _run_with_retries_sync(
                lambda: spreadsheet.add_worksheet(
                    title=GOOGLE_SHEETS_WORKSHEET_NAME,
                    rows=1000,
                    cols=20,
                ),
                f"Створення вкладки {GOOGLE_SHEETS_WORKSHEET_NAME}",
            )
        _worksheet_cache = worksheet
    else:
        worksheet = _worksheet_cache

    if not _headers_initialized:
        existing_headers = _run_with_retries_sync(
            lambda: worksheet.row_values(1),
            f"Читання заголовків вкладки {GOOGLE_SHEETS_WORKSHEET_NAME}",
        )
        if existing_headers != CLIENT_HEADERS:
            if existing_headers:
                _run_with_retries_sync(
                    lambda: worksheet.update("A1:L1", [CLIENT_HEADERS]),
                    f"Оновлення заголовків вкладки {GOOGLE_SHEETS_WORKSHEET_NAME}",
                )
            else:
                _run_with_retries_sync(
                    lambda: worksheet.append_row(CLIENT_HEADERS),
                    f"Запис заголовків вкладки {GOOGLE_SHEETS_WORKSHEET_NAME}",
                )
        _headers_initialized = True

    return worksheet


def _profile_to_row(profile: dict) -> list[str]:
    return [
        str(profile.get("user_id", "")),
        profile.get("username", ""),
        profile.get("first_name", ""),
        profile.get("last_name", ""),
        profile.get("phone_number", ""),
        profile.get("pet_name", ""),
        profile.get("pet_breed", ""),
        profile.get("pet_age", ""),
        profile.get("pet_weight", ""),
        profile.get("issue_description", ""),
        profile.get("created_at", ""),
        profile.get("updated_at", ""),
    ]


def _normalize_profile(profile: dict) -> dict:
    normalized = dict(profile)
    normalized["user_id"] = int(normalized["user_id"])
    for key in CLIENT_HEADERS[1:]:
        normalized[key] = str(normalized.get(key, "") or "").strip()
    return normalized


def _read_all_profiles_sync() -> list[dict]:
    worksheet = _get_worksheet_sync()
    rows = _run_with_retries_sync(
        lambda: worksheet.get_all_records(expected_headers=CLIENT_HEADERS),
        f"Читання профілів із вкладки {GOOGLE_SHEETS_WORKSHEET_NAME}",
    )
    records: list[dict] = []
    for row in rows:
        if not row.get("user_id"):
            continue
        try:
            records.append(_normalize_profile(row))
        except (TypeError, ValueError):
            continue
    records.sort(
        key=lambda item: (
            item.get("updated_at", ""),
            item.get("created_at", ""),
            item["user_id"],
        ),
        reverse=True,
    )
    return records


def _sync_profile_sync(profile: dict) -> None:
    worksheet = _get_worksheet_sync()
    user_id = str(profile["user_id"])
    existing_user_ids = worksheet.col_values(1)
    row_values = _profile_to_row(profile)

    for index, existing_user_id in enumerate(existing_user_ids[1:], start=2):
        if existing_user_id.strip() == user_id:
            _run_with_retries_sync(
                lambda: worksheet.batch_clear([f"M{index}:Z{index}"]),
                f"Очищення зайвих клітинок профілю {user_id}",
            )
            _run_with_retries_sync(
                lambda: worksheet.update(f"A{index}:L{index}", [row_values]),
                f"Оновлення профілю клієнта {user_id}",
            )
            logger.info(
                "Профіль клієнта %s оновлено в Google Sheets (%s / %s).",
                user_id,
                GOOGLE_SHEETS_SPREADSHEET_ID,
                GOOGLE_SHEETS_WORKSHEET_NAME,
            )
            cached_profiles = _clients_cache.get("records")
            normalized_profile = _normalize_profile(profile)
            if cached_profiles:
                updated_profiles = []
                replaced = False
                for cached_profile in cached_profiles:
                    if int(cached_profile["user_id"]) == int(user_id):
                        updated_profiles.append(normalized_profile)
                        replaced = True
                    else:
                        updated_profiles.append(dict(cached_profile))
                if not replaced:
                    updated_profiles.append(normalized_profile)
                updated_profiles.sort(
                    key=lambda item: (
                        item.get("updated_at", ""),
                        item.get("created_at", ""),
                        item["user_id"],
                    ),
                    reverse=True,
                )
                _set_cached_profiles(updated_profiles)
            else:
                _invalidate_clients_cache()
            return

    _run_with_retries_sync(
        lambda: worksheet.append_row(row_values),
        f"Створення профілю клієнта {user_id}",
    )
    logger.info(
        "Профіль клієнта %s додано в Google Sheets (%s / %s).",
        user_id,
        GOOGLE_SHEETS_SPREADSHEET_ID,
        GOOGLE_SHEETS_WORKSHEET_NAME,
    )
    cached_profiles = _clients_cache.get("records")
    normalized_profile = _normalize_profile(profile)
    if cached_profiles:
        updated_profiles = [dict(item) for item in cached_profiles]
        updated_profiles.append(normalized_profile)
        updated_profiles.sort(
            key=lambda item: (
                item.get("updated_at", ""),
                item.get("created_at", ""),
                item["user_id"],
            ),
            reverse=True,
        )
        _set_cached_profiles(updated_profiles)
    else:
        _invalidate_clients_cache()


async def sync_client_profile(profile: dict) -> None:
    if not _is_configured():
        return

    try:
        await asyncio.to_thread(_sync_profile_sync, profile)
    except Exception:
        logger.exception("Не вдалося синхронізувати профіль клієнта з Google Sheets.")


def _get_profile_sync(user_id: int) -> dict | None:
    cached_profiles = _get_cached_profiles()
    if cached_profiles is not None:
        for profile in cached_profiles:
            if int(profile["user_id"]) == user_id:
                logger.info(
                    "Профіль клієнта %s знайдено в кеші Google Sheets (%s / %s).",
                    user_id,
                    GOOGLE_SHEETS_SPREADSHEET_ID,
                    GOOGLE_SHEETS_WORKSHEET_NAME,
                )
                return dict(profile)

    worksheet = _get_worksheet_sync()
    rows = _run_with_retries_sync(
        lambda: worksheet.get_all_values(),
        f"Читання профілів із вкладки {GOOGLE_SHEETS_WORKSHEET_NAME}",
    )
    if not rows:
        return None

    headers = rows[0]
    header_map = {header: index for index, header in enumerate(headers)}
    user_id_column = header_map.get("user_id")
    if user_id_column is None:
        return None

    expected_user_id = str(user_id)
    for row in rows[1:]:
        if user_id_column >= len(row):
            continue
        if row[user_id_column].strip() != expected_user_id:
            continue

        profile: dict[str, str | int] = {"user_id": user_id}
        for header in CLIENT_HEADERS[1:]:
            column_index = header_map.get(header)
            if column_index is None or column_index >= len(row):
                profile[header] = ""
            else:
                profile[header] = row[column_index].strip()

        logger.info(
            "Профіль клієнта %s знайдено в Google Sheets (%s / %s).",
            expected_user_id,
            GOOGLE_SHEETS_SPREADSHEET_ID,
            GOOGLE_SHEETS_WORKSHEET_NAME,
        )
        return profile

    return None


def _delete_profile_sync(user_id: int) -> bool:
    worksheet = _get_worksheet_sync()
    expected_user_id = str(user_id)
    user_ids = _run_with_retries_sync(
        lambda: worksheet.col_values(1),
        f"Читання user_id профілів із вкладки {GOOGLE_SHEETS_WORKSHEET_NAME}",
    )

    for index, existing_user_id in enumerate(user_ids[1:], start=2):
        if existing_user_id.strip() != expected_user_id:
            continue

        _run_with_retries_sync(
            lambda: worksheet.delete_rows(index),
            f"Видалення профілю клієнта {user_id}",
        )
        cached_profiles = _clients_cache.get("records")
        if cached_profiles:
            filtered_profiles = [
                dict(item) for item in cached_profiles if int(item["user_id"]) != user_id
            ]
            _set_cached_profiles(filtered_profiles)
        else:
            _invalidate_clients_cache()
        logger.info(
            "Профіль клієнта %s видалено з Google Sheets (%s / %s).",
            user_id,
            GOOGLE_SHEETS_SPREADSHEET_ID,
            GOOGLE_SHEETS_WORKSHEET_NAME,
        )
        return True

    return False


async def get_client_profile_from_google_sheets(user_id: int) -> dict | None:
    if not _is_configured():
        return None

    try:
        return await asyncio.to_thread(_get_profile_sync, user_id)
    except Exception:
        logger.exception("Не вдалося отримати профіль клієнта з Google Sheets.")
        return None


async def get_all_client_profiles_from_google_sheets() -> list[dict]:
    if not _is_configured():
        return []

    cached_profiles = _get_cached_profiles()
    if cached_profiles is not None:
        return cached_profiles

    try:
        records = await asyncio.to_thread(_read_all_profiles_sync)
        _set_cached_profiles(records)
        return records
    except Exception as error:
        stale_profiles = _clients_cache.get("records")
        if stale_profiles and _is_retryable_error(error):
            logger.warning(
                "Перевищено квоту або тимчасово недоступне читання Google Sheets. Використовую кешовані профілі клієнтів."
            )
            return [dict(profile) for profile in stale_profiles]
        logger.exception("Не вдалося отримати список профілів клієнтів із Google Sheets.")
        return []


async def delete_client_profile_from_google_sheets(user_id: int) -> bool:
    if not _is_configured():
        return False

    try:
        return await asyncio.to_thread(_delete_profile_sync, user_id)
    except Exception:
        logger.exception("Не вдалося видалити профіль клієнта з Google Sheets.")
        return False
