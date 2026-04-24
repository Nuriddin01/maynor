from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MENU_WAKE, SKIP_BUTTON
from app.models import User
from app.schemas import SleepEntryCreate
from app.services.sleep_service import SleepService
from app.utils.validators import parse_minutes, parse_scale_1_5
from bot.handlers import is_back_request, is_menu_request, send_main_menu
from bot.keyboards.main import navigation_keyboard, rating_keyboard, shortcut_minutes_keyboard
from bot.states.wake import WakeCheckinFlow
from bot.texts import errors
from bot.texts.wake import INTRO_TEXT, SAVED_TEXT

router = Router(name=__name__)


async def ask_duration(message: Message) -> None:
    await message.answer(
        f"{INTRO_TEXT}\n\nСколько минут вы в итоге спали?",
        reply_markup=shortcut_minutes_keyboard([10, 15, 20, 30, 45, 60]),
    )


async def ask_quality(message: Message) -> None:
    await message.answer(
        "Как вы оцениваете качество сна по шкале 1-5?",
        reply_markup=rating_keyboard(),
    )


async def ask_felt_after(message: Message) -> None:
    await message.answer(
        "Как вы чувствуете себя после пробуждения по шкале 1-5?",
        reply_markup=rating_keyboard(),
    )


async def ask_helpfulness(message: Message) -> None:
    await message.answer(
        "Насколько помогла рекомендация по шкале 1-5?",
        reply_markup=rating_keyboard(),
    )


async def ask_notes(message: Message) -> None:
    await message.answer(
        "Есть ли заметки? Можно написать свободным текстом или нажать «Пропустить».",
        reply_markup=navigation_keyboard(include_skip=True),
    )


@router.message(Command("wake"))
@router.message(lambda message: (message.text or "").strip() == MENU_WAKE)
async def start_wake_checkin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(WakeCheckinFlow.duration_minutes)
    await ask_duration(message)


@router.message(WakeCheckinFlow.duration_minutes)
async def handle_duration(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    try:
        value = parse_minutes(text)
    except ValueError:
        await message.answer(errors.INVALID_MINUTES_TEXT)
        return
    await state.update_data(duration_minutes=value)
    await state.set_state(WakeCheckinFlow.quality)
    await ask_quality(message)


@router.message(WakeCheckinFlow.quality)
async def handle_quality(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    if is_back_request(text):
        await state.set_state(WakeCheckinFlow.duration_minutes)
        return await ask_duration(message)
    try:
        value = parse_scale_1_5(text)
    except ValueError:
        await message.answer(errors.INVALID_SCALE_TEXT)
        return
    await state.update_data(quality=value)
    await state.set_state(WakeCheckinFlow.felt_after)
    await ask_felt_after(message)


@router.message(WakeCheckinFlow.felt_after)
async def handle_felt_after(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    if is_back_request(text):
        await state.set_state(WakeCheckinFlow.quality)
        return await ask_quality(message)
    try:
        value = parse_scale_1_5(text)
    except ValueError:
        await message.answer(errors.INVALID_SCALE_TEXT)
        return
    await state.update_data(felt_after=value)
    await state.set_state(WakeCheckinFlow.helpfulness)
    await ask_helpfulness(message)


@router.message(WakeCheckinFlow.helpfulness)
async def handle_helpfulness(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    if is_back_request(text):
        await state.set_state(WakeCheckinFlow.felt_after)
        return await ask_felt_after(message)
    try:
        value = parse_scale_1_5(text)
    except ValueError:
        await message.answer(errors.INVALID_SCALE_TEXT)
        return
    await state.update_data(helpfulness=value)
    await state.set_state(WakeCheckinFlow.notes)
    await ask_notes(message)


@router.message(WakeCheckinFlow.notes)
async def handle_notes(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    sleep_service: SleepService,
) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    if is_back_request(text):
        await state.set_state(WakeCheckinFlow.helpfulness)
        return await ask_helpfulness(message)

    data = await state.get_data()
    notes = None if text.strip() == SKIP_BUTTON else text.strip()
    await sleep_service.create_sleep_entry_from_latest_session(
        session,
        db_user,
        SleepEntryCreate(
            mode="manual_checkin",
            duration_minutes=data["duration_minutes"],
            subjective_sleep_quality_1_5=data["quality"],
            felt_after_waking_1_5=data["felt_after"],
            helpfulness_1_5=data["helpfulness"],
            notes=notes,
        ),
    )

    await message.answer(SAVED_TEXT)
    await send_main_menu(message, state)
