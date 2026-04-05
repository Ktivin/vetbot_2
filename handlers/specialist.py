import logging
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN_USER_IDS, BUSINESS_TIMEZONE
from database import add_consultation, get_client_profile, is_slot_available
from formatting import (
    format_date_for_button,
    format_date_for_display,
    format_username,
    get_available_times,
)
from texts import (
    ADMIN_NEW_RECORD_TITLE,
    BACK_BUTTON,
    BOOKING_CANCELED,
    BOOKING_SUCCESS_FOOTER,
    BOOKING_SUCCESS_TITLE,
    CANCEL_BUTTON,
    CHECK_SLOT_ERROR,
    CITY_LABELS,
    CONFIRM_BUTTON,
    CONSULTATION_TYPE_LABELS,
    KYNOLOGIST_TYPE_LABELS,
    NO_FREE_TIMES_FOR_DATE,
    NO_TIMES_LEFT_FOR_TODAY,
    PROMPT_CITY,
    PROMPT_CONSULTATION_FORMAT,
    PROMPT_DATE,
    PROMPT_SERVICE_FORMAT,
    PROMPT_TIME_FOR_DATE,
    SAVE_BOOKING_ERROR,
    SLOT_ALREADY_BOOKED_PICK_ANOTHER_DATE,
    SLOT_ALREADY_BOOKED_WITH_ALTERNATIVES,
    SPECIALIST_LABELS,
    SUMMARY_CITY,
    SUMMARY_DATE,
    SUMMARY_ISSUE,
    SUMMARY_NOTE,
    SUMMARY_PET_AGE,
    SUMMARY_PET_BREED,
    SUMMARY_PET_NAME,
    SUMMARY_PET_WEIGHT,
    SUMMARY_SPECIALIST,
    SUMMARY_TIME,
    SUMMARY_TITLE,
    SUMMARY_TYPE,
    ONBOARDING_REQUIRED_BEFORE_BOOKING,
    WELCOME_CHOOSE_SPECIALIST,
)


router = Router()
logger = logging.getLogger(__name__)


class ConsultationStates(StatesGroup):
    choosing_specialist = State()
    choosing_kyno_type = State()
    choosing_cons_type = State()
    choosing_city = State()
    choosing_date = State()
    choosing_time = State()
    confirming = State()


def _format_summary(data: dict) -> str:
    lines = [
        SUMMARY_TITLE,
        "",
        f"{SUMMARY_PET_NAME}: {data['pet_name']}",
        f"{SUMMARY_PET_BREED}: {data['pet_breed']}",
        f"{SUMMARY_PET_AGE}: {data['pet_age']}",
        f"{SUMMARY_PET_WEIGHT}: {data['pet_weight']}",
        f"{SUMMARY_SPECIALIST}: {data['specialist']}",
        f"{SUMMARY_TYPE}: {data['consultation_type']}",
        f"{SUMMARY_DATE}: {format_date_for_display(data['date'])}",
        f"{SUMMARY_TIME}: {data['time']}",
    ]
    city = data.get("city", "").strip()
    if city:
        lines.append(f"{SUMMARY_CITY}: {city}")
    lines.append(f"{SUMMARY_ISSUE}: {data['issue_description']}")
    lines.extend(["", SUMMARY_NOTE])
    return "\n".join(lines)


def _format_booking_created_message(data: dict) -> str:
    lines = [
        BOOKING_SUCCESS_TITLE,
        "",
        f"{SUMMARY_PET_NAME}: {data['pet_name']}",
        f"{SUMMARY_SPECIALIST}: {data['specialist']}",
        f"{SUMMARY_TYPE}: {data['consultation_type']}",
        f"{SUMMARY_DATE}: {format_date_for_display(data['date'])}",
        f"{SUMMARY_TIME}: {data['time']}",
    ]
    city = data.get("city", "").strip()
    if city:
        lines.append(f"{SUMMARY_CITY}: {city}")
    lines.extend(["", BOOKING_SUCCESS_FOOTER])
    return "\n".join(lines)


def _needs_city_selection(data: dict) -> bool:
    consultation_type = data.get("consultation_type")
    return consultation_type in {
        KYNOLOGIST_TYPE_LABELS["venue"],
        CONSULTATION_TYPE_LABELS["analysis"],
    }


