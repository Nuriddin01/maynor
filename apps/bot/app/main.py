from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from apps.bot.app.local_bot import LocalBotSession
from apps.bot.app.texts import CONSENT_TEXT, MAIN_MENU, recommendation_text
from packages.core.config import get_settings
from packages.core.logging import configure_logging
from packages.billing.plans import PLANS
from packages.domain.models import AnalyticsEventName, AudioType
from packages.services.facade import services

logger = logging.getLogger(__name__)


async def run_local_bot() -> None:
    session = LocalBotSession(telegram_id=1, username="local")
    logger.info(session.start())
    logger.info(session.calculate_bedtime())
    logger.info(session.meditation())
    logger.info(session.quick_sleep())
    logger.info(session.good_wake())


async def run_aiogram_bot() -> None:
    try:
        from aiogram import Bot, Dispatcher, F, Router
        from aiogram.filters import CommandStart
        from aiogram.fsm.context import FSMContext
        from aiogram.fsm.state import State, StatesGroup
        from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
    except ImportError as exc:
        raise RuntimeError("aiogram is not installed. Install project dependencies or use BOT_MODE=local") from exc

    settings = get_settings()
    router = Router()

    class NightFlow(StatesGroup):
        slept = State()
        quality = State()
        sleepiness = State()
        stress = State()
        free_minutes = State()
        alarm = State()
        audio = State()

    class DayRecoveryFlow(StatesGroup):
        choice = State()
        free_minutes = State()

    class TechniqueFlow(StatesGroup):
        kind = State()
        quality = State()
        wake_feeling = State()

    class WakeFlow(StatesGroup):
        slept = State()
        quality = State()
        feeling = State()
        helpfulness = State()
        note = State()

    class AlarmFlow(StatesGroup):
        minutes = State()

    def menu_keyboard() -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🛏 Рассчитать отбой"), KeyboardButton(text="🌙 Заснуть ночью")],
                [KeyboardButton(text="⚡ Power nap"), KeyboardButton(text="🧘 Медитация")],
                [KeyboardButton(text="💤 Быстро заснуть"), KeyboardButton(text="🌅 Хорошее пробуждение")],
                [KeyboardButton(text="✅ Я проснулся"), KeyboardButton(text="📊 Статистика")],
                [KeyboardButton(text="📜 История"), KeyboardButton(text="⏰ Будильник")],
                [KeyboardButton(text="⭐ Premium"), KeyboardButton(text="⚙️ Настройки")],
            ],
            resize_keyboard=True,
        )

    def scale_keyboard() -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=str(value)) for value in range(1, 6)]], resize_keyboard=True)

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        user = services.start_user(message.from_user.id, message.from_user.username if message.from_user else None)
        services.accept_consents(user.id)
        await message.answer(CONSENT_TEXT)
        await message.answer(MAIN_MENU, reply_markup=menu_keyboard())

    @router.message(F.text == "В меню")
    async def show_menu(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer(MAIN_MENU, reply_markup=menu_keyboard())

    @router.message(F.text == "Отменить сценарий")
    async def cancel_flow(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Сценарий отменен. Возвращаю в меню.", reply_markup=menu_keyboard())

    @router.message(F.text == "📊 Статистика")
    async def stats(message: Message) -> None:
        user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
        summary = services.summary(user.id, 7)
        await message.answer(_summary_text(summary), reply_markup=menu_keyboard())

    @router.message(F.text == "📜 История")
    async def history(message: Message) -> None:
        user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
        await message.answer(_history_text(services.history(user.id, 5)), reply_markup=menu_keyboard())

    @router.message(F.text == "⭐ Premium")
    async def premium(message: Message) -> None:
        user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
        services.analytics.track(AnalyticsEventName.PREMIUM_SCREEN_VIEWED, user.id, {"source": "telegram"})
        lines = ["⭐ Premium", "", "Расширенные сценарии, глубокая история, weekly insights и больше контента.", "", "Тарифы:"]
        for plan in PLANS.values():
            lines.append(f"- {plan.title}: {plan.price_minor / 100:.0f} {plan.currency} / {plan.period_days} дней")
        lines.append("")
        lines.append("В локальном режиме платежи работают через mock provider в Swagger: /billing/checkout")
        await message.answer("\n".join(lines), reply_markup=menu_keyboard())

    @router.message(F.text == "⚙️ Настройки")
    async def settings_view(message: Message) -> None:
        user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
        prefs = user.preferences
        await message.answer(
            "⚙️ Настройки\n\n"
            f"Часовой пояс: {prefs.timezone}\n"
            f"Язык: {prefs.language}\n"
            f"Цель сна: {prefs.target_sleep_minutes // 60} ч {prefs.target_sleep_minutes % 60:02d} мин\n"
            f"Power nap по умолчанию: {prefs.default_nap_duration} мин\n"
            "\nВ этой локальной версии настройки можно менять через Swagger: PUT /users/{telegram_id}/profile",
            reply_markup=menu_keyboard(),
        )

    @router.message(F.text == "⏰ Будильник")
    async def alarm_start(message: Message, state: FSMContext) -> None:
        await state.set_state(AlarmFlow.minutes)
        await message.answer("Через сколько минут разбудить? Например: 10, 15 или 20")

    @router.message(AlarmFlow.minutes)
    async def alarm_minutes(message: Message, state: FSMContext) -> None:
        value = _parse_int(message.text, 1, 720)
        if value is None:
            await message.answer("Введи число минут от 1 до 720")
            return
        user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
        key = f"tg-{user.telegram_id}-{int(datetime.now(timezone.utc).timestamp())}"
        alarm = services.create_power_nap_alarm(user, value, key)
        await state.clear()
        await message.answer(
            f"⏰ Будильник поставлен на {value} мин.\n"
            f"Код отключения: {alarm.dismiss_code}",
            reply_markup=menu_keyboard(),
        )

    @router.message(F.text == "✅ Я проснулся")
    async def wake_start(message: Message, state: FSMContext) -> None:
        await state.set_state(WakeFlow.slept)
        await message.answer("Сколько минут примерно спал? Например: 420")

    @router.message(WakeFlow.slept)
    async def wake_slept(message: Message, state: FSMContext) -> None:
        value = _parse_int(message.text, 0, 1440)
        if value is None:
            await message.answer("Введи число минут от 0 до 1440")
            return
        await state.update_data(slept=value)
        await state.set_state(WakeFlow.quality)
        await message.answer("Качество сна 1-5?", reply_markup=scale_keyboard())

    @router.message(WakeFlow.quality)
    async def wake_quality(message: Message, state: FSMContext) -> None:
        value = _parse_int(message.text, 1, 5)
        if value is None:
            await message.answer("Выбери число от 1 до 5")
            return
        await state.update_data(quality=value)
        await state.set_state(WakeFlow.feeling)
        await message.answer("Самочувствие после пробуждения 1-5?", reply_markup=scale_keyboard())

    @router.message(WakeFlow.feeling)
    async def wake_feeling(message: Message, state: FSMContext) -> None:
        value = _parse_int(message.text, 1, 5)
        if value is None:
            await message.answer("Выбери число от 1 до 5")
            return
        await state.update_data(feeling=value)
        await state.set_state(WakeFlow.helpfulness)
        await message.answer("Насколько рекомендация помогла 1-5?", reply_markup=scale_keyboard())

    @router.message(WakeFlow.helpfulness)
    async def wake_helpfulness(message: Message, state: FSMContext) -> None:
        value = _parse_int(message.text, 1, 5)
        if value is None:
            await message.answer("Выбери число от 1 до 5")
            return
        await state.update_data(helpfulness=value)
        await state.set_state(WakeFlow.note)
        await message.answer("Можно добавить короткую заметку. Если не хочешь - напиши пропустить")

    @router.message(WakeFlow.note)
    async def wake_note(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        note = None if (message.text or "").strip().lower() in {"пропустить", "skip", "-"} else message.text
        user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
        services.add_wake_checkin(
            user,
            slept_minutes=data["slept"],
            quality=data["quality"],
            feeling=data["feeling"],
            helpfulness=data["helpfulness"],
            audio=AudioType.SILENCE,
            note=note,
        )
        await state.clear()
        await message.answer("Записал. Это поможет точнее подбирать следующие рекомендации.", reply_markup=menu_keyboard())

    @router.message(F.text == "🛏 Рассчитать отбой")
    async def bedtime_plan(message: Message) -> None:
        user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
        recommendation = services.generate_bedtime_plan(user, reminder_enabled=True)
        await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())

    @router.message(F.text == "⚡ Power nap")
    async def power_nap_start(message: Message, state: FSMContext) -> None:
        user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
        has_data = user.preferences.wake_time is not None and bool(services.store.entries.get(user.id, []))
        if has_data:
            recommendation = services.generate_day_recovery(user, choice="power_nap", free_minutes=None, reminder_enabled=True)
            await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())
            return
        await state.set_state(DayRecoveryFlow.free_minutes)
        await state.update_data(choice="power_nap")
        await message.answer("Сколько минут реально есть на короткий сон? Например: 10, 15 или 20")

    @router.message(F.text == "🧘 Медитация")
    async def meditation_start(message: Message, state: FSMContext) -> None:
        user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
        has_data = user.preferences.wake_time is not None and bool(services.store.entries.get(user.id, []))
        if has_data:
            recommendation = services.generate_day_recovery(user, choice="meditation", free_minutes=None, reminder_enabled=True)
            await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())
            return
        await state.set_state(DayRecoveryFlow.free_minutes)
        await state.update_data(choice="meditation")
        await message.answer("Сколько минут можешь выделить на медитацию или восстановительный перерыв?")

    @router.message(DayRecoveryFlow.free_minutes)
    async def day_recovery_minutes(message: Message, state: FSMContext) -> None:
        value = _parse_int(message.text, 5, 60)
        if value is None:
            await message.answer("Введи число минут от 5 до 60")
            return
        data = await state.get_data()
        user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
        recommendation = services.generate_day_recovery(user, choice=data["choice"], free_minutes=value, reminder_enabled=True)
        await state.clear()
        await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())

    @router.message(F.text == "💤 Быстро заснуть")
    async def quick_sleep_start(message: Message, state: FSMContext) -> None:
        user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
        has_data = user.preferences.wake_time is not None and bool(services.store.entries.get(user.id, []))
        if has_data:
            recommendation = services.generate_sleep_or_wake_technique(user, kind="quick_sleep", quality=None, wake_feeling=None)
            await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())
            return
        await state.set_state(TechniqueFlow.quality)
        await state.update_data(kind="quick_sleep")
        await message.answer("Как оцениваешь последнее качество сна 1-5?", reply_markup=scale_keyboard())

    @router.message(F.text == "🌅 Хорошее пробуждение")
    async def good_wake_start(message: Message, state: FSMContext) -> None:
        user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
        has_data = user.preferences.wake_time is not None and bool(services.store.entries.get(user.id, []))
        if has_data:
            recommendation = services.generate_sleep_or_wake_technique(user, kind="good_wake", quality=None, wake_feeling=None)
            await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())
            return
        await state.set_state(TechniqueFlow.wake_feeling)
        await state.update_data(kind="good_wake")
        await message.answer("Как оцениваешь самочувствие после пробуждения 1-5?", reply_markup=scale_keyboard())

    @router.message(TechniqueFlow.quality)
    async def quick_sleep_quality(message: Message, state: FSMContext) -> None:
        value = _parse_int(message.text, 1, 5)
        if value is None:
            await message.answer("Выбери число от 1 до 5")
            return
        user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
        recommendation = services.generate_sleep_or_wake_technique(user, kind="quick_sleep", quality=value, wake_feeling=None)
        await state.clear()
        await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())

    @router.message(TechniqueFlow.wake_feeling)
    async def good_wake_feeling(message: Message, state: FSMContext) -> None:
        value = _parse_int(message.text, 1, 5)
        if value is None:
            await message.answer("Выбери число от 1 до 5")
            return
        user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
        recommendation = services.generate_sleep_or_wake_technique(user, kind="good_wake", quality=None, wake_feeling=value)
        await state.clear()
        await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())

    @router.message(F.text == "🌙 Заснуть ночью")
    async def night_start(message: Message, state: FSMContext) -> None:
        await state.set_state(NightFlow.slept)
        await message.answer("Сколько минут примерно спал прошлой ночью? Например: 420")

    @router.message(NightFlow.slept)
    async def night_slept(message: Message, state: FSMContext) -> None:
        value = _parse_int(message.text, 0, 1440)
        if value is None:
            await message.answer("Введи число минут от 0 до 1440")
            return
        await state.update_data(slept=value)
        await state.set_state(NightFlow.quality)
        await message.answer("Качество сна 1-5?", reply_markup=scale_keyboard())

    @router.message(NightFlow.quality)
    async def night_quality(message: Message, state: FSMContext) -> None:
        value = _parse_int(message.text, 1, 5)
        if value is None:
            await message.answer("Выбери число от 1 до 5")
            return
        await state.update_data(quality=value)
        await state.set_state(NightFlow.sleepiness)
        await message.answer("Сонливость сейчас 1-5?", reply_markup=scale_keyboard())

    @router.message(NightFlow.sleepiness)
    async def night_sleepiness(message: Message, state: FSMContext) -> None:
        value = _parse_int(message.text, 1, 5)
        if value is None:
            await message.answer("Выбери число от 1 до 5")
            return
        await state.update_data(sleepiness=value)
        await state.set_state(NightFlow.stress)
        await message.answer("Стресс или тревожность 1-5?", reply_markup=scale_keyboard())

    @router.message(NightFlow.stress)
    async def night_stress(message: Message, state: FSMContext) -> None:
        value = _parse_int(message.text, 1, 5)
        if value is None:
            await message.answer("Выбери число от 1 до 5")
            return
        await state.update_data(stress=value)
        await state.set_state(NightFlow.free_minutes)
        await message.answer("Сколько минут есть на подготовку ко сну?")

    @router.message(NightFlow.free_minutes)
    async def night_free_minutes(message: Message, state: FSMContext) -> None:
        value = _parse_int(message.text, 1, 240)
        if value is None:
            await message.answer("Введи число минут от 1 до 240")
            return
        await state.update_data(free_minutes=value)
        await state.set_state(NightFlow.alarm)
        await message.answer("Нужен будильник? Напиши да или нет")

    @router.message(NightFlow.alarm)
    async def night_alarm(message: Message, state: FSMContext) -> None:
        text = (message.text or "").lower()
        if text not in {"да", "нет", "yes", "no"}:
            await message.answer("Ответь да или нет")
            return
        await state.update_data(needs_alarm=text in {"да", "yes"})
        await state.set_state(NightFlow.audio)
        await message.answer("Формат: silence / rain / forest / pink_noise / guided_text / breathing_only")

    @router.message(NightFlow.audio)
    async def night_audio(message: Message, state: FSMContext) -> None:
        audio = _parse_audio(message.text)
        if audio is None:
            await message.answer("Выбери один формат из списка")
            return
        data = await state.get_data()
        user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
        recommendation = services.generate_night_recommendation(
            user=user,
            slept_minutes=data["slept"],
            quality=data["quality"],
            sleepiness=data["sleepiness"],
            stress=data["stress"],
            free_minutes=data["free_minutes"],
            needs_alarm=data["needs_alarm"],
            preferred_audio=audio,
        )
        await state.clear()
        await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)


