import asyncio
import json
import logging

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


def _is_configured() -> bool:
    return bool(GOOGLE_SHEETS_SPREADSHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON)


def is_google_sheets_enabled() -> bool:
    return _is_configured()


def _get_worksheet_sync():
    import gspread

    credentials = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    client = gspread.service_account_from_dict(credentials)
    spreadsheet = client.open_by_key(GOOGLE_SHEETS_SPREADSHEET_ID)

    try:
        worksheet = spreadsheet.worksheet(GOOGLE_SHEETS_WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=GOOGLE_SHEETS_WORKSHEET_NAME,
            rows=1000,
            cols=20,
        )

    existing_headers = worksheet.row_values(1)
    if existing_headers != CLIENT_HEADERS:
        if existing_headers:
            worksheet.update("A1:L1", [CLIENT_HEADERS])
        else:
            worksheet.append_row(CLIENT_HEADERS)

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


def _sync_profile_sync(profile: dict) -> None:
    worksheet = _get_worksheet_sync()
    user_id = str(profile["user_id"])
    existing_user_ids = worksheet.col_values(1)
    row_values = _profile_to_row(profile)

    for index, existing_user_id in enumerate(existing_user_ids[1:], start=2):
        if existing_user_id.strip() == user_id:
            worksheet.update(f"A{index}:L{index}", [row_values])
            logger.info(
                "Профіль клієнта %s оновлено в Google Sheets (%s / %s).",
                user_id,
                GOOGLE_SHEETS_SPREADSHEET_ID,
                GOOGLE_SHEETS_WORKSHEET_NAME,
            )
            return

    worksheet.append_row(row_values)
    logger.info(
        "Профіль клієнта %s додано в Google Sheets (%s / %s).",
        user_id,
        GOOGLE_SHEETS_SPREADSHEET_ID,
        GOOGLE_SHEETS_WORKSHEET_NAME,
    )


async def sync_client_profile(profile: dict) -> None:
    if not _is_configured():
        return

    try:
        await asyncio.to_thread(_sync_profile_sync, profile)
    except Exception:
        logger.exception("Не вдалося синхронізувати профіль клієнта з Google Sheets.")


def _get_profile_sync(user_id: int) -> dict | None:
    worksheet = _get_worksheet_sync()
    rows = worksheet.get_all_values()
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


async def get_client_profile_from_google_sheets(user_id: int) -> dict | None:
    if not _is_configured():
        return None

    try:
        return await asyncio.to_thread(_get_profile_sync, user_id)
    except Exception:
        logger.exception("Не вдалося отримати профіль клієнта з Google Sheets.")
        return None
