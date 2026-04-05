# config.py — для хмари
import os
from zoneinfo import ZoneInfo


def _get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Не задано обов'язкову змінну середовища: {name}")
    return value


def _get_admin_user_id() -> int:
    raw_value = _get_required_env("ADMIN_USER_IDS")
    admin_ids: list[int] = []

    for part in raw_value.split(","):
        candidate = part.strip()
        if not candidate:
            continue
        try:
            admin_ids.append(int(candidate))
        except ValueError as error:
            raise RuntimeError(
                "Змінна середовища ADMIN_USER_IDS має містити лише цілі числа, розділені комами."
            ) from error

    if not admin_ids:
        raise RuntimeError("У змінній середовища ADMIN_USER_IDS немає жодного коректного ID.")

    return admin_ids


def _get_business_timezone() -> ZoneInfo:
    timezone_name = os.getenv("BOT_TIMEZONE", "Europe/Kyiv").strip() or "Europe/Kyiv"
    try:
        return ZoneInfo(timezone_name)
    except Exception as error:
        raise RuntimeError(
            f"Не вдалося завантажити часовий пояс '{timezone_name}' для BOT_TIMEZONE."
        ) from error


BOT_TOKEN = _get_required_env("BOT_TOKEN")
ADMIN_USER_IDS = _get_admin_user_id()
BUSINESS_TIMEZONE = _get_business_timezone()
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()
GOOGLE_SHEETS_WORKSHEET_NAME = os.getenv("GOOGLE_SHEETS_WORKSHEET_NAME", "Clients").strip() or "Clients"
GOOGLE_SHEETS_CONSULTATIONS_WORKSHEET_NAME = (
    os.getenv("GOOGLE_SHEETS_CONSULTATIONS_WORKSHEET_NAME", "Consultations").strip()
    or "Consultations"
)
GOOGLE_SHEETS_SYSTEM_WORKSHEET_NAME = (
    os.getenv("GOOGLE_SHEETS_SYSTEM_WORKSHEET_NAME", "_system").strip()
    or "_system"
)
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
