from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MENU_STATS
from app.models import User
from app.services.stats_service import StatsService
from bot.keyboards.main import main_menu_keyboard
from bot.texts.common import render_stats

router = Router(name=__name__)


@router.message(Command("stats"))
@router.message(lambda message: (message.text or "").strip() == MENU_STATS)
async def show_stats(
    message: Message,
    session: AsyncSession,
    db_user: User,
    stats_service: StatsService,
) -> None:
    summary = await stats_service.build_summary(session, db_user.id)
    await message.answer(render_stats(summary), reply_markup=main_menu_keyboard())
