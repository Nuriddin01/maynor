# Sleep Support Bot

Локальный Telegram-first продукт для поддержки сна: вечерний сценарий засыпания, power nap, дневной перерыв, check-in после сна, история, статистика, будильники, premium-логика и admin API.

Проект теперь рассчитан на простой запуск без Docker:

```bash
python main.py
```

После запуска открой:

- API: http://127.0.0.1:8000
- Swagger/OpenAPI: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

Локальные данные сохраняются в SQLite-файл:

```text
local_data/sleep_support.sqlite3
```

Файл создаётся автоматически при первом запуске.

## Быстрый старт

### 1. Создать виртуальное окружение

```bash
python -m venv .venv
source .venv/bin/activate
```

На Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 2. Установить зависимости

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-local.txt
```

### 3. Запустить локальный сервер

```bash
python main.py
```

Можно указать другой порт или путь к базе:

```bash
python main.py --port 8080 --db local_data/demo.sqlite3
```

## Что запускается через `python main.py`

- локальный FastAPI сервер
- SQLite-хранилище
- фоновой alarm worker внутри этого же процесса
- автоматическое создание таблиц БД
- admin API
- mock billing provider
- product analytics storage
- Telegram polling, если задан `TELEGRAM_BOT_TOKEN`

После этого достаточно одной команды:

```bash
python main.py
```

Локальный sandbox бота без Telegram:

```bash
BOT_MODE=local python -m apps.bot.app.main
```

## Основные локальные команды

```bash
make run        # python main.py
make test       # pytest -q
make compile    # проверка импортов/синтаксиса
make seed       # вывести seed-контент
make clean-data # удалить local_data
```

## Проверка API вручную

Создать пользователя:

```bash
curl -X POST http://127.0.0.1:8000/users/start \
  -H "Content-Type: application/json" \
  -d '{"telegram_id": 100, "username": "demo"}'
```

Принять обязательные согласия:

```bash
curl -X POST http://127.0.0.1:8000/users/100/consents/accept-required
```

Получить рекомендацию:

```bash
curl -X POST http://127.0.0.1:8000/recommendations/night \
  -H "Content-Type: application/json" \
  -d '{
    "telegram_id": 100,
    "slept_last_night_minutes": 390,
    "quality": 3,
    "sleepiness": 4,
    "stress": 5,
    "free_minutes": 15,
    "needs_alarm": false,
    "preferred_audio": "rain"
  }'
```

Поставить power nap будильник:

```bash
curl -X POST http://127.0.0.1:8000/alarms \
  -H "Content-Type: application/json" \
  -d '{"telegram_id": 100, "minutes": 15, "idempotency_key": "alarm-100-1"}'
```

Посмотреть пользователей через admin API:

```bash
curl http://127.0.0.1:8000/admin/users \
  -H "X-Admin-Token: change-me-local-admin-token"
```

## Где хранятся данные

В SQLite сохраняются:

- users
- user preferences
- consents
- sleep entries
- recommendations
- alarms
- analytics events
- payment intents
- subscriptions
- audit logs

Экспорт данных пользователя доступен через:

```http
GET /admin/users/{user_id}/export
```

Удаление данных:

```http
DELETE /admin/users/{user_id}
```

Оба endpoint требуют заголовок:

```http
X-Admin-Token: change-me-local-admin-token
```

## Premium и платежи

В локальном режиме используется mock billing provider. Он создаёт payment intent и затем подтверждается локальным endpoint:

```bash
curl -X POST http://127.0.0.1:8000/billing/checkout \
  -H "Content-Type: application/json" \
  -d '{"telegram_id": 100, "plan_code": "premium_monthly", "idempotency_key": "pay-100-1"}'

