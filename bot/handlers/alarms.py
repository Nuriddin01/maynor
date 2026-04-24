from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MENU_ALARM
from app.models import User
from app.services.alarm_service import AlarmService
from app.utils.time_utils import format_datetime_for_user
from app.utils.validators import parse_int_in_range, parse_minutes
from bot.handlers import is_back_request, is_menu_request, send_main_menu
from bot.keyboards.inline import alarm_setup_keyboard
from bot.keyboards.main import main_menu_keyboard, navigation_keyboard, shortcut_minutes_keyboard
from bot.states.alarm import AlarmFlow
from bot.texts import common as common_texts
from bot.texts import errors

router = Router(name=__name__)


async def prompt_alarm_menu(message: Message) -> None:
    await message.answer(
        "Как поставить будильник?",
        reply_markup=main_menu_keyboard(),
    )
    await message.answer(
        "Выберите способ установки будильника:",
        reply_markup=alarm_setup_keyboard(),
    )


@router.message(Command("alarm"))
@router.message(lambda message: (message.text or "").strip() == MENU_ALARM)
async def open_alarm_menu(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    alarm_service: AlarmService,
) -> None:
    await state.clear()
    active_alarm = await alarm_service.get_active_alarm_for_user(session, db_user.id)
    if active_alarm:
        await message.answer(
            "У вас уже есть активный будильник.\n\n"
            f"Когда сработает: {format_datetime_for_user(active_alarm.alarm_time, db_user.timezone, db_user.preferences.time_format)}\n"
            "Когда получите сообщение будильника, введите код в этот чат.",
            reply_markup=main_menu_keyboard(),
        )
        return
    await prompt_alarm_menu(message)


@router.callback_query(F.data == "alarm:minutes")
async def callback_alarm_minutes(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AlarmFlow.waiting_minutes)
    await callback.message.answer(
        "Через сколько минут поставить будильник?",
        reply_markup=shortcut_minutes_keyboard([10, 15, 20, 30, 45, 60]),
    )
    await callback.answer()


@router.callback_query(F.data == "alarm:clock")
async def callback_alarm_clock(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AlarmFlow.waiting_clock_time)
    await callback.message.answer(
        "На какое время поставить будильник? Введите HH:MM по вашему часовому поясу.",
        reply_markup=navigation_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("alarm:quick:"))
async def callback_alarm_quick(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    alarm_service: AlarmService,
    state: FSMContext,
) -> None:
    try:
        minutes = parse_int_in_range(callback.data.split(":")[-1], 1, 180)
        result = await alarm_service.create_alarm_in_minutes(session, db_user, minutes)
    except ValueError:
        await callback.answer(errors.ACTIVE_ALARM_TEXT, show_alert=True)
        return

    await state.clear()
    await callback.message.answer(
        common_texts.render_alarm_created(
            result.alarm_time,
            db_user.timezone,
            db_user.preferences.time_format,
            result.code,
        ),
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer("Будильник установлен")


@router.callback_query(F.data == "alarm:cancel_flow")
async def callback_alarm_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer(common_texts.MENU_READY_TEXT, reply_markup=main_menu_keyboard())
    await callback.answer()


@router.message(AlarmFlow.waiting_minutes)
async def handle_alarm_minutes(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    alarm_service: AlarmService,
) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    if is_back_request(text):
        await state.clear()
        return await prompt_alarm_menu(message)
    try:
        minutes = parse_minutes(text, max_value=1440)
        result = await alarm_service.create_alarm_in_minutes(session, db_user, minutes)
    except ValueError as exc:
        await message.answer(str(exc) if "активный" in str(exc) else errors.INVALID_MINUTES_TEXT)
        return
    await state.clear()
    await message.answer(
        common_texts.render_alarm_created(
            result.alarm_time,
            db_user.timezone,
            db_user.preferences.time_format,
            result.code,
        ),
        reply_markup=main_menu_keyboard(),
    )


@router.message(AlarmFlow.waiting_clock_time)
async def handle_alarm_clock_time(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    alarm_service: AlarmService,
) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    if is_back_request(text):
        await state.clear()
        return await prompt_alarm_menu(message)
    try:
        result = await alarm_service.create_alarm_at_clock(session, db_user, text)
    except ValueError as exc:
        if "активный" in str(exc):
            await message.answer(errors.ACTIVE_ALARM_TEXT)
        else:
            await message.answer(errors.INVALID_TIME_TEXT)
        return
    await state.clear()
    await message.answer(
        common_texts.render_alarm_created(
            result.alarm_time,
            db_user.timezone,
            db_user.preferences.time_format,
            result.code,
        ),
        reply_markup=main_menu_keyboard(),
    )




@router.message(Command("stop_alarm"))
async def stop_alarm_command(
    message: Message,
    session: AsyncSession,
    db_user: User,
    alarm_service: AlarmService,
) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Используйте формат: /stop_alarm CODE")
        return
    result = await alarm_service.confirm_alarm_stop(session, db_user.telegram_id, parts[1].strip())
    if result.stopped:
        await message.answer("Будильник остановлен.", reply_markup=main_menu_keyboard())
    else:
        await message.answer("Код не подошел или активный будильник не найден.", reply_markup=main_menu_keyboard())
@router.message(lambda message: (message.text or "").strip().isdigit() and len((message.text or "").strip()) in {4,5,6})
async def handle_alarm_stop_code(
    message: Message,
    session: AsyncSession,
    db_user: User,
    alarm_service: AlarmService,
) -> None:
    active_alarm = await alarm_service.get_active_alarm_for_user(session, db_user.id)
    if active_alarm is None:
        return

    result = await alarm_service.confirm_alarm_stop(session, db_user.telegram_id, (message.text or "").strip())
    if result.stopped:
        await message.answer("Будильник остановлен.", reply_markup=main_menu_keyboard())
        return
    await message.answer(errors.WRONG_ALARM_CODE_TEXT, reply_markup=main_menu_keyboard())
