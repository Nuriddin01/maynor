from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MENU_POWER_NAP
from app.models import User
from app.schemas import RecommendationRequest, SessionRequestCreate
from app.services.alarm_service import AlarmService
from app.services.recommendation_service import RecommendationService
from app.services.sleep_service import SleepService
from app.utils.validators import parse_minutes, parse_scale_1_5, parse_yes_no
from bot.handlers import is_back_request, is_menu_request, send_main_menu
from bot.keyboards.main import rating_keyboard, shortcut_minutes_keyboard, yes_no_keyboard
from bot.states.power_nap import PowerNapFlow
from bot.texts import common as common_texts
from bot.texts import errors
from bot.texts.power_nap import INTRO_TEXT, render_power_nap_recommendation

router = Router(name=__name__)


async def ask_slept_last_night(message: Message) -> None:
    await message.answer(
        f"{INTRO_TEXT}\n\nСколько минут вы спали прошлой ночью?",
        reply_markup=shortcut_minutes_keyboard([240, 300, 360, 420, 480, 540]),
    )


async def ask_sleepiness(message: Message) -> None:
    await message.answer(
        "Насколько вы сейчас сонны по шкале 1-5?",
        reply_markup=rating_keyboard(),
    )


async def ask_free_time(message: Message) -> None:
    await message.answer(
        "Сколько минут у вас есть сейчас?",
        reply_markup=shortcut_minutes_keyboard([5, 10, 15, 20, 25, 30]),
    )


async def ask_alarm_preference(message: Message) -> None:
    await message.answer(
        "Если сценарий подойдет, поставить будильник сразу?",
        reply_markup=yes_no_keyboard(),
    )


@router.message(Command("power_nap"))
@router.message(lambda message: (message.text or "").strip() == MENU_POWER_NAP)
async def start_power_nap_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(PowerNapFlow.slept_last_night)
    await ask_slept_last_night(message)


@router.message(PowerNapFlow.slept_last_night)
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
    await state.set_state(PowerNapFlow.current_sleepiness)
    await ask_sleepiness(message)


@router.message(PowerNapFlow.current_sleepiness)
async def handle_sleepiness(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    if is_back_request(text):
        await state.set_state(PowerNapFlow.slept_last_night)
        return await ask_slept_last_night(message)
    try:
        value = parse_scale_1_5(text)
    except ValueError:
        await message.answer(errors.INVALID_SCALE_TEXT)
        return
    await state.update_data(current_sleepiness=value)
    await state.set_state(PowerNapFlow.free_time)
    await ask_free_time(message)


@router.message(PowerNapFlow.free_time)
async def handle_free_time(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    if is_back_request(text):
        await state.set_state(PowerNapFlow.current_sleepiness)
        return await ask_sleepiness(message)
    try:
        value = parse_minutes(text, max_value=120)
    except ValueError:
        await message.answer(errors.INVALID_MINUTES_TEXT)
        return
    await state.update_data(free_time_minutes=value)
    await state.set_state(PowerNapFlow.wants_alarm)
    await ask_alarm_preference(message)


@router.message(PowerNapFlow.wants_alarm)
async def handle_alarm_preference(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    recommendation_service: RecommendationService,
    sleep_service: SleepService,
    alarm_service: AlarmService,
) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    if is_back_request(text):
        await state.set_state(PowerNapFlow.free_time)
        return await ask_free_time(message)
    try:
        wants_alarm = parse_yes_no(text)
    except ValueError:
        await message.answer("Выберите «Да» или «Нет».")
        return

    data = await state.get_data()
    payload = RecommendationRequest(
        request_type="power_nap",
        slept_last_night_minutes=data["slept_last_night_minutes"],
        current_sleepiness=data["current_sleepiness"],
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
            wants_alarm=wants_alarm,
            recommendation_snapshot_json=recommendation.model_dump(mode="json"),
        ),
    )

    await message.answer(render_power_nap_recommendation(recommendation))
    if wants_alarm and recommendation.suggest_alarm and recommendation.recommended_duration_minutes:
        try:
            result = await alarm_service.create_alarm_in_minutes(
                session,
                db_user,
                recommendation.recommended_duration_minutes,
            )
            await message.answer(
                common_texts.render_alarm_created(
                    result.alarm_time,
                    db_user.timezone,
                    db_user.preferences.time_format,
                    result.code,
                )
            )
        except ValueError:
            await message.answer(errors.ACTIVE_ALARM_TEXT)

    await send_main_menu(message, state)
