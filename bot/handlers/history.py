from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MENU_HISTORY
from app.models import User
from app.services.sleep_service import SleepService
from bot.keyboards.main import main_menu_keyboard
from bot.texts.common import render_history

router = Router(name=__name__)


@router.message(Command("history"))
@router.message(lambda message: (message.text or "").strip() == MENU_HISTORY)
async def show_history(
    message: Message,
    session: AsyncSession,
    db_user: User,
    sleep_service: SleepService,
) -> None:
    entries = await sleep_service.get_recent_history(session, db_user.id, limit=10)
    await message.answer(render_history(entries), reply_markup=main_menu_keyboard())
