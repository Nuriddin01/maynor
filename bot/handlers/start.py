from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards.main import main_menu_keyboard
from bot.texts.common import build_welcome_text

router = Router(name=__name__)


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    name = message.from_user.first_name if message.from_user else None
    await message.answer(
        build_welcome_text(name),
        reply_markup=main_menu_keyboard(),
    )
