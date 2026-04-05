import asyncio
import json
import logging

from config import (
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_SHEETS_SPREADSHEET_ID,
    GOOGLE_SHEETS_WORKSHEET_NAME,
)


logger = logging.getLogger(__name__)


def _is_configured() -> bool:
    return bool(GOOGLE_SHEETS_SPREADSHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON)


def is_google_sheets_enabled() -> bool:
    return _is_configured()


def _sync_profile_sync(profile: dict) -> None:
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
        worksheet.append_row(
            [
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
        )

    worksheet.append_row(
        [
            profile["user_id"],
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
    )


async def sync_client_profile(profile: dict) -> None:
    if not _is_configured():
        return

    try:
        await asyncio.to_thread(_sync_profile_sync, profile)
    except Exception:
        logger.exception("Не вдалося синхронізувати профіль клієнта з Google Sheets.")
