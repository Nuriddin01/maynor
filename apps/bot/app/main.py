from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from apps.bot.app.local_bot import LocalBotSession
from apps.bot.app.texts import CONSENT_TEXT, MAIN_MENU, recommendation_text
from packages.billing.plans import PLANS
from packages.core.config import get_settings
from packages.core.logging import configure_logging
from packages.domain.models import AlarmStatus, AnalyticsEventName, AudioType
from packages.premium.service import PremiumExperienceService
from packages.services.facade import services

logger = logging.getLogger(__name__)

STAR_PLANS = {
  "premium_monthly": {
    "title": "Sleep Support Premium 30 дней",
    "amount": 99,
    "period_days": 30,
  },
  "premium_yearly": {
    "title": "Sleep Support Premium 365 дней",
    "amount": 999,
    "period_days": 365,
  },
}


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
    from aiogram.types import KeyboardButton, LabeledPrice, Message, PreCheckoutQuery, ReplyKeyboardMarkup
  except ImportError as exc:
    raise RuntimeError("aiogram is not installed. Install dependencies or use BOT_MODE=local") from exc

  settings = get_settings()
  router = Router()
  premium_service = PremiumExperienceService(services.store, services.billing, settings.local_db_path)

  class NightFlow(StatesGroup):
    slept = State()
    quality = State()
    sleepiness = State()
    stress = State()
    free_minutes = State()
    alarm = State()
    audio = State()

  class DayRecoveryFlow(StatesGroup):
    free_minutes = State()

  class TechniqueFlow(StatesGroup):
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

  class RoutineFlow(StatesGroup):
    kind = State()
    duration = State()

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

  def premium_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
      keyboard=[
        [KeyboardButton(text="👑 Мой Premium")],
        [KeyboardButton(text="📅 Weekly insights"), KeyboardButton(text="📈 Advanced stats")],
        [KeyboardButton(text="📚 Deep history"), KeyboardButton(text="🎧 Content packs")],
        [KeyboardButton(text="🔊 Audio library"), KeyboardButton(text="🧩 Custom routine")],
        [KeyboardButton(text="🧪 Experiments")],
        [KeyboardButton(text="Купить Premium 30 дней ⭐")],
        [KeyboardButton(text="Купить Premium 365 дней ⭐")],
        [KeyboardButton(text="В меню")],
      ],
      resize_keyboard=True,
    )

  def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
      keyboard=[[KeyboardButton(text="В меню"), KeyboardButton(text="Отменить сценарий")]],
      resize_keyboard=True,
    )

  def scale_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
      keyboard=[
        [KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="3"), KeyboardButton(text="4"), KeyboardButton(text="5")],
        [KeyboardButton(text="В меню"), KeyboardButton(text="Отменить сценарий")],
      ],
      resize_keyboard=True,
    )

  def power_nap_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
      keyboard=[
        [KeyboardButton(text="10"), KeyboardButton(text="15"), KeyboardButton(text="20")],
        [KeyboardButton(text="В меню"), KeyboardButton(text="Отменить сценарий")],
      ],
      resize_keyboard=True,
    )

  def meditation_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
      keyboard=[
        [KeyboardButton(text="5"), KeyboardButton(text="10"), KeyboardButton(text="15")],
        [KeyboardButton(text="20"), KeyboardButton(text="30"), KeyboardButton(text="45")],
        [KeyboardButton(text="В меню"), KeyboardButton(text="Отменить сценарий")],
      ],
      resize_keyboard=True,
    )

  def yes_no_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
      keyboard=[
        [KeyboardButton(text="да"), KeyboardButton(text="нет")],
        [KeyboardButton(text="В меню"), KeyboardButton(text="Отменить сценарий")],
      ],
      resize_keyboard=True,
    )

  def audio_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
      keyboard=[
        [KeyboardButton(text="Без аудио"), KeyboardButton(text="Тишина")],
        [KeyboardButton(text="Дождь"), KeyboardButton(text="Лес")],
        [KeyboardButton(text="Pink noise"), KeyboardButton(text="Только дыхание")],
        [KeyboardButton(text="Текст-гайд")],
        [KeyboardButton(text="В меню"), KeyboardButton(text="Отменить сценарий")],
      ],
      resize_keyboard=True,
    )

  def routine_type_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
      keyboard=[
        [KeyboardButton(text="Вечерняя"), KeyboardButton(text="Утренняя")],
        [KeyboardButton(text="Power nap")],
        [KeyboardButton(text="В меню"), KeyboardButton(text="Отменить сценарий")],
      ],
      resize_keyboard=True,
    )

  def routine_duration_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
      keyboard=[
        [KeyboardButton(text="5"), KeyboardButton(text="10"), KeyboardButton(text="15")],
        [KeyboardButton(text="20"), KeyboardButton(text="30"), KeyboardButton(text="45")],
        [KeyboardButton(text="В меню"), KeyboardButton(text="Отменить сценарий")],
      ],
      resize_keyboard=True,
    )

  def has_enough_user_data(user) -> bool:
    try:
      history = services.history(user.id, 1)
      return bool(history.get("sleep_entries")) or user.preferences.wake_time is not None
    except Exception:
      return user.preferences.wake_time is not None

  def get_alarm_items() -> list:
    alarm_store = services.alarms._store
    if hasattr(alarm_store, "all"):
      return list(alarm_store.all())
    return list(getattr(alarm_store, "_items", {}).values())

  def dismiss_latest_alarm_for_user(user_id, code: str | None = None):
    active_alarms = [
      alarm
      for alarm in get_alarm_items()
      if alarm.user_id == user_id
      and alarm.status in {AlarmStatus.SCHEDULED, AlarmStatus.FIRING}
      and (code is None or alarm.dismiss_code == code)
    ]
    if not active_alarms:
      return None
    active_alarms.sort(key=lambda alarm: alarm.due_at, reverse=True)
    try:
      return services.alarms.dismiss(active_alarms[0].id, code=code)
    except ValueError:
      return None

  def user_from_message(message: Message):
    return services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)

  async def require_premium(message: Message, feature_title: str) -> bool:
    user = user_from_message(message)
    if premium_service.is_premium(user.id):
      return True
    services.analytics.track(AnalyticsEventName.PAYWALL_SHOWN, user.id, {"feature": feature_title})
    await message.answer(premium_service.paywall_text(feature_title), reply_markup=premium_keyboard())
    return False

  async def send_premium_invoice(message: Message, plan_code: str) -> None:
    if plan_code not in STAR_PLANS:
      await message.answer("Тариф не найден. Вернись в меню и попробуй снова.", reply_markup=menu_keyboard())
      return

    user = user_from_message(message)
    plan = STAR_PLANS[plan_code]
    idempotency_key = f"tg-stars-{user.telegram_id}-{plan_code}-{uuid4().hex}"
    services.billing.create_checkout(user.id, plan_code, idempotency_key)

    await message.answer_invoice(
      title=str(plan["title"]),
      description="Доступ к Premium-функциям Sleep Support Bot. Бот не заменяет врача и не ставит диагнозы.",
      payload=f"premium:{plan_code}:{idempotency_key}",
      provider_token="",
      currency="XTR",
      prices=[LabeledPrice(label=str(plan["title"]), amount=int(plan["amount"]))],
    )

  @router.message(CommandStart())
  async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
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
    await message.answer("Сценарий отменён. Возвращаю в меню.", reply_markup=menu_keyboard())

  @router.message(F.text.startswith("/"))
  async def unknown_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Я не знаю такую команду. Вернул тебя в главное меню.", reply_markup=menu_keyboard())

  @router.message(F.text == "⭐ Premium")
  async def premium(message: Message) -> None:
    user = user_from_message(message)
    services.analytics.track(AnalyticsEventName.PREMIUM_SCREEN_VIEWED, user.id, {"source": "telegram"})
    lines = [
      "⭐ Premium",
      "",
      premium_service.status_text(user.id),
      "",
      "Что входит:",
      "- weekly insights",
      "- advanced stats",
      "- deep history",
      "- content packs",
      "- richer audio library",
      "- custom routines",
      "- safe experiments",
      "",
      "Оплата проходит через Telegram Stars. Карту в боте вводить не нужно.",
      "",
      "Тарифы:",
    ]
    for plan_code, plan in STAR_PLANS.items():
      base_plan = PLANS.get(plan_code)
      title = base_plan.title if base_plan else str(plan["title"])
      lines.append(f"- {title}: {plan['amount']} ⭐ / {plan['period_days']} дней")
    await message.answer("\n".join(lines), reply_markup=premium_keyboard())

  @router.message(F.text == "👑 Мой Premium")
  async def premium_status(message: Message) -> None:
    user = user_from_message(message)
    await message.answer(premium_service.status_text(user.id), reply_markup=premium_keyboard())

  @router.message(F.text == "📅 Weekly insights")
  async def weekly_insights(message: Message) -> None:
    if not await require_premium(message, "Weekly insights"):
      return
    user = user_from_message(message)
    await message.answer(premium_service.weekly_insights_text(user.id), reply_markup=premium_keyboard())

  @router.message(F.text == "📈 Advanced stats")
  async def advanced_stats(message: Message) -> None:
    if not await require_premium(message, "Advanced stats"):
      return
    user = user_from_message(message)
    await message.answer(premium_service.advanced_stats_text(user.id), reply_markup=premium_keyboard())

  @router.message(F.text == "📚 Deep history")
  async def deep_history(message: Message) -> None:
    if not await require_premium(message, "Deep history"):
      return
    user = user_from_message(message)
    await message.answer(premium_service.deep_history_text(user.id), reply_markup=premium_keyboard())

  @router.message(F.text == "🎧 Content packs")
  async def content_packs(message: Message) -> None:
    if not await require_premium(message, "Content packs"):
      return
    user = user_from_message(message)
    await message.answer(premium_service.content_packs_text(user.id), reply_markup=premium_keyboard())

  @router.message(F.text == "🔊 Audio library")
  async def audio_library(message: Message) -> None:
    if not await require_premium(message, "Audio library"):
      return
    user = user_from_message(message)
    await message.answer(premium_service.audio_library_text(user.id), reply_markup=premium_keyboard())

  @router.message(F.text == "🧪 Experiments")
  async def experiments(message: Message) -> None:
    if not await require_premium(message, "Experiments"):
      return
    user = user_from_message(message)
    await message.answer(premium_service.experiments_text(user.id), reply_markup=premium_keyboard())

  @router.message(F.text == "🧩 Custom routine")
  async def custom_routine_start(message: Message, state: FSMContext) -> None:
    if not await require_premium(message, "Custom routine"):
      return
    user = user_from_message(message)
    existing = premium_service.routines_text(user.id)
    await state.clear()
    await state.set_state(RoutineFlow.kind)
    await message.answer(existing)
    await message.answer("Какую рутину создать?", reply_markup=routine_type_keyboard())

  @router.message(RoutineFlow.kind)
  async def custom_routine_kind(message: Message, state: FSMContext) -> None:
    mapping = {"вечерняя": "evening", "утренняя": "morning", "power nap": "nap", "павер нап": "nap"}
    kind = mapping.get((message.text or "").strip().lower())
    if kind is None:
      await message.answer("Выбери тип рутины кнопкой ниже.", reply_markup=routine_type_keyboard())
      return
    await state.update_data(kind=kind)
    await state.set_state(RoutineFlow.duration)
    await message.answer("Сколько минут выделить на рутину?", reply_markup=routine_duration_keyboard())

  @router.message(RoutineFlow.duration)
  async def custom_routine_duration(message: Message, state: FSMContext) -> None:
    value = _parse_int(message.text, 5, 60)
    if value is None:
      await message.answer("Введи число минут от 5 до 60.", reply_markup=routine_duration_keyboard())
      return
    data = await state.get_data()
    user = user_from_message(message)
    routine = premium_service.create_routine(user.id, data["kind"], value)
    await state.clear()
    lines = [f"🧩 Рутина сохранена: {routine.title}", f"Длительность: {routine.duration_minutes} мин", ""]
    lines.extend(f"{index}. {step}" for index, step in enumerate(routine.steps, 1))
    await message.answer("\n".join(lines), reply_markup=premium_keyboard())

  @router.message(F.text == "Купить Premium 30 дней ⭐")
  async def buy_monthly(message: Message) -> None:
    await send_premium_invoice(message, "premium_monthly")

  @router.message(F.text == "Купить Premium 365 дней ⭐")
  async def buy_yearly(message: Message) -> None:
    await send_premium_invoice(message, "premium_yearly")

  @router.pre_checkout_query()
  async def pre_checkout(query: PreCheckoutQuery) -> None:
    payload = query.invoice_payload or ""
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != "premium" or parts[1] not in STAR_PLANS:
      await query.answer(ok=False, error_message="Не удалось проверить платёж. Открой Premium заново.")
      return
    plan = STAR_PLANS[parts[1]]
    if query.currency != "XTR" or query.total_amount != int(plan["amount"]):
      await query.answer(ok=False, error_message="Сумма платежа не совпадает с выбранным тарифом.")
      return
    await query.answer(ok=True)

  @router.message(F.successful_payment)
  async def successful_payment(message: Message) -> None:
    payment = message.successful_payment
    if payment is None:
      return
    payload = payment.invoice_payload or ""
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != "premium" or parts[1] not in STAR_PLANS:
      await message.answer("Платёж получен, но тариф не распознан. Напиши администратору.", reply_markup=menu_keyboard())
      return
    plan_code = parts[1]
    idempotency_key = parts[2]
    user = user_from_message(message)
    subscription = services.billing.confirm_telegram_stars_payment(
      user_id=user.id,
      plan_code=plan_code,
      idempotency_key=idempotency_key,
      amount_minor=payment.total_amount,
      currency=payment.currency,
      telegram_payment_charge_id=payment.telegram_payment_charge_id,
    )
    services.analytics.track(
      AnalyticsEventName.SUBSCRIPTION_STARTED,
      user.id,
      {"plan": plan_code, "provider": "telegram_stars", "amount": payment.total_amount, "currency": payment.currency},
    )
    await message.answer(
      "Готово, Premium активирован ✅\n\n"
      f"Тариф: {STAR_PLANS[plan_code]['title']}\n"
      f"Доступ до: {subscription.current_period_end.strftime('%d.%m.%Y')}\n\n"
      "Теперь доступны weekly insights, advanced stats, deep history, content packs и custom routines.",
      reply_markup=premium_keyboard(),
    )

  @router.message(F.text == "📊 Статистика")
  async def stats(message: Message) -> None:
    user = user_from_message(message)
    await message.answer(_summary_text(services.summary(user.id, 7)), reply_markup=menu_keyboard())

  @router.message(F.text == "📜 История")
  async def history(message: Message) -> None:
    user = user_from_message(message)
    await message.answer(_history_text(services.history(user.id, 5)), reply_markup=menu_keyboard())

  @router.message(F.text == "⚙️ Настройки")
  async def settings_view(message: Message) -> None:
    user = user_from_message(message)
    prefs = user.preferences
    await message.answer(
      "⚙️ Настройки\n\n"
      f"Часовой пояс: {prefs.timezone}\n"
      f"Язык: {prefs.language}\n"
      f"Цель сна: {prefs.target_sleep_minutes // 60} ч {prefs.target_sleep_minutes % 60:02d} мин\n"
      f"Power nap по умолчанию: {prefs.default_nap_duration} мин\n"
      "\nНастройки можно менять через Swagger: PUT /users/{telegram_id}/profile",
      reply_markup=menu_keyboard(),
    )

  @router.message(F.text == "⏰ Будильник")
  async def alarm_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AlarmFlow.minutes)
    await message.answer("Через сколько минут разбудить? Например: 10, 15 или 20.", reply_markup=power_nap_keyboard())

  @router.message(AlarmFlow.minutes)
  async def alarm_minutes(message: Message, state: FSMContext) -> None:
    value = _parse_int(message.text, 1, 720)
    if value is None:
      await message.answer("Введи число минут от 1 до 720.", reply_markup=cancel_keyboard())
      return
    user = user_from_message(message)
    key = f"tg-{user.telegram_id}-{int(datetime.now(timezone.utc).timestamp())}"
    alarm = services.create_power_nap_alarm(user, value, key)
    await state.clear()
    await message.answer(
      f"⏰ Будильник поставлен на {value} мин.\n"
      f"Код отключения: {alarm.dismiss_code}\n\n"
      "Когда он сработает, отправь этот код одним сообщением или нажми «✅ Я проснулся».",
      reply_markup=menu_keyboard(),
    )

  @router.message(F.text == "✅ Я проснулся")
  async def wake_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = user_from_message(message)
    alarm = dismiss_latest_alarm_for_user(user.id)
    if alarm is not None:
      services.analytics.track(AnalyticsEventName.ALARM_DISMISSED, user.id, {"alarm_id": str(alarm.id), "source": "wake_button"})
    await state.set_state(WakeFlow.slept)
    await message.answer("Сколько часов примерно спал? Например: 5, 5.5 или 6.", reply_markup=cancel_keyboard())

  @router.message(WakeFlow.slept)
  async def wake_slept(message: Message, state: FSMContext) -> None:
    value = _parse_sleep_hours(message.text, 0, 24)
    if value is None:
      await message.answer("Введи число часов: 5, 5.5 или 6. Можно использовать только шаг 0.5 часа.", reply_markup=cancel_keyboard())
      return
    await state.update_data(slept=value)
    await state.set_state(WakeFlow.quality)
    await message.answer("Качество сна 1-5?", reply_markup=scale_keyboard())

  @router.message(WakeFlow.quality)
  async def wake_quality(message: Message, state: FSMContext) -> None:
    value = _parse_int(message.text, 1, 5)
    if value is None:
      await message.answer("Выбери число от 1 до 5.", reply_markup=scale_keyboard())
      return
    await state.update_data(quality=value)
    await state.set_state(WakeFlow.feeling)
    await message.answer("Самочувствие после пробуждения 1-5?", reply_markup=scale_keyboard())

  @router.message(WakeFlow.feeling)
  async def wake_feeling(message: Message, state: FSMContext) -> None:
    value = _parse_int(message.text, 1, 5)
    if value is None:
      await message.answer("Выбери число от 1 до 5.", reply_markup=scale_keyboard())
      return

    user = user_from_message(message)
    has_recommendation = _has_previous_recommendation(user.id)
    await state.update_data(feeling=value, has_recommendation=has_recommendation)

    if not has_recommendation:
      await state.update_data(helpfulness=3)
      await state.set_state(WakeFlow.note)
      await message.answer(
        "Пока нет прошлой рекомендации, поэтому вопрос о её пользе пропускаю.\n\n"
        "Можно добавить короткую заметку. Если не хочешь - напиши «пропустить».",
        reply_markup=cancel_keyboard(),
      )
      return

    await state.set_state(WakeFlow.helpfulness)
    await message.answer(
      "Насколько вчерашняя рекомендация помогла уснуть 1-5?",
      reply_markup=scale_keyboard(),
    )

  @router.message(WakeFlow.helpfulness)
  async def wake_helpfulness(message: Message, state: FSMContext) -> None:
    value = _parse_int(message.text, 1, 5)
    if value is None:
      await message.answer("Выбери число от 1 до 5.", reply_markup=scale_keyboard())
      return
    await state.update_data(helpfulness=value)
    await state.set_state(WakeFlow.note)
    await message.answer("Можно добавить короткую заметку. Если не хочешь - напиши «пропустить».", reply_markup=cancel_keyboard())

  @router.message(WakeFlow.note)
  async def wake_note(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    note = None if (message.text or "").strip().lower() in {"пропустить", "skip", "-"} else message.text
    user = user_from_message(message)
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
  async def bedtime_plan(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = user_from_message(message)
    recommendation = services.generate_bedtime_plan(user, reminder_enabled=True)
    await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())

  @router.message(F.text == "⚡ Power nap")
  async def power_nap_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = user_from_message(message)
    if has_enough_user_data(user):
      recommendation = services.generate_day_recovery(user, choice="power_nap", free_minutes=None, reminder_enabled=True)
      await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())
      return
    await state.set_state(DayRecoveryFlow.free_minutes)
    await state.update_data(choice="power_nap")
    await message.answer(
      "Сколько минут реально есть на power nap?\n\n"
      "Выбери 10, 15 или 20 минут. Если есть меньше 10 минут, лучше сделать короткий recovery break.",
      reply_markup=power_nap_keyboard(),
    )

  @router.message(F.text == "🧘 Медитация")
  async def meditation_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = user_from_message(message)
    if has_enough_user_data(user):
      recommendation = services.generate_day_recovery(user, choice="meditation", free_minutes=None, reminder_enabled=True)
      await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())
      return
    await state.set_state(DayRecoveryFlow.free_minutes)
    await state.update_data(choice="meditation")
    await message.answer("Сколько минут можешь выделить на медитацию или восстановительный перерыв?", reply_markup=meditation_keyboard())

  @router.message(DayRecoveryFlow.free_minutes)
  async def day_recovery_minutes(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    choice = data.get("choice")
    value = _parse_int(message.text, 1, 120)
    if value is None:
      await message.answer("Введи число минут.", reply_markup=cancel_keyboard())
      return
    if choice == "power_nap" and value not in {10, 15, 20}:
      await message.answer(
        "Power nap лучше выбрать строго на 10, 15 или 20 минут.\n\n"
        "Если времени меньше 10 минут, лучше используй «🧘 Медитация» как короткий recovery break.",
        reply_markup=power_nap_keyboard(),
      )
      return
    if choice == "meditation" and not 5 <= value <= 60:
      await message.answer("Для этого сценария выбери время от 5 до 60 минут.", reply_markup=meditation_keyboard())
      return
    user = user_from_message(message)
    recommendation = services.generate_day_recovery(user, choice=choice, free_minutes=value, reminder_enabled=True)
    await state.clear()
    await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())

  @router.message(F.text == "💤 Быстро заснуть")
  async def quick_sleep_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = user_from_message(message)
    if has_enough_user_data(user):
      recommendation = services.generate_sleep_or_wake_technique(user, kind="quick_sleep", quality=None, wake_feeling=None)
      await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())
      return
    await state.set_state(TechniqueFlow.quality)
    await state.update_data(kind="quick_sleep")
    await message.answer("Как оцениваешь последнее качество сна 1-5?", reply_markup=scale_keyboard())

  @router.message(F.text == "🌅 Хорошее пробуждение")
  async def good_wake_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = user_from_message(message)
    if has_enough_user_data(user):
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
      await message.answer("Выбери число от 1 до 5.", reply_markup=scale_keyboard())
      return
    user = user_from_message(message)
    recommendation = services.generate_sleep_or_wake_technique(user, kind="quick_sleep", quality=value, wake_feeling=None)
    await state.clear()
    await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())

  @router.message(TechniqueFlow.wake_feeling)
  async def good_wake_feeling(message: Message, state: FSMContext) -> None:
    value = _parse_int(message.text, 1, 5)
    if value is None:
      await message.answer("Выбери число от 1 до 5.", reply_markup=scale_keyboard())
      return
    user = user_from_message(message)
    recommendation = services.generate_sleep_or_wake_technique(user, kind="good_wake", quality=None, wake_feeling=value)
    await state.clear()
    await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())

  @router.message(F.text == "🌙 Заснуть ночью")
  async def night_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(NightFlow.slept)
    await message.answer("Сколько часов примерно спал прошлой ночью? Например: 5, 5.5 или 6.", reply_markup=cancel_keyboard())

  @router.message(NightFlow.slept)
  async def night_slept(message: Message, state: FSMContext) -> None:
    value = _parse_sleep_hours(message.text, 0, 24)
    if value is None:
      await message.answer("Введи число часов: 5, 5.5 или 6. Можно использовать только шаг 0.5 часа.", reply_markup=cancel_keyboard())
      return
    await state.update_data(slept=value)
    await state.set_state(NightFlow.quality)
    await message.answer("Качество сна 1-5?", reply_markup=scale_keyboard())

  @router.message(NightFlow.quality)
  async def night_quality(message: Message, state: FSMContext) -> None:
    value = _parse_int(message.text, 1, 5)
    if value is None:
      await message.answer("Выбери число от 1 до 5.", reply_markup=scale_keyboard())
      return
    await state.update_data(quality=value)
    await state.set_state(NightFlow.sleepiness)
    await message.answer("Сонливость сейчас 1-5?", reply_markup=scale_keyboard())

  @router.message(NightFlow.sleepiness)
  async def night_sleepiness(message: Message, state: FSMContext) -> None:
    value = _parse_int(message.text, 1, 5)
    if value is None:
      await message.answer("Выбери число от 1 до 5.", reply_markup=scale_keyboard())
      return
    await state.update_data(sleepiness=value)
    await state.set_state(NightFlow.stress)
    await message.answer("Стресс или тревожность 1-5?", reply_markup=scale_keyboard())

  @router.message(NightFlow.stress)
  async def night_stress(message: Message, state: FSMContext) -> None:
    value = _parse_int(message.text, 1, 5)
    if value is None:
      await message.answer("Выбери число от 1 до 5.", reply_markup=scale_keyboard())
      return
    await state.update_data(stress=value)
    await state.set_state(NightFlow.free_minutes)
    await message.answer("Сколько минут есть на подготовку ко сну?", reply_markup=cancel_keyboard())

  @router.message(NightFlow.free_minutes)
  async def night_free_minutes(message: Message, state: FSMContext) -> None:
    value = _parse_int(message.text, 1, 240)
    if value is None:
      await message.answer("Введи число минут от 1 до 240.", reply_markup=cancel_keyboard())
      return
    await state.update_data(free_minutes=value)
    await state.set_state(NightFlow.alarm)
    await message.answer("Нужен будильник?", reply_markup=yes_no_keyboard())

  @router.message(NightFlow.alarm)
  async def night_alarm(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip().lower()
    if text not in {"да", "нет", "yes", "no"}:
      await message.answer("Ответь «да» или «нет».", reply_markup=yes_no_keyboard())
      return
    await state.update_data(needs_alarm=text in {"да", "yes"})
    await state.set_state(NightFlow.audio)
    await message.answer("Выбери формат сопровождения:", reply_markup=audio_keyboard())

  @router.message(NightFlow.audio)
  async def night_audio(message: Message, state: FSMContext) -> None:
    audio = _parse_audio(message.text)
    if audio is None:
      await message.answer("Выбери формат кнопкой ниже.", reply_markup=audio_keyboard())
      return
    data = await state.get_data()
    user = user_from_message(message)
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

  @router.message(F.text.regexp(r"^\d{4}$"))
  async def dismiss_alarm_by_code(message: Message, state: FSMContext) -> None:
    if await state.get_state():
      await message.answer("Я сейчас жду ответ по текущему сценарию. Можно нажать «В меню».", reply_markup=cancel_keyboard())
      return
    user = user_from_message(message)
    code = (message.text or "").strip()
    alarm = dismiss_latest_alarm_for_user(user.id, code=code)
    if alarm is None:
      await message.answer("Не нашёл активный будильник с таким кодом. Проверь код или нажми «✅ Я проснулся».", reply_markup=menu_keyboard())
      return
    services.analytics.track(AnalyticsEventName.ALARM_DISMISSED, user.id, {"alarm_id": str(alarm.id), "source": "telegram_code"})
    await message.answer("Будильник отключён ✅\n\nКогда будешь готов, нажми «✅ Я проснулся», чтобы сохранить check-in.", reply_markup=menu_keyboard())

  @router.message()
  async def fallback(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state:
      await message.answer("Я сейчас жду ответ по текущему сценарию. Можно продолжить или нажать «В меню».", reply_markup=cancel_keyboard())
      return
    await message.answer("Не понял сообщение. Выбери действие в меню.", reply_markup=menu_keyboard())

  bot = Bot(token=settings.telegram_bot_token)
  dispatcher = Dispatcher()
  dispatcher.include_router(router)
  await dispatcher.start_polling(bot, handle_signals=False)


def _summary_text(summary: object) -> str:
  if getattr(summary, "entries_count", 0) == 0:
    return "📊 Пока мало данных. После check-in здесь появится статистика за 7 дней."

  avg_duration = getattr(summary, "average_duration", None)
  duration_text = "нет данных" if avg_duration is None else _format_hours(int(avg_duration), round_to_half=True)
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
      lines.append(f"- сон {_format_hours(entry.duration_minutes)}, качество {entry.quality}/5, польза {entry.helpfulness}/5")
  if recommendations:
    lines.append("")
    lines.append("Рекомендации:")
    for rec in recommendations[-3:]:
      lines.append(f"- {rec.recommended_mode.value}, {rec.duration_minutes} мин")
  return "\n".join(lines)


def _has_previous_recommendation(user_id: object) -> bool:
  try:
    history = services.history(user_id, 1)
  except Exception:
    return False
  return bool(history.get("recommendations"))


def _format_hours(minutes: int, round_to_half: bool = False) -> str:
  value = minutes / 60
  if round_to_half:
    value = round(value * 2) / 2
  if float(value).is_integer():
    return f"{int(value)} ч"
  return f"{value:.1f} ч"


def _parse_int(text: str | None, min_value: int, max_value: int) -> int | None:
  try:
    value = int((text or "").strip())
  except ValueError:
    return None
  if min_value <= value <= max_value:
    return value
  return None


def _parse_sleep_hours(text: str | None, min_hours: int, max_hours: int) -> int | None:
  raw = (text or "").strip().lower().replace(",", ".")
  raw = raw.replace("часов", "").replace("часа", "").replace("час", "").replace("ч", "").strip()
  try:
    value = float(raw)
  except ValueError:
    return None

  if not min_hours <= value <= max_hours:
    return None

  doubled = value * 2
  if abs(doubled - round(doubled)) > 1e-9:
    return None

  return int(round(value * 60))


def _parse_audio(text: str | None) -> AudioType | None:
  normalized = (text or "").strip().lower().replace("ё", "е")
  aliases: dict[str, list[str]] = {
    "без аудио": ["no_audio", "silence"],
    "no_audio": ["no_audio", "silence"],
    "нет": ["no_audio", "silence"],
    "тишина": ["silence", "no_audio"],
    "silence": ["silence", "no_audio"],
    "дождь": ["rain"],
    "rain": ["rain"],
    "лес": ["forest"],
    "forest": ["forest"],
    "pink noise": ["pink_noise"],
    "pink_noise": ["pink_noise"],
    "розовый шум": ["pink_noise"],
    "текст-гайд": ["guided_text"],
    "текст": ["guided_text"],
    "guided_text": ["guided_text"],
    "только дыхание": ["breathing_only"],
    "дыхание": ["breathing_only"],
    "breathing_only": ["breathing_only"],
  }
  candidates = aliases.get(normalized, [normalized])
  for candidate in candidates:
    try:
      return AudioType(candidate)
    except ValueError:
      continue
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
