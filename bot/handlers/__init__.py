from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.constants import BACK_BUTTON, CANCEL_BUTTON, MENU_BUTTON
from bot.keyboards.main import main_menu_keyboard
from bot.texts import common as common_texts


def is_back_request(text: str | None) -> bool:
    return (text or "").strip() == BACK_BUTTON


def is_menu_request(text: str | None) -> bool:
    normalized = (text or "").strip()
    return normalized in {MENU_BUTTON, CANCEL_BUTTON, "/start"}


async def send_main_menu(message: Message, state: FSMContext, text: str | None = None) -> None:
    await state.clear()
    await message.answer(
        text or common_texts.MENU_READY_TEXT,
        reply_markup=main_menu_keyboard(),
    )
