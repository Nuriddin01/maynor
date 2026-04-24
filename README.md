# Sleep Support Bot

Production-ready MVP+ Telegram wellbeing-бот для поддержки сна и коротких восстановительных сессий.

> Бот не заменяет врача. Если проблемы со сном стали постоянными или сильно мешают жизни, лучше обратиться к специалисту.

## Функции MVP
- Night flow (ultra/short/standard/calm protocol)
- Day flow (recovery break, short rest, guided nap, long rest)
- Отдельный Power Nap 10/15/20
- Wake check-in и история
- Статистика 7/30 дней и insights
- Будильник в Telegram с кодом отключения `/stop_alarm CODE`
- Настройки (timezone, language, audio, white-noise dislike, default nap, reminders, time format)
- Premium-заготовка (feature flags)

## Стек
Python 3.12+, aiogram 3, SQLAlchemy async + SQLite, APScheduler, pydantic-settings, pytest, Docker.

## Запуск локально
```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Запуск через Docker
```bash
cp .env.example .env
docker compose up --build
```

## Тесты
```bash
PYTHONPATH=. pytest -q
```

## Документация
См. `docs/*`: Lean Canvas, BMC, Use Cases, User Stories, Story Map, Acceptance Criteria, CJM, privacy policy, public offer, security model, unit economics, monetization, metrics, marketing, presentation outline.

## Ограничения MVP
- Нет оплаты premium в runtime.
- SQLite подходит для MVP, для production требуется managed DB + backups + encryption-at-rest.
- Нет медицинских назначений, только wellbeing support.

## Roadmap
- v2: weekly insights, richer content templates, better reminder intelligence.
- v3: adaptive personalization, subscription billing, cohort-level experimentation.
