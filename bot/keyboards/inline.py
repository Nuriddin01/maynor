from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.constants import AUDIO_TYPES, LANGUAGE_CHOICES, PREMIUM_FEATURES


def alarm_setup_keyboard(default_minutes: int | None = None) -> InlineKeyboardMarkup:
    buttons = []
    if default_minutes:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"Поставить на {default_minutes} мин",
                    callback_data=f"alarm:quick:{default_minutes}",
                )
            ]
        )
    buttons.extend(
        [
            [InlineKeyboardButton(text="Поставить через минуты", callback_data="alarm:minutes")],
            [InlineKeyboardButton(text="Поставить на время", callback_data="alarm:clock")],
            [InlineKeyboardButton(text="Не сейчас", callback_data="alarm:cancel_flow")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Часовой пояс", callback_data="settings:timezone"),
                InlineKeyboardButton(text="Язык", callback_data="settings:language"),
            ],
            [
                InlineKeyboardButton(text="Аудио", callback_data="settings:audio"),
                InlineKeyboardButton(text="Формат времени", callback_data="settings:timeformat"),
            ],
            [InlineKeyboardButton(text="Reminders on/off", callback_data="settings:toggle:reminders")],
            [InlineKeyboardButton(text="Default nap 10", callback_data="settings:nap:set:10"), InlineKeyboardButton(text="Default nap 20", callback_data="settings:nap:set:20")],
            [InlineKeyboardButton(text="Обновить экран", callback_data="settings:refresh")],
        ]
    )


def audio_settings_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"settings:audio:set:{code}")]
        for code, label in AUDIO_TYPES.items()
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="White noise раздражает / не раздражает",
                callback_data="settings:audio:toggle_white_noise",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="Назад к настройкам", callback_data="settings:refresh")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def language_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"settings:language:set:{code}")]
        for code, label in LANGUAGE_CHOICES.items()
    ]
    rows.append([InlineKeyboardButton(text="Назад к настройкам", callback_data="settings:refresh")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def time_format_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="24h", callback_data="settings:timeformat:set:24h")],
            [InlineKeyboardButton(text="12h", callback_data="settings:timeformat:set:12h")],
            [InlineKeyboardButton(text="Назад к настройкам", callback_data="settings:refresh")],
        ]
    )


def premium_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=feature, callback_data=f"premium:feature:{code}")]
        for code, feature in PREMIUM_FEATURES.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
