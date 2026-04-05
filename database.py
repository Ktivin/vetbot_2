import logging

import aiosqlite
from datetime import datetime, timedelta

from config import BUSINESS_TIMEZONE
from integrations.google_sheets_consultations import (
    add_consultation_to_google_sheets,
    delete_old_consultations_in_google_sheets,
    get_admin_counts_from_google_sheets,
    get_consultation_by_id_from_google_sheets,
    get_consultations_from_google_sheets,
    is_google_sheets_consultations_enabled,
    is_slot_available_in_google_sheets,
    update_consultation_status_in_google_sheets,
)
from integrations.google_sheets_store import get_client_profile_from_google_sheets


DB_NAME = "consultations.db"
logger = logging.getLogger(__name__)
CONSULTATION_COLUMNS = (
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
)
CLIENT_COLUMNS = (
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
)


def _row_to_consultation(row: tuple | None) -> dict | None:
    if row is None:
        return None
    return dict(zip(CONSULTATION_COLUMNS, row))


def _row_to_client(row: tuple | None) -> dict | None:
    if row is None:
        return None
    return dict(zip(CLIENT_COLUMNS, row))


async def _get_client_profile_local(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT * FROM clients WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return _row_to_client(row)


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS consultations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                specialist TEXT,
                consultation_type TEXT,
                city TEXT,
                date TEXT,
                time TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS clients (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone_number TEXT,
                pet_name TEXT,
                pet_breed TEXT,
                pet_age TEXT,
                pet_weight TEXT,
                issue_description TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        await db.commit()


async def add_consultation(data: dict) -> int:
    if is_google_sheets_consultations_enabled():
        return await add_consultation_to_google_sheets(data)

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            INSERT INTO consultations
            (user_id, username, specialist, consultation_type, city, date, time, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["user_id"],
                data.get("username", ""),
                data["specialist"],
                data["consultation_type"],
                data.get("city", ""),
                data["date"],
                data["time"],
                datetime.now(BUSINESS_TIMEZONE).isoformat(),
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def get_all_consultations():
    if is_google_sheets_consultations_enabled():
        return await get_consultations_from_google_sheets("all")

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT * FROM consultations ORDER BY date, time, created_at"
        ) as cursor:
            rows = await cursor.fetchall()
            return [_row_to_consultation(row) for row in rows]


async def get_consultations(filter_name: str = "all") -> list[dict]:
    if is_google_sheets_consultations_enabled():
        return await get_consultations_from_google_sheets(filter_name)

    query = "SELECT * FROM consultations"
    params: list[str] = []
    clauses: list[str] = []

    today = datetime.now(BUSINESS_TIMEZONE).date()

    if filter_name == "pending":
        clauses.append("status = ?")
        params.append("pending")
    elif filter_name == "confirmed":
        clauses.append("status = ?")
        params.append("confirmed")
    elif filter_name == "today":
        clauses.append("date = ?")
        params.append(today.isoformat())
    elif filter_name == "tomorrow":
        clauses.append("date = ?")
        params.append((today + timedelta(days=1)).isoformat())

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " ORDER BY date, time, created_at"

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [_row_to_consultation(row) for row in rows]


async def get_consultation_by_id(record_id: int) -> dict | None:
    if is_google_sheets_consultations_enabled():
        return await get_consultation_by_id_from_google_sheets(record_id)

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT * FROM consultations WHERE id = ?",
            (record_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return _row_to_consultation(row)


async def get_client_profile(user_id: int) -> dict | None:
    local_profile = await _get_client_profile_local(user_id)
    if local_profile:
        return local_profile

    google_profile = await get_client_profile_from_google_sheets(user_id)
    if not google_profile:
        return None

    cached_profile = await upsert_client_profile(google_profile, sync_to_google=False)
    logger.info("Профіль клієнта %s відновлено з Google Sheets у локальний кеш.", user_id)
    return cached_profile


async def upsert_client_profile(data: dict, sync_to_google: bool = True) -> dict:
    existing_profile = await _get_client_profile_local(data["user_id"])
    created_at = (
        existing_profile["created_at"]
        if existing_profile and existing_profile.get("created_at")
        else datetime.now(BUSINESS_TIMEZONE).isoformat()
    )
    updated_at = datetime.now(BUSINESS_TIMEZONE).isoformat()

    profile = {
        "user_id": data["user_id"],
        "username": data.get("username", ""),
        "first_name": data.get("first_name", ""),
        "last_name": data.get("last_name", ""),
        "phone_number": data.get("phone_number", ""),
        "pet_name": data.get("pet_name", ""),
        "pet_breed": data.get("pet_breed", ""),
        "pet_age": data.get("pet_age", ""),
        "pet_weight": data.get("pet_weight", ""),
        "issue_description": data.get("issue_description", ""),
        "created_at": created_at,
        "updated_at": updated_at,
    }

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO clients (
                user_id, username, first_name, last_name, phone_number,
                pet_name, pet_breed, pet_age, pet_weight, issue_description,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                phone_number = excluded.phone_number,
                pet_name = excluded.pet_name,
                pet_breed = excluded.pet_breed,
                pet_age = excluded.pet_age,
                pet_weight = excluded.pet_weight,
                issue_description = excluded.issue_description,
                updated_at = excluded.updated_at
            """,
            (
                profile["user_id"],
                profile["username"],
                profile["first_name"],
                profile["last_name"],
                profile["phone_number"],
                profile["pet_name"],
                profile["pet_breed"],
                profile["pet_age"],
                profile["pet_weight"],
                profile["issue_description"],
                profile["created_at"],
                profile["updated_at"],
            ),
        )
        await db.commit()

    if sync_to_google:
        from integrations.google_sheets_store import sync_client_profile

        await sync_client_profile(profile)

    return profile


async def update_consultation_status(record_id: int, new_status: str) -> bool:
    if is_google_sheets_consultations_enabled():
        return await update_consultation_status_in_google_sheets(record_id, new_status)

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "UPDATE consultations SET status = ? WHERE id = ?",
            (new_status, record_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_admin_counts() -> dict[str, int]:
    if is_google_sheets_consultations_enabled():
        return await get_admin_counts_from_google_sheets()

    today = datetime.now(BUSINESS_TIMEZONE).date()
    tomorrow = today + timedelta(days=1)

    async with aiosqlite.connect(DB_NAME) as db:
        counts = {}

        async with db.execute("SELECT COUNT(*) FROM consultations") as cursor:
            counts["all"] = (await cursor.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM consultations WHERE status = ?",
            ("pending",),
        ) as cursor:
            counts["pending"] = (await cursor.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM consultations WHERE status = ?",
            ("confirmed",),
        ) as cursor:
            counts["confirmed"] = (await cursor.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM consultations WHERE date = ?",
            (today.isoformat(),),
        ) as cursor:
            counts["today"] = (await cursor.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM consultations WHERE date = ?",
            (tomorrow.isoformat(),),
        ) as cursor:
            counts["tomorrow"] = (await cursor.fetchone())[0]

        return counts


async def is_slot_available(
    specialist: str,
    date: str,
    time: str,
    city: str | None = None,
) -> bool:
    if is_google_sheets_consultations_enabled():
        return await is_slot_available_in_google_sheets(specialist, date, time, city)

    """
    Перевіряє, чи вільний слот.
    Якщо місто не вказано, вважаємо консультацію онлайн.
    Інакше перевіряємо зайнятість слота в конкретному місті.
    Перевірка виконується в межах конкретного фахівця.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        if not city or city.strip() == "":
            query = (
                "SELECT 1 FROM consultations "
                "WHERE specialist = ? AND date = ? AND time = ? "
                "AND status IN ('pending', 'confirmed')"
            )
            params = (specialist, date, time)
        else:
            query = (
                "SELECT 1 FROM consultations "
                "WHERE specialist = ? AND date = ? AND time = ? AND city = ? "
                "AND status IN ('pending', 'confirmed')"
            )
            params = (specialist, date, time, city)

        async with db.execute(query, params) as cursor:
            result = await cursor.fetchone()
            return result is None


async def delete_old_consultations():
    if is_google_sheets_consultations_enabled():
        return await delete_old_consultations_in_google_sheets()

    """
    Видаляє записи, дата яких уже минула.
    Викликається щодня о 03:00 за часовим поясом бота.
    """
    today = datetime.now(BUSINESS_TIMEZONE).date()
    cutoff_date = today.isoformat()

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "DELETE FROM consultations WHERE date < ?",
            (cutoff_date,),
        )
        deleted = cursor.rowcount
        await db.commit()
        logger.info("Автоочистка завершена. Видалено %s застарілих записів.", deleted)
        return deleted
