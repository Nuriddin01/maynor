from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.constants import (
    BACK_BUTTON,
    MENU_ALARM,
    MENU_BUTTON,
    MENU_DAY,
    MENU_HELP,
    MENU_HISTORY,
    MENU_NIGHT,
    MENU_POWER_NAP,
    MENU_PREMIUM,
    MENU_SETTINGS,
    MENU_STATS,
    MENU_WAKE,
    NO_BUTTON,
    SKIP_BUTTON,
    YES_BUTTON,
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=MENU_NIGHT), KeyboardButton(text=MENU_DAY)],
        [KeyboardButton(text=MENU_POWER_NAP), KeyboardButton(text=MENU_WAKE)],
        [KeyboardButton(text=MENU_HISTORY), KeyboardButton(text=MENU_STATS)],
        [KeyboardButton(text=MENU_ALARM), KeyboardButton(text=MENU_SETTINGS)],
        [KeyboardButton(text=MENU_PREMIUM), KeyboardButton(text=MENU_HELP)],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def navigation_keyboard(include_skip: bool = False) -> ReplyKeyboardMarkup:
    row = [KeyboardButton(text=BACK_BUTTON), KeyboardButton(text=MENU_BUTTON)]
    keyboard = [row]
    if include_skip:
        keyboard.insert(0, [KeyboardButton(text=SKIP_BUTTON)])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def rating_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=str(value)) for value in range(1, 6)],
        [KeyboardButton(text=BACK_BUTTON), KeyboardButton(text=MENU_BUTTON)],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def yes_no_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=YES_BUTTON), KeyboardButton(text=NO_BUTTON)],
        [KeyboardButton(text=BACK_BUTTON), KeyboardButton(text=MENU_BUTTON)],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def simple_choices_keyboard(*choices: str, include_back: bool = True) -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text=choice)] for choice in choices]
    if include_back:
        keyboard.append([KeyboardButton(text=BACK_BUTTON), KeyboardButton(text=MENU_BUTTON)])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def shortcut_minutes_keyboard(values: list[int]) -> ReplyKeyboardMarkup:
    first_row = [KeyboardButton(text=str(value)) for value in values[:3]]
    second_row = [KeyboardButton(text=str(value)) for value in values[3:6]]
    keyboard = [row for row in [first_row, second_row] if row]
    keyboard.append([KeyboardButton(text=BACK_BUTTON), KeyboardButton(text=MENU_BUTTON)])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
