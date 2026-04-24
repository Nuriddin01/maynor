from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.constants import MENU_HELP
from bot.keyboards.main import main_menu_keyboard
from bot.texts.common import HELP_TEXT

router = Router(name=__name__)


@router.message(Command("help"))
@router.message(lambda message: (message.text or "").strip() == MENU_HELP)
async def handle_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu_keyboard())