def kynologist_types():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=KYNOLOGIST_TYPE_LABELS["online"], callback_data="kyno:online")],
            [InlineKeyboardButton(text=KYNOLOGIST_TYPE_LABELS["training"], callback_data="kyno:training")],
            [InlineKeyboardButton(text=KYNOLOGIST_TYPE_LABELS["venue"], callback_data="kyno:venue")],
            [InlineKeyboardButton(text=BACK_BUTTON, callback_data="back:main")],
        ]
    )


def consultation_types():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=CONSULTATION_TYPE_LABELS["online"], callback_data="cons:online")],
            [InlineKeyboardButton(text=CONSULTATION_TYPE_LABELS["analysis"], callback_data="cons:analysis")],
            [InlineKeyboardButton(text=CONSULTATION_TYPE_LABELS["call"], callback_data="cons:call")],
            [InlineKeyboardButton(text=CONSULTATION_TYPE_LABELS["message"], callback_data="cons:message")],
            [InlineKeyboardButton(text=BACK_BUTTON, callback_data="back:spec")],
        ]
    )


def venue_cities():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=CITY_LABELS["poltava"], callback_data="city:poltava")],
            [InlineKeyboardButton(text=CITY_LABELS["brovary"], callback_data="city:brovary")],
            [InlineKeyboardButton(text=CITY_LABELS["kyiv"], callback_data="city:kyiv")],
            [InlineKeyboardButton(text=BACK_BUTTON, callback_data="back:kyno")],
        ]
    )


def cities_for_offline():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=CITY_LABELS["poltava"], callback_data="city:poltava")],
            [InlineKeyboardButton(text=CITY_LABELS["brovary"], callback_data="city:brovary")],
            [InlineKeyboardButton(text=CITY_LABELS["kyiv"], callback_data="city:kyiv")],
            [InlineKeyboardButton(text=BACK_BUTTON, callback_data="back:cons_type")],
        ]
    )