def _summary_text(summary: object) -> str:
    if getattr(summary, "entries_count", 0) == 0:
        return "📊 Пока мало данных. После check-in здесь появится статистика за 7 дней."
    avg_duration = getattr(summary, "average_duration", None)
    duration_text = "нет данных" if avg_duration is None else f"{avg_duration / 60:.1f} ч"
    quality = getattr(summary, "average_quality", None)
    feeling = getattr(summary, "average_post_wake_feeling", None)
    debt = getattr(summary, "possible_sleep_debt_minutes", 0)
    return (
        "📊 Статистика за 7 дней\n\n"
        f"Записей: {summary.entries_count}\n"
        f"Средняя длительность: {duration_text}\n"
        f"Среднее качество: {quality if quality is not None else 'нет данных'}\n"
        f"Самочувствие после сна: {feeling if feeling is not None else 'нет данных'}\n"
        f"Оценочный долг сна: {debt} мин"
    )


def _history_text(history: dict[str, object]) -> str:
    entries = list(history.get("sleep_entries", []))
    recommendations = list(history.get("recommendations", []))
    if not entries and not recommendations:
        return "📜 История пока пустая. Используй любой сценарий или check-in - запись появится здесь."
    lines = ["📜 Последняя история", ""]
    if entries:
        lines.append("Check-ins:")
        for entry in entries[-3:]:
            lines.append(f"- сон {entry.duration_minutes} мин, качество {entry.quality}/5, польза {entry.helpfulness}/5")
    if recommendations:
        lines.append("")
        lines.append("Рекомендации:")
        for rec in recommendations[-3:]:
            lines.append(f"- {rec.recommended_mode.value}, {rec.duration_minutes} мин")
    return "\n".join(lines)


def _parse_int(text: str | None, min_value: int, max_value: int) -> int | None:
    try:
        value = int(text or "")
    except ValueError:
        return None
    if min_value <= value <= max_value:
        return value
    return None


def _parse_audio(text: str | None) -> AudioType | None:
    try:
        return AudioType(text or "")
    except ValueError:
        return None


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.bot_mode == "local":
        await run_local_bot()
        return
    await run_aiogram_bot()


if __name__ == "__main__":
    asyncio.run(main())