curl -X POST http://127.0.0.1:8000/billing/mock/confirm/pay-100-1
```

Архитектура billing-provider оставлена расширяемой: mock provider можно заменить на Telegram Stars/invoices или другой provider.

## Privacy и безопасность

Проект не является медицинским продуктом и не ставит диагнозы. В текстах используется мягкий дисклеймер:

> Бот не заменяет врача. Если проблемы со сном стали постоянными или сильно мешают жизни, обратитесь к специалисту.

Реализовано:

- отдельные core/privacy/marketing consent
- хранение consent version
- export my data
- delete my data
- admin token boundary
- audit log для удаления
- data minimization в локальной схеме
- mock платежи без реальных карт и боевых ключей

Перед реальным публичным запуском нужно заменить admin auth, проверить legal docs с юристом и подключить настоящий payment provider.

## Структура

```text
sleep_support_platform/
  main.py
  apps/
    api/
    bot/
    worker/
  packages/
    analytics/
    billing/
    content/
    core/
    domain/
    services/
  docs/
  tests/
  scripts/
  requirements-local.txt
  .env.example
  Makefile
```

## Проверки

Локально были запущены:

```bash
python -m compileall apps packages tests main.py
pytest -q
python main.py --host 127.0.0.1 --port 8765 --db /tmp/sleep_local_test/sleep.sqlite3
python scripts/seed.py
```

Результат проверки на момент сборки архива:

```text
16 passed
compileall passed
local server /health returned 200 OK
SQLite persistence after restart verified
seed script passed
```

## Ограничения

- Реальный Telegram polling требует `TELEGRAM_BOT_TOKEN`
- Реальные платежи требуют production billing provider и webhook verification
- SQLite подходит для локального запуска, демо и учебного проекта. Для большой нагрузки лучше подключить PostgreSQL-репозиторий
- `ruff` и `mypy` запускаются только если установлены dev-зависимости

## Реализация user stories

В версии `1.1.0` добавлены сценарии из трёх user stories.

### 1. Рассчитать отбой

Telegram-кнопка:

```text
🛏 Рассчитать отбой
```

API:

```http
PUT /users/{telegram_id}/profile
POST /planning/bedtime
GET /users/{telegram_id}/history
```

Пример:

```bash
curl -X PUT http://127.0.0.1:8000/users/100/profile \
  -H "Content-Type: application/json" \
  -d '{"wake_time":"07:30","timezone":"UTC","target_sleep_minutes":480,"default_nap_duration":15}'

curl -X POST http://127.0.0.1:8000/planning/bedtime \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":100,"reminder_enabled":true}'
```

Бот считает долг сна, рекомендуемое время отбоя, оптимальную длительность сна на сегодня и сохраняет результат в историю. Если данных мало, использует базовый ориентир и прямо сообщает об этом.

### 2. Power nap / медитация

Telegram-кнопки:

```text
⚡ Power nap
🧘 Медитация
```

API:

```http
POST /recommendations/day-recovery
```

Пример:

```bash
curl -X POST http://127.0.0.1:8000/recommendations/day-recovery \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":100,"choice":"meditation","free_minutes":12,"reminder_enabled":true}'
```

Если есть профиль и история сна, бот учитывает долг сна. Если данных мало, Telegram-flow спрашивает, сколько минут пользователь может выделить.

### 3. Быстро заснуть / хорошее пробуждение

Telegram-кнопки:

```text
💤 Быстро заснуть
🌅 Хорошее пробуждение
```

API:

```http
POST /recommendations/sleep-technique
POST /recommendations/feedback
```

Пример:

```bash
curl -X POST http://127.0.0.1:8000/recommendations/sleep-technique \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":100,"kind":"good_wake","wake_feeling":3}'
```

Бот выбирает технику по длительности сна, качеству сна и времени подъёма. Если данных мало, спрашивает самооценку. После выполнения можно сохранить оценку полезности рекомендации.

Подробная таблица соответствия лежит в:

```text
docs/product/user_stories_compliance.md
```

## Запуск настоящего Telegram-бота

Подробная инструкция лежит в `docs/TELEGRAM_RUN.md`. Коротко:

```bash
cp .env.example .env
# вставь TELEGRAM_BOT_TOKEN в .env
python main.py
```

В консоли должно появиться:

```text
Telegram:  polling запущен
```

Если написано `Telegram: не запущен`, значит токен не прочитан из `.env` или переменных окружения.

## Запуск на сервере без Docker

Команда запуска:

```bash
python main.py --host 0.0.0.0
```

Если платформа задает переменную `PORT`, приложение подхватит ее автоматически. В проект добавлен `Procfile`:

```text
web: python main.py --host 0.0.0.0
```

Для SQLite на сервере нужен persistent disk/volume, иначе база может пропасть после redeploy.
