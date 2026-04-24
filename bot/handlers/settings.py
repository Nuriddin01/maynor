from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MENU_SETTINGS
from app.models import User
from app.services.user_service import UserService
from app.utils.validators import validate_timezone_name
from bot.handlers import is_back_request, is_menu_request, send_main_menu
from bot.keyboards.inline import (
    audio_settings_keyboard,
    language_keyboard,
    settings_keyboard,
    time_format_keyboard,
)
from bot.keyboards.main import main_menu_keyboard, navigation_keyboard
from bot.states.settings import SettingsFlow
from bot.texts import common as common_texts
from bot.texts import errors

router = Router(name=__name__)


async def show_settings_screen(
    target,
    session: AsyncSession,
    db_user: User,
    user_service: UserService,
) -> None:
    overview = await user_service.settings_overview(session, db_user)
    text = common_texts.render_settings(overview)
    if hasattr(target, "edit_text"):
        await target.edit_text(text, reply_markup=settings_keyboard())
    else:
        await target.answer(text, reply_markup=settings_keyboard())


@router.message(Command("settings"))
@router.message(lambda message: (message.text or "").strip() == MENU_SETTINGS)
async def open_settings(
    message: Message,
    session: AsyncSession,
    db_user: User,
    user_service: UserService,
    state: FSMContext,
) -> None:
    await state.clear()
    overview = await user_service.settings_overview(session, db_user)
    await message.answer(
        common_texts.render_settings(overview),
        reply_markup=settings_keyboard(),
    )


@router.callback_query(F.data == "settings:refresh")
async def refresh_settings(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    user_service: UserService,
) -> None:
    await show_settings_screen(callback.message, session, db_user, user_service)
    await callback.answer()


@router.callback_query(F.data == "settings:timezone")
async def choose_timezone(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFlow.waiting_timezone)
    await callback.message.answer(
        "Введите часовой пояс, например Europe/Moscow.",
        reply_markup=navigation_keyboard(),
    )
    await callback.answer()


@router.message(SettingsFlow.waiting_timezone)
async def handle_timezone_value(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    user_service: UserService,
) -> None:
    text = message.text or ""
    if is_menu_request(text):
        return await send_main_menu(message, state)
    if is_back_request(text):
        await state.clear()
        overview = await user_service.settings_overview(session, db_user)
        return await message.answer(common_texts.render_settings(overview), reply_markup=settings_keyboard())
    try:
        timezone_name = validate_timezone_name(text)
    except ValueError:
        await message.answer(errors.INVALID_TIMEZONE_TEXT)
        return

    await user_service.update_timezone(session, db_user, timezone_name)
    await state.clear()
    overview = await user_service.settings_overview(session, db_user)
    await message.answer(
        f"Часовой пояс обновлен на {timezone_name}.\n\n{common_texts.render_settings(overview)}",
        reply_markup=settings_keyboard(),
    )


@router.callback_query(F.data == "settings:language")
async def choose_language(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Выберите язык профиля. Интерфейс MVP в основном русскоязычный, но выбор сохраняется.",
        reply_markup=language_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("settings:language:set:"))
async def set_language(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    user_service: UserService,
) -> None:
    language = callback.data.split(":")[-1]
    await user_service.update_language(session, db_user, language)
    await show_settings_screen(callback.message, session, db_user, user_service)
    await callback.answer("Язык профиля обновлен")


@router.callback_query(F.data == "settings:audio")
async def choose_audio(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Выберите предпочтительное аудио и при необходимости отметьте, что white noise вам не подходит.",
        reply_markup=audio_settings_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("settings:audio:set:"))
async def set_audio(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    user_service: UserService,
) -> None:
    audio = callback.data.split(":")[-1]
    await user_service.update_audio_preferences(
        session,
        db_user,
        preferred_audio=audio,
        likes_rain=audio == "rain",
        likes_forest=audio == "forest",
        likes_silence=audio == "silence",
    )
    await show_settings_screen(callback.message, session, db_user, user_service)
    await callback.answer("Аудио-предпочтение сохранено")


@router.callback_query(F.data == "settings:audio:toggle_white_noise")
async def toggle_white_noise(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    user_service: UserService,
) -> None:
    current_value = db_user.preferences.dislikes_white_noise
    await user_service.update_audio_preferences(
        session,
        db_user,
        dislikes_white_noise=not current_value,
    )
    await show_settings_screen(callback.message, session, db_user, user_service)
    await callback.answer("Настройка white noise обновлена")


@router.callback_query(F.data == "settings:timeformat")
async def choose_time_format(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Выберите формат времени.",
        reply_markup=time_format_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("settings:timeformat:set:"))
async def set_time_format(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    user_service: UserService,
) -> None:
    value = callback.data.split(":")[-1]
    await user_service.update_toggle_preferences(session, db_user, time_format=value)
    await show_settings_screen(callback.message, session, db_user, user_service)
    await callback.answer("Формат времени обновлен")




@router.callback_query(F.data == "settings:toggle:reminders")
async def toggle_reminders(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    user_service: UserService,
) -> None:
    await user_service.update_audio_preferences(
        session,
        db_user,
        reminders_enabled=not db_user.preferences.reminders_enabled,
    )
    await show_settings_screen(callback.message, session, db_user, user_service)
    await callback.answer("Reminders обновлены")


@router.callback_query(F.data.startswith("settings:nap:set:"))
async def set_default_nap(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    user_service: UserService,
) -> None:
    minutes = int(callback.data.split(":")[-1])
    await user_service.update_audio_preferences(session, db_user, default_nap_minutes=minutes)
    await show_settings_screen(callback.message, session, db_user, user_service)
    await callback.answer("Default nap сохранен")