def date_picker():
    today = datetime.now(BUSINESS_TIMEZONE)
    buttons = []
    current_row: list[InlineKeyboardButton] = []
    for i in range(7):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        current_row.append(
            InlineKeyboardButton(
                text=format_date_for_button(date),
                callback_data=f"date:{date_str}",
            )
        )
        if len(current_row) == 2:
            buttons.append(current_row)
            current_row = []

    if current_row:
        buttons.append(current_row)

    buttons.append([InlineKeyboardButton(text=BACK_BUTTON, callback_data="back:date")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def time_picker(date_str: str, available_times: list[str] | None = None):
    buttons = []
    times = available_times if available_times is not None else get_available_times(date_str)

    row: list[InlineKeyboardButton] = []
    for time_str in times:
        row.append(InlineKeyboardButton(text=time_str, callback_data=f"time:{time_str}"))
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text=BACK_BUTTON, callback_data="back:time")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _get_available_time_slots(data: dict, date: str) -> list[str]:
    specialist = data["specialist"]
    city = data.get("city", "").strip()
    candidate_times = get_available_times(date)

    available_slots: list[str] = []
    for time_str in candidate_times:
        if await is_slot_available(specialist, date, time_str, city):
            available_slots.append(time_str)

    return available_slots


@router.callback_query(lambda callback: callback.data.startswith("spec:"))
async def choose_specialist(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    profile = await get_client_profile(callback.from_user.id)
    if not profile:
        await callback.message.answer(ONBOARDING_REQUIRED_BEFORE_BOOKING)
        return

    spec_key = callback.data.split(":")[1]
    specialist = SPECIALIST_LABELS[spec_key]
    await state.update_data(
        specialist=specialist,
        phone_number=profile.get("phone_number", ""),
        pet_name=profile.get("pet_name", ""),
        pet_breed=profile.get("pet_breed", ""),
        pet_age=profile.get("pet_age", ""),
        pet_weight=profile.get("pet_weight", ""),
        issue_description=profile.get("issue_description", ""),
    )

    if spec_key == "kynologist":
        await callback.message.edit_text(
            PROMPT_SERVICE_FORMAT,
            reply_markup=kynologist_types(),
        )
        await state.set_state(ConsultationStates.choosing_kyno_type)
    else:
        await callback.message.edit_text(
            PROMPT_CONSULTATION_FORMAT,
            reply_markup=consultation_types(),
        )
        await state.set_state(ConsultationStates.choosing_cons_type)


@router.callback_query(
    lambda callback: callback.data.startswith("kyno:"),
    ConsultationStates.choosing_kyno_type,
)
async def kyno_type_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    choice = callback.data.split(":")[1]
    consultation_type = KYNOLOGIST_TYPE_LABELS[choice]
    await state.update_data(consultation_type=consultation_type)

    if choice == "venue":
        await callback.message.edit_text(PROMPT_CITY, reply_markup=venue_cities())
        await state.set_state(ConsultationStates.choosing_city)
    else:
        await callback.message.edit_text(PROMPT_DATE, reply_markup=date_picker())
        await state.set_state(ConsultationStates.choosing_date)


@router.callback_query(
    lambda callback: callback.data.startswith("cons:"),
    ConsultationStates.choosing_cons_type,
)
async def cons_type_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    choice = callback.data.split(":")[1]
    consultation_type = CONSULTATION_TYPE_LABELS[choice]
    await state.update_data(consultation_type=consultation_type)

    if choice in {"online", "call", "message"}:
        await callback.message.edit_text(PROMPT_DATE, reply_markup=date_picker())
        await state.set_state(ConsultationStates.choosing_date)
    else:
        await callback.message.edit_text(PROMPT_CITY, reply_markup=cities_for_offline())
        await state.set_state(ConsultationStates.choosing_city)


@router.callback_query(
    lambda callback: callback.data.startswith("city:"),
    ConsultationStates.choosing_city,
)
async def city_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    city_key = callback.data.split(":")[1]
    city = CITY_LABELS[city_key]
    await state.update_data(city=city)
    await callback.message.edit_text(PROMPT_DATE, reply_markup=date_picker())
    await state.set_state(ConsultationStates.choosing_date)


@router.callback_query(
    lambda callback: callback.data.startswith("date:"),
    ConsultationStates.choosing_date,
)
async def date_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    date = callback.data.split(":")[1]
    await state.update_data(date=date)

    data = await state.get_data()
    available_times = await _get_available_time_slots(data, date)
    if not available_times:
        message_text = (
            NO_TIMES_LEFT_FOR_TODAY
            if date == datetime.now(BUSINESS_TIMEZONE).strftime("%Y-%m-%d")
            else NO_FREE_TIMES_FOR_DATE.format(date=format_date_for_display(date))
        )
        await callback.message.edit_text(message_text, reply_markup=date_picker())
        await state.set_state(ConsultationStates.choosing_date)
        return

    await callback.message.edit_text(
        PROMPT_TIME_FOR_DATE.format(date=format_date_for_display(date)),
        reply_markup=time_picker(date, available_times),
    )
    await state.set_state(ConsultationStates.choosing_time)


@router.callback_query(
    lambda callback: callback.data.startswith("time:"),
    ConsultationStates.choosing_time,
)
async def time_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    time = callback.data.split(":")[1]
    await state.update_data(time=time)

    data = await state.get_data()
    await callback.message.edit_text(
        _format_summary(data),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=CONFIRM_BUTTON, callback_data="confirm")],
                [InlineKeyboardButton(text=CANCEL_BUTTON, callback_data="cancel")],
            ]
        ),
    )
    await state.set_state(ConsultationStates.confirming)


@router.callback_query(lambda callback: callback.data == "confirm", ConsultationStates.confirming)
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()
    data["user_id"] = callback.from_user.id
    data["username"] = callback.from_user.username

    city = data.get("city", "").strip()
    specialist = data["specialist"]
    date = data["date"]
    time = data["time"]

    try:
        available = await is_slot_available(specialist, date, time, city)
    except Exception:
        logger.exception("Не вдалося перевірити доступність слота.")
        await callback.message.edit_text(CHECK_SLOT_ERROR)
        await state.clear()
        return

    if not available:
        available_times = await _get_available_time_slots(data, date)
        if available_times:
            await callback.message.edit_text(
                SLOT_ALREADY_BOOKED_WITH_ALTERNATIVES.format(
                    date=format_date_for_display(date)
                ),
                reply_markup=time_picker(date, available_times),
            )
            await state.set_state(ConsultationStates.choosing_time)
            return

        await callback.message.edit_text(
            SLOT_ALREADY_BOOKED_PICK_ANOTHER_DATE.format(
                date=format_date_for_display(date)
            ),
            reply_markup=date_picker(),
        )
        await state.set_state(ConsultationStates.choosing_date)
        return

    try:
        record_id = await add_consultation(data)
    except Exception:
        logger.exception("Не вдалося зберегти новий запис.")
        await callback.message.edit_text(SAVE_BOOKING_ERROR)
        await state.clear()
        return

    await callback.message.edit_text(_format_booking_created_message(data))

    admin_text = (
        f"{ADMIN_NEW_RECORD_TITLE} #{record_id}!\n\n"
        f"Користувач: {format_username(data['username'])} (ID: {data['user_id']})\n"
        f"Телефон: {data['phone_number']}\n"
        f"Хвостик: {data['pet_name']}\n"
        f"Порода: {data['pet_breed']}\n"
        f"Вік: {data['pet_age']}\n"
        f"Вага: {data['pet_weight']}\n"
        f"Спеціаліст: {data['specialist']}\n"
        f"Тип: {data['consultation_type']}\n"
        f"Дата: {format_date_for_display(data['date'])} о {data['time']}\n"
        f"Запит: {data['issue_description']}\n"
    )
    if city:
        admin_text += f"Місто: {city}\n"

    try:
        for admin_id in ADMIN_USER_IDS:
            await callback.bot.send_message(admin_id, admin_text)
    except Exception:
        logger.exception("Не вдалося надіслати сповіщення адміністратору.")

    await state.clear()


@router.callback_query(lambda callback: callback.data == "cancel")
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    from .start import main_menu

    await callback.message.edit_text(BOOKING_CANCELED, reply_markup=main_menu())


@router.callback_query(lambda callback: callback.data.startswith("back:"))
async def go_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    back_target = callback.data.split(":")[1]

    if back_target == "main":
        from .start import main_menu

        await callback.message.edit_text(WELCOME_CHOOSE_SPECIALIST, reply_markup=main_menu())
        await state.clear()
    elif back_target == "kyno":
        await callback.message.edit_text(
            PROMPT_SERVICE_FORMAT,
            reply_markup=kynologist_types(),
        )
        await state.set_state(ConsultationStates.choosing_kyno_type)
    elif back_target == "spec":
        from .start import main_menu

        await callback.message.edit_text(WELCOME_CHOOSE_SPECIALIST, reply_markup=main_menu())
        await state.set_state(ConsultationStates.choosing_specialist)
    elif back_target == "cons_type":
        await callback.message.edit_text(
            PROMPT_CONSULTATION_FORMAT,
            reply_markup=consultation_types(),
        )
        await state.set_state(ConsultationStates.choosing_cons_type)
    elif back_target == "date":
        data = await state.get_data()
        specialist = data.get("specialist")

        if _needs_city_selection(data):
            keyboard = (
                venue_cities()
                if specialist == SPECIALIST_LABELS["kynologist"]
                else cities_for_offline()
            )
            await callback.message.edit_text(PROMPT_CITY, reply_markup=keyboard)
            await state.set_state(ConsultationStates.choosing_city)
        elif specialist == SPECIALIST_LABELS["kynologist"]:
            await callback.message.edit_text(
                PROMPT_SERVICE_FORMAT,
                reply_markup=kynologist_types(),
            )
            await state.set_state(ConsultationStates.choosing_kyno_type)
        else:
            await callback.message.edit_text(
                PROMPT_CONSULTATION_FORMAT,
                reply_markup=consultation_types(),
            )
            await state.set_state(ConsultationStates.choosing_cons_type)
    elif back_target == "time":
        await callback.message.edit_text(PROMPT_DATE, reply_markup=date_picker())
        await state.set_state(ConsultationStates.choosing_date)
    else:
        await state.clear()
        from .start import main_menu

        await callback.message.edit_text(WELCOME_CHOOSE_SPECIALIST, reply_markup=main_menu())

