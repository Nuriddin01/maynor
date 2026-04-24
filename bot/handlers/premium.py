from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.constants import MENU_PREMIUM, PREMIUM_FEATURES
from app.models import User
from bot.keyboards.inline import premium_keyboard
from bot.keyboards.main import main_menu_keyboard
from bot.texts.premium import render_premium_overview, render_premium_stub

router = Router(name=__name__)


@router.message(Command("premium"))
@router.message(lambda message: (message.text or "").strip() == MENU_PREMIUM)
async def show_premium(message: Message, db_user: User) -> None:
    await message.answer(
        render_premium_overview(db_user.premium_status),
        reply_markup=premium_keyboard(),
    )


@router.callback_query(F.data.startswith("premium:feature:"))
async def handle_premium_feature(callback: CallbackQuery, db_user: User) -> None:
    feature_code = callback.data.split(":")[-1]
    feature_name = PREMIUM_FEATURES[feature_code]
    await callback.message.answer(
        render_premium_stub(feature_name, db_user.premium_status),
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
