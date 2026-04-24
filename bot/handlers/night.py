from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MENU_NIGHT, YES_BUTTON
from app.models import User
from app.schemas import RecommendationRequest, SessionRequestCreate
from app.services.recommendation_service import RecommendationService
from app.services.sleep_service import SleepService
from app.utils.validators import parse_minutes, parse_scale_1_5, parse_yes_no
from bot.handlers import is_back_request, is_menu_request, send_main_menu
from bot.keyboards.inline import alarm_setup_keyboard
from bot.keyboards.main import rating_keyboard, shortcut_minutes_keyboard, yes_no_keyboard
from bot.states.night import NightFlow
from bot.texts import errors
from bot.texts.night import INTRO_TEXT, render_night_recommendation

router = Router(name=__name__)


async def ask_slept_last_night(message: Message) -> None:
    await message.answer(
        f"{INTRO_TEXT}\n\nСколько минут вы спали прошлой ночью?",
        reply_markup=shortcut_minutes_keyboard([240, 300, 360, 420, 480, 540]),
    )


async def ask_sleep_quality(message: Message) -> None:
    await message.answer(
        "Как вы оцениваете качество прошлой ночи по шкале 1-5?",
        reply_markup=rating_keyboard(),
    )


async def ask_sleepiness(message: Message) -> None:
    await message.answer(
        "Насколько вы сейчас сонны по шкале 1-5?",
        reply_markup=rating_keyboard(),
    )


async def ask_stress(message: Message) -> None:
    await message.answer(
        "Насколько вы сейчас напряжены или тревожны по шкале 1-5?",
        reply_markup=rating_keyboard(),
    )


async def ask_free_time(message: Message) -> None:
    await message.answer(
        "Сколько минут у вас есть на подготовку ко сну?",
        reply_markup=shortcut_minutes_keyboard([5, 10, 15, 20, 25, 30]),
    )


async def ask_alarm_preference(message: Message) -> None:
    await message.answer(
        "Хотите сразу перейти к настройке будильника?",
        reply_markup=yes_no_keyboard(),
    )


@router.message(Command("night"))
@router.message(lambda message: (message.text or "").strip() == MENU_NIGHT)
async def start_night_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(NightFlow.slept_last_night)
    await ask_slept_last_night(message)


@router.message(NightFlow.slept_last_night)
async def handle_slept_last_night(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    try:
        value = parse_minutes(text)
    except ValueError:
        await message.answer(errors.INVALID_MINUTES_TEXT)
        return
    await state.update_data(slept_last_night_minutes=value)
    await state.set_state(NightFlow.sleep_quality)
    await ask_sleep_quality(message)


@router.message(NightFlow.sleep_quality)
async def handle_sleep_quality(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    if is_back_request(text):
        await state.set_state(NightFlow.slept_last_night)
        return await ask_slept_last_night(message)
    try:
        value = parse_scale_1_5(text)
    except ValueError:
        await message.answer(errors.INVALID_SCALE_TEXT)
        return
    await state.update_data(subjective_sleep_quality=value)
    await state.set_state(NightFlow.current_sleepiness)
    await ask_sleepiness(message)


@router.message(NightFlow.current_sleepiness)
async def handle_sleepiness(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    if is_back_request(text):
        await state.set_state(NightFlow.sleep_quality)
        return await ask_sleep_quality(message)
    try:
        value = parse_scale_1_5(text)
    except ValueError:
        await message.answer(errors.INVALID_SCALE_TEXT)
        return
    await state.update_data(current_sleepiness=value)
    await state.set_state(NightFlow.current_stress)
    await ask_stress(message)


@router.message(NightFlow.current_stress)
async def handle_stress(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    if is_back_request(text):
        await state.set_state(NightFlow.current_sleepiness)
        return await ask_sleepiness(message)
    try:
        value = parse_scale_1_5(text)
    except ValueError:
        await message.answer(errors.INVALID_SCALE_TEXT)
        return
    await state.update_data(current_stress=value)
    await state.set_state(NightFlow.free_time)
    await ask_free_time(message)


@router.message(NightFlow.free_time)
async def handle_free_time(
    message: Message,
    state: FSMContext,
) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    if is_back_request(text):
        await state.set_state(NightFlow.current_stress)
        return await ask_stress(message)
    try:
        value = parse_minutes(text, max_value=180)
    except ValueError:
        await message.answer(errors.INVALID_MINUTES_TEXT)
        return
    await state.update_data(free_time_minutes=value)
    await state.set_state(NightFlow.wants_alarm)
    await ask_alarm_preference(message)


@router.message(NightFlow.wants_alarm)
async def handle_alarm_preference(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    recommendation_service: RecommendationService,
    sleep_service: SleepService,
) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    if is_back_request(text):
        await state.set_state(NightFlow.free_time)
        return await ask_free_time(message)

    try:
        wants_alarm = parse_yes_no(text)
    except ValueError:
        await message.answer("Выберите «Да» или «Нет».")
        return

    data = await state.get_data()
    payload = RecommendationRequest(
        request_type="night",
        slept_last_night_minutes=data["slept_last_night_minutes"],
        subjective_sleep_quality=data["subjective_sleep_quality"],
        current_sleepiness=data["current_sleepiness"],
        current_stress=data["current_stress"],
        free_time_minutes=data["free_time_minutes"],
    )
    recommendation = await recommendation_service.build_for_user(session, db_user, payload)

    await sleep_service.create_session_request(
        session,
        db_user,
        SessionRequestCreate(
            requested_mode=recommendation.recommended_mode,
            free_time_minutes=data["free_time_minutes"],
            slept_last_night_minutes=data["slept_last_night_minutes"],
            current_sleepiness_1_5=data["current_sleepiness"],
            current_stress_1_5=data["current_stress"],
            wants_alarm=wants_alarm,
            recommendation_snapshot_json=recommendation.model_dump(mode="json"),
        ),
    )

    await message.answer(render_night_recommendation(recommendation))
    if wants_alarm is True:
        await message.answer(
            "Могу сразу открыть настройку будильника. Для ночного режима удобнее выбрать конкретное время.",
            reply_markup=alarm_setup_keyboard(),
        )
    await send_main_menu(message, state)
