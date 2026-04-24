from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MENU_DAY
from app.models import User
from app.schemas import RecommendationRequest, SessionRequestCreate
from app.services.alarm_service import AlarmService
from app.services.recommendation_service import RecommendationService
from app.services.sleep_service import SleepService
from app.utils.validators import parse_minutes, parse_scale_1_5, parse_yes_no
from bot.handlers import is_back_request, is_menu_request, send_main_menu
from bot.keyboards.main import rating_keyboard, shortcut_minutes_keyboard, simple_choices_keyboard, yes_no_keyboard
from bot.states.day import DayFlow
from bot.texts import common as common_texts
from bot.texts import errors
from bot.texts.day import INTRO_TEXT, render_day_recommendation

router = Router(name=__name__)
RECOVERY_LABEL = "Просто восстановиться"
SLEEP_LABEL = "Попробовать поспать"


@router.message(Command("day"))
@router.message(lambda message: (message.text or "").strip() == MENU_DAY)
async def start_day_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(DayFlow.slept_last_night)
    await message.answer(f"{INTRO_TEXT}\n\nСколько минут вы спали прошлой ночью?", reply_markup=shortcut_minutes_keyboard([240, 300, 360, 420, 480, 540]))


@router.message(DayFlow.slept_last_night)
async def slept(message: Message, state: FSMContext) -> None:
    if is_menu_request(message.text):
        return await send_main_menu(message, state)
    try:
        value = parse_minutes(message.text or "")
    except ValueError:
        return await message.answer(errors.INVALID_MINUTES_TEXT)
    await state.update_data(slept_last_night_minutes=value)
    await state.set_state(DayFlow.current_energy)
    await message.answer("Текущая энергия 1-5?", reply_markup=rating_keyboard())


@router.message(DayFlow.current_energy)
async def energy(message: Message, state: FSMContext) -> None:
    try:
        value = parse_scale_1_5(message.text or "")
    except ValueError:
        return await message.answer(errors.INVALID_SCALE_TEXT)
    await state.update_data(current_energy=value)
    await state.set_state(DayFlow.current_sleepiness)
    await message.answer("Текущая сонливость 1-5?", reply_markup=rating_keyboard())


@router.message(DayFlow.current_sleepiness)
async def sleepiness(message: Message, state: FSMContext) -> None:
    try:
        value = parse_scale_1_5(message.text or "")
    except ValueError:
        return await message.answer(errors.INVALID_SCALE_TEXT)
    await state.update_data(current_sleepiness=value)
    await state.set_state(DayFlow.current_stress)
    await message.answer("Уровень напряжения 1-5?", reply_markup=rating_keyboard())


@router.message(DayFlow.current_stress)
async def stress(message: Message, state: FSMContext) -> None:
    try:
        value = parse_scale_1_5(message.text or "")
    except ValueError:
        return await message.answer(errors.INVALID_SCALE_TEXT)
    await state.update_data(current_stress=value)
    await state.set_state(DayFlow.free_time)
    await message.answer("Сколько минут есть?", reply_markup=shortcut_minutes_keyboard([5, 10, 15, 20, 30, 45]))


@router.message(DayFlow.free_time)
async def free_time(message: Message, state: FSMContext) -> None:
    try:
        value = parse_minutes(message.text or "", max_value=180)
    except ValueError:
        return await message.answer(errors.INVALID_MINUTES_TEXT)
    await state.update_data(free_time_minutes=value)
    await state.set_state(DayFlow.intention)
    await message.answer("Что хотите?", reply_markup=simple_choices_keyboard(RECOVERY_LABEL, SLEEP_LABEL))


@router.message(DayFlow.intention)
async def intention(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text not in {RECOVERY_LABEL, SLEEP_LABEL}:
        return await message.answer("Выберите кнопку.")
    await state.update_data(mode_preference="sleep" if text == SLEEP_LABEL else "recovery")
    await state.set_state(DayFlow.wants_alarm)
    await message.answer("Нужен будильник?", reply_markup=yes_no_keyboard())


@router.message(DayFlow.wants_alarm)
async def done(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    recommendation_service: RecommendationService,
    sleep_service: SleepService,
    alarm_service: AlarmService,
) -> None:
    try:
        wants_alarm = parse_yes_no(message.text or "")
    except ValueError:
        return await message.answer("Выберите Да/Нет")
    data = await state.get_data()
    payload = RecommendationRequest(
        request_type="day",
        slept_last_night_minutes=data["slept_last_night_minutes"],
        current_energy=data["current_energy"],
        current_sleepiness=data["current_sleepiness"],
        current_stress=data["current_stress"],
        free_time_minutes=data["free_time_minutes"],
        mode_preference=data["mode_preference"],
    )
    recommendation = await recommendation_service.build_for_user(session, db_user, payload)
    await sleep_service.create_session_request(session, db_user, SessionRequestCreate(
        requested_mode=recommendation.recommended_mode,
        free_time_minutes=data["free_time_minutes"],
        slept_last_night_minutes=data["slept_last_night_minutes"],
        current_energy_1_5=data["current_energy"],
        current_sleepiness_1_5=data["current_sleepiness"],
        current_stress_1_5=data["current_stress"],
        wants_alarm=wants_alarm,
        recommendation_snapshot_json=recommendation.model_dump(mode="json"),
    ))
    await message.answer(render_day_recommendation(recommendation))
    if wants_alarm and recommendation.recommended_duration_minutes:
        try:
            created = await alarm_service.create_alarm_in_minutes(session, db_user, recommendation.recommended_duration_minutes)
            await message.answer(common_texts.render_alarm_created(created.alarm_time, db_user.timezone, db_user.preferences.time_format, created.code))
        except ValueError:
            await message.answer(errors.ACTIVE_ALARM_TEXT)
    await send_main_menu(message, state)
