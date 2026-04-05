import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from database import get_client_profile, upsert_client_profile
from texts import (
    PROFILE_ALREADY_SAVED,
    PROFILE_ASK_AGE,
    PROFILE_ASK_BREED,
    PROFILE_ASK_ISSUE,
    PROFILE_ASK_PET_NAME,
    PROFILE_ASK_WEIGHT,
    PROFILE_SAVE_ERROR,
    PROFILE_SAVE_SUCCESS,
    SPECIALIST_LABELS,
    START_CONTACT_BUTTON,
    START_CONTACT_REQUIRED,
    START_CONTACT_WRONG,
    START_GREETING,
)


router = Router()
logger = logging.getLogger(__name__)


class OnboardingStates(StatesGroup):
    waiting_contact = State()
    waiting_pet_name = State()
    waiting_pet_breed = State()
    waiting_pet_age = State()
    waiting_pet_weight = State()
    waiting_issue_description = State()


def _extract_text(message: Message) -> str | None:
    if not message.text:
        return None
    text = message.text.strip()
    return text or None


def contact_request_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=START_CONTACT_BUTTON, request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=SPECIALIST_LABELS["veterinarian"], callback_data="spec:veterinarian")],
            [InlineKeyboardButton(text=SPECIALIST_LABELS["kynologist"], callback_data="spec:kynologist")],
            [InlineKeyboardButton(text=SPECIALIST_LABELS["rehab"], callback_data="spec:rehab")],
            [
                InlineKeyboardButton(
                    text=SPECIALIST_LABELS["behavior"],
                    callback_data="spec:behavior",
                )
            ],
        ]
    )


async def _show_main_menu(message: Message, text: str = START_GREETING):
    await message.answer(text, reply_markup=main_menu())


async def _start_onboarding(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(OnboardingStates.waiting_contact)
    await message.answer(
        START_CONTACT_REQUIRED,
        reply_markup=contact_request_keyboard(),
    )


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    profile = await get_client_profile(message.from_user.id)
    if profile and profile.get("phone_number"):
        await state.clear()
        await _show_main_menu(message, PROFILE_ALREADY_SAVED)
        return

    await _start_onboarding(message, state)


@router.message(OnboardingStates.waiting_contact, F.contact)
async def save_contact(message: Message, state: FSMContext):
    contact = message.contact
    if not contact or contact.user_id != message.from_user.id:
        await message.answer(
            START_CONTACT_WRONG,
            reply_markup=contact_request_keyboard(),
        )
        return

    await state.update_data(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or "",
        last_name=message.from_user.last_name or "",
        phone_number=contact.phone_number,
    )
    await state.set_state(OnboardingStates.waiting_pet_name)
    await message.answer(PROFILE_ASK_PET_NAME, reply_markup=ReplyKeyboardRemove())


@router.message(OnboardingStates.waiting_contact)
async def contact_required(message: Message):
    await message.answer(
        START_CONTACT_WRONG,
        reply_markup=contact_request_keyboard(),
    )


@router.message(OnboardingStates.waiting_pet_name)
async def save_pet_name(message: Message, state: FSMContext):
    pet_name = _extract_text(message)
    if not pet_name:
        await message.answer(PROFILE_ASK_PET_NAME)
        return

    await state.update_data(pet_name=pet_name)
    await state.set_state(OnboardingStates.waiting_pet_breed)
    await message.answer(PROFILE_ASK_BREED)


@router.message(OnboardingStates.waiting_pet_breed)
async def save_pet_breed(message: Message, state: FSMContext):
    pet_breed = _extract_text(message)
    if not pet_breed:
        await message.answer(PROFILE_ASK_BREED)
        return

    await state.update_data(pet_breed=pet_breed)
    await state.set_state(OnboardingStates.waiting_pet_age)
    await message.answer(PROFILE_ASK_AGE)


@router.message(OnboardingStates.waiting_pet_age)
async def save_pet_age(message: Message, state: FSMContext):
    pet_age = _extract_text(message)
    if not pet_age:
        await message.answer(PROFILE_ASK_AGE)
        return

    await state.update_data(pet_age=pet_age)
    await state.set_state(OnboardingStates.waiting_pet_weight)
    await message.answer(PROFILE_ASK_WEIGHT)


@router.message(OnboardingStates.waiting_pet_weight)
async def save_pet_weight(message: Message, state: FSMContext):
    pet_weight = _extract_text(message)
    if not pet_weight:
        await message.answer(PROFILE_ASK_WEIGHT)
        return

    await state.update_data(pet_weight=pet_weight)
    await state.set_state(OnboardingStates.waiting_issue_description)
    await message.answer(PROFILE_ASK_ISSUE)


@router.message(OnboardingStates.waiting_issue_description)
async def save_issue_description(message: Message, state: FSMContext):
    issue_description = _extract_text(message)
    if not issue_description:
        await message.answer(PROFILE_ASK_ISSUE)
        return

    await state.update_data(issue_description=issue_description)
    profile_data = await state.get_data()

    try:
        await upsert_client_profile(profile_data)
    except Exception:
        logger.exception("Не вдалося зберегти профіль клієнта.")
        await message.answer(PROFILE_SAVE_ERROR, reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return

    await state.clear()
    await message.answer(PROFILE_SAVE_SUCCESS, reply_markup=ReplyKeyboardRemove())
    await _show_main_menu(message)


@router.message()
async def fallback(message: Message, state: FSMContext):
    profile = await get_client_profile(message.from_user.id)
    if profile and profile.get("phone_number"):
        await state.clear()
        await _show_main_menu(message)
        return

    await _start_onboarding(message, state)
