from __future__ import annotations

BUTTONS = {
    "bedtime": "🛏 Рассчитать отбой",
    "night": "🌙 Заснуть ночью",
    "day_rest": "☀️ Дневной сон / перерыв",
    "meditation": "🧘 Медитация",
    "quick_sleep": "💤 Быстро заснуть",
    "good_wake": "🌅 Хорошее пробуждение",
    "power_nap": "⚡ Power nap",
    "wake": "✅ Я проснулся",
    "history": "📜 История",
    "stats": "📊 Статистика",
    "alarm": "⏰ Будильник",
    "settings": "⚙️ Настройки",
    "premium": "⭐ Premium",
    "help": "Помощь",
    "back": "Назад",
    "skip": "Пропустить",
    "menu": "В меню",
    "cancel": "Отменить сценарий",
}


def numeric_buttons(min_value: int, max_value: int) -> list[str]:
    return [str(value) for value in range(min_value, max_value + 1)]
