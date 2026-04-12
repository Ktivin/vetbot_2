from datetime import datetime, timedelta

from config import BUSINESS_TIMEZONE


WEEKDAYS_SHORT = {
    0: "пн",
    1: "вт",
    2: "ср",
    3: "чт",
    4: "пт",
    5: "сб",
    6: "нд",
}

WEEKDAYS_FULL = {
    0: "понеділок",
    1: "вівторок",
    2: "середа",
    3: "четвер",
    4: "п’ятниця",
    5: "субота",
    6: "неділя",
}

STATUS_LABELS = {
    "pending": "Очікує підтвердження",
    "confirmed": "Підтверджено",
    "cancelled": "Скасовано",
    "completed": "Завершено",
}


def parse_iso_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


def format_date_for_button(date: datetime) -> str:
    today = datetime.now(BUSINESS_TIMEZONE).date()
    selected_date = date.date()

    if selected_date == today:
        prefix = "Сьогодні"
    elif selected_date == today + timedelta(days=1):
        prefix = "Завтра"
    else:
        prefix = WEEKDAYS_FULL[date.weekday()].capitalize()

    return f"{prefix}, {date.strftime('%d.%m')}"


def format_date_for_display(date_str: str) -> str:
    date = parse_iso_date(date_str)
    return f"{date.strftime('%d.%m.%Y')}, {WEEKDAYS_FULL[date.weekday()]}"


def format_datetime_for_display(value: str | None) -> str:
    if not value:
        return "—"

    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value

    return dt.astimezone(BUSINESS_TIMEZONE).strftime("%d.%m.%Y %H:%M")


def format_status(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def format_username(username: str | None) -> str:
    from texts import NO_USERNAME

    return f"@{username}" if username else NO_USERNAME


def get_available_times(date_str: str, start_hour: int = 9, end_hour: int = 18) -> list[str]:
    selected_date = parse_iso_date(date_str).date()
    now = datetime.now(BUSINESS_TIMEZONE)
    current_date = now.date()

    available_times: list[str] = []
    for hour in range(start_hour, end_hour + 1):
        if selected_date == current_date and hour <= now.hour:
            continue
        available_times.append(f"{hour:02d}:00")

    return available_times
