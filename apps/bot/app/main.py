from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from apps.bot.app.local_bot import LocalBotSession
from apps.bot.app.texts import CONSENT_TEXT, MAIN_MENU, recommendation_text
from packages.analytics.events import AnalyticsEventName
from packages.billing.plans import PLANS
from packages.core.config import get_settings
from packages.core.logging import configure_logging
from packages.domain.models import (
  AudioType,
  BillingProviderName,
  PaymentIntent,
  Subscription,
  SubscriptionStatus,
  new_uuid,
)
from packages.services.facade import services

logger = logging.getLogger(__name__)

STAR_PLANS = {
  "premium_monthly": {
    "title": "Sleep Support Premium 30 дней",
    "amount": 299,
    "period_days": 30,
  },
  "premium_yearly": {
    "title": "Sleep Support Premium 365 дней",
    "amount": 2490,
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
    from aiogram.types import (
      KeyboardButton,
      LabeledPrice,
      Message,
      PreCheckoutQuery,
      ReplyKeyboardMarkup,
    )
  except ImportError as exc:
    raise RuntimeError("aiogram is not installed. Install dependencies or use BOT_MODE=local") from exc

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
    return ReplyKeyboardMarkup(
      keyboard=[
        [
          KeyboardButton(text="1"),
          KeyboardButton(text="2"),
          KeyboardButton(text="3"),
          KeyboardButton(text="4"),
          KeyboardButton(text="5"),
        ],
        [KeyboardButton(text="В меню"), KeyboardButton(text="Отменить сценарий")],
      ],
      resize_keyboard=True,
    )

  def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
      keyboard=[
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

  def premium_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
      keyboard=[
        [KeyboardButton(text="Купить Premium 30 дней ⭐")],
        [KeyboardButton(text="Купить Premium 365 дней ⭐")],
        [KeyboardButton(text="В меню")],
      ],
      resize_keyboard=True,
    )

  def has_enough_user_data(user) -> bool:
    try:
      history = services.history(user.id, 1)
      return bool(history.get("sleep_entries")) or user.preferences.wake_time is not None
    except Exception:
      return user.preferences.wake_time is not None

  async def send_premium_invoice(message: Message, plan_code: str) -> None:
    if plan_code not in STAR_PLANS:
      await message.answer("Тариф не найден. Вернись в меню и попробуй снова.", reply_markup=menu_keyboard())
      return

    user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
    plan = STAR_PLANS[plan_code]
    idempotency_key = f"tg-stars-{user.telegram_id}-{plan_code}-{uuid4().hex}"

    try:
      services.billing.create_checkout(user.id, plan_code, idempotency_key)
    except Exception:
      logger.exception("Failed to create checkout intent")

    await message.answer_invoice(
      title=str(plan["title"]),
      description=(
        "Доступ к Premium-функциям Sleep Support Bot. "
        "Бот не заменяет врача и не ставит диагнозы."
      ),
      payload=f"premium:{plan_code}:{idempotency_key}",
      provider_token="",
      currency="XTR",
      prices=[LabeledPrice(label=str(plan["title"]), amount=int(plan["amount"]))],
    )

  def activate_telegram_stars_subscription(
    user_id,
    plan_code: str,
    idempotency_key: str,
    amount_minor: int,
    currency: str,
    telegram_payment_charge_id: str,
  ) -> Subscription:
    now = datetime.now(timezone.utc)
    plan = STAR_PLANS[plan_code]

    confirm_method = getattr(services.billing, "confirm_telegram_stars_payment", None)
    if callable(confirm_method):
      return confirm_method(
        user_id=user_id,
        plan_code=plan_code,
        idempotency_key=idempotency_key,
        amount_minor=amount_minor,
        currency=currency,
        telegram_payment_charge_id=telegram_payment_charge_id,
        now=now,
      )

    store = services.billing._store

    existing = store.get_payment(idempotency_key)
    payment = PaymentIntent(
      id=existing.id if existing else new_uuid(),
      user_id=user_id,
      plan_code=plan_code,
      provider=BillingProviderName.TELEGRAM_STARS,
      amount_minor=amount_minor,
      currency=currency,
      status="paid",
      payment_url=f"telegram-stars://{telegram_payment_charge_id}",
      idempotency_key=idempotency_key,
      created_at=existing.created_at if existing else now,
    )
    store.save_payment(payment)

    subscription = Subscription(
      id=new_uuid(),
      user_id=user_id,
      plan_code=plan_code,
      status=SubscriptionStatus.ACTIVE,
      provider=BillingProviderName.TELEGRAM_STARS,
      current_period_end=now + timedelta(days=int(plan["period_days"])),
      created_at=now,
    )
    return store.save_subscription(subscription)

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
    await message.answer(
      "Я не знаю такую команду. Вернул тебя в главное меню.",
      reply_markup=menu_keyboard(),
    )

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

    lines = [
      "⭐ Premium",
      "",
      "Что входит:",
      "- расширенные сценарии сна и восстановления",
      "- глубокая история",
      "- advanced analytics",
      "- weekly insights",
      "- больше контента",
      "",
      "Оплата проходит через Telegram Stars.",
      "Карту в боте вводить не нужно.",
      "",
      "Тарифы:",
    ]

    for plan_code, plan in STAR_PLANS.items():
      base_plan = PLANS.get(plan_code)
      title = base_plan.title if base_plan else str(plan["title"])
      lines.append(f"- {title}: {plan['amount']} ⭐ / {plan['period_days']} дней")

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
      await message.answer(
        "Платёж получен, но тариф не распознан. Напиши администратору.",
        reply_markup=menu_keyboard(),
      )
      return

    plan_code = parts[1]
    idempotency_key = parts[2]
    user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)

    subscription = activate_telegram_stars_subscription(
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
      {
        "plan": plan_code,
        "provider": "telegram_stars",
        "amount": payment.total_amount,
        "currency": payment.currency,
      },
    )

    await message.answer(
      "Готово, Premium активирован ✅\n\n"
      f"Тариф: {STAR_PLANS[plan_code]['title']}\n"
      f"Доступ до: {subscription.current_period_end.strftime('%d.%m.%Y')}\n\n"
      "Спасибо за поддержку проекта.",
      reply_markup=menu_keyboard(),
    )

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
      "\nНастройки можно менять через Swagger: PUT /users/{telegram_id}/profile",
      reply_markup=menu_keyboard(),
    )

  @router.message(F.text == "⏰ Будильник")
  async def alarm_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AlarmFlow.minutes)
    await message.answer("Через сколько минут разбудить? Например: 10, 15 или 20", reply_markup=power_nap_keyboard())

  @router.message(AlarmFlow.minutes)
  async def alarm_minutes(message: Message, state: FSMContext) -> None:
    value = _parse_int(message.text, 1, 720)
    if value is None:
      await message.answer("Введи число минут от 1 до 720.", reply_markup=cancel_keyboard())
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
    await state.clear()
    await state.set_state(WakeFlow.slept)
    await message.answer("Сколько минут примерно спал? Например: 420", reply_markup=cancel_keyboard())

  @router.message(WakeFlow.slept)
  async def wake_slept(message: Message, state: FSMContext) -> None:
    value = _parse_int(message.text, 0, 1440)
    if value is None:
      await message.answer("Введи число минут от 0 до 1440.", reply_markup=cancel_keyboard())
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

    await state.update_data(feeling=value)
    await state.set_state(WakeFlow.helpfulness)
    await message.answer("Насколько рекомендация помогла 1-5?", reply_markup=scale_keyboard())

  @router.message(WakeFlow.helpfulness)
  async def wake_helpfulness(message: Message, state: FSMContext) -> None:
    value = _parse_int(message.text, 1, 5)
    if value is None:
      await message.answer("Выбери число от 1 до 5.", reply_markup=scale_keyboard())
      return

    await state.update_data(helpfulness=value)
    await state.set_state(WakeFlow.note)
    await message.answer(
      "Можно добавить короткую заметку. Если не хочешь - напиши «пропустить».",
      reply_markup=cancel_keyboard(),
    )

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
  async def bedtime_plan(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
    recommendation = services.generate_bedtime_plan(user, reminder_enabled=True)
    await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())

  @router.message(F.text == "⚡ Power nap")
  async def power_nap_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)

    if has_enough_user_data(user):
      recommendation = services.generate_day_recovery(
        user,
        choice="power_nap",
        free_minutes=None,
        reminder_enabled=True,
      )
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
    user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)

    if has_enough_user_data(user):
      recommendation = services.generate_day_recovery(
        user,
        choice="meditation",
        free_minutes=None,
        reminder_enabled=True,
      )
      await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())
      return

    await state.set_state(DayRecoveryFlow.free_minutes)
    await state.update_data(choice="meditation")
    await message.answer(
      "Сколько минут можешь выделить на медитацию или восстановительный перерыв?",
      reply_markup=meditation_keyboard(),
    )

  @router.message(DayRecoveryFlow.free_minutes)
  async def day_recovery_minutes(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    choice = data.get("choice")
    value = _parse_int(message.text, 1, 120)

    if value is None:
      await message.answer("Введи число минут.", reply_markup=cancel_keyboard())
      return

    if choice == "power_nap" and value < 10:
      await message.answer(
        "Для power nap нужно хотя бы 10 минут.\n\n"
        "Выбери 10, 15 или 20. Если времени меньше, лучше нажми «🧘 Медитация» и сделай короткий recovery break.",
        reply_markup=power_nap_keyboard(),
      )
      return

    if choice == "power_nap" and value > 20:
      await message.answer(
        "Power nap лучше держать в диапазоне 10-20 минут.\n\n"
        "Выбери 10, 15 или 20. Если есть больше времени, лучше используй «🧘 Медитация» или дневной перерыв.",
        reply_markup=power_nap_keyboard(),
      )
      return

    if choice == "meditation" and not 5 <= value <= 60:
      await message.answer("Для этого сценария выбери время от 5 до 60 минут.", reply_markup=meditation_keyboard())
      return

    user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
    recommendation = services.generate_day_recovery(
      user,
      choice=choice,
      free_minutes=value,
      reminder_enabled=True,
    )

    await state.clear()
    await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())

  @router.message(F.text == "💤 Быстро заснуть")
  async def quick_sleep_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)

    if has_enough_user_data(user):
      recommendation = services.generate_sleep_or_wake_technique(
        user,
        kind="quick_sleep",
        quality=None,
        wake_feeling=None,
      )
      await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())
      return

    await state.set_state(TechniqueFlow.quality)
    await state.update_data(kind="quick_sleep")
    await message.answer("Как оцениваешь последнее качество сна 1-5?", reply_markup=scale_keyboard())

  @router.message(F.text == "🌅 Хорошее пробуждение")
  async def good_wake_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)

    if has_enough_user_data(user):
      recommendation = services.generate_sleep_or_wake_technique(
        user,
        kind="good_wake",
        quality=None,
        wake_feeling=None,
      )
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

    user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
    recommendation = services.generate_sleep_or_wake_technique(
      user,
      kind="quick_sleep",
      quality=value,
      wake_feeling=None,
    )

    await state.clear()
    await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())

  @router.message(TechniqueFlow.wake_feeling)
  async def good_wake_feeling(message: Message, state: FSMContext) -> None:
    value = _parse_int(message.text, 1, 5)
    if value is None:
      await message.answer("Выбери число от 1 до 5.", reply_markup=scale_keyboard())
      return

    user = services.store.upsert_user(message.from_user.id, message.from_user.username if message.from_user else None)
    recommendation = services.generate_sleep_or_wake_technique(
      user,
      kind="good_wake",
      quality=None,
      wake_feeling=value,
    )

    await state.clear()
    await message.answer(recommendation_text(recommendation), reply_markup=menu_keyboard())

  @router.message(F.text == "🌙 Заснуть ночью")
  async def night_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(NightFlow.slept)
    await message.answer("Сколько минут примерно спал прошлой ночью? Например: 420", reply_markup=cancel_keyboard())

  @router.message(NightFlow.slept)
  async def night_slept(message: Message, state: FSMContext) -> None:
    value = _parse_int(message.text, 0, 1440)
    if value is None:
      await message.answer("Введи число минут от 0 до 1440.", reply_markup=cancel_keyboard())
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

  @router.message()
  async def fallback(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state:
      await message.answer(
        "Я сейчас жду ответ по текущему сценарию. Можно продолжить или нажать «В меню».",
        reply_markup=cancel_keyboard(),
      )
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
    value = int((text or "").strip())
  except ValueError:
    return None

  if min_value <= value <= max_value:
    return value

  return None


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