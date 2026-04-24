# Sleep Support Bot

Sleep Support Bot - это production-ready MVP+ Telegram-бот для поддержки сна и коротких восстановительных сессий. Он помогает пользователю подготовиться ко сну, сделать дневную паузу, пройти сценарий power nap, сохранить утренний чек-ин, посмотреть историю, увидеть простую аналитику и управлять будильниками прямо в Telegram.

Бот сделан честно и безопасно:

- не ставит медицинские диагнозы
- не обещает вылечить бессонницу
- не использует псевдонауку
- использует мягкие и прозрачные эвристики вместо непрозрачных рекомендаций
- в важных местах показывает дисклеймер:
  `Бот не заменяет врача. Если проблемы со сном стали постоянными или сильно мешают жизни, лучше обратиться к специалисту.`

## Возможности

- Вечерний сценарий подготовки ко сну с адаптивными режимами:
  - `ultra_short_wind_down`
  - `short_wind_down`
  - `standard_wind_down`
  - `calm_night_protocol`
- Дневной отдых:
  - `recovery_break`
  - `short_day_rest`
  - `guided_nap_attempt`
  - `long_rest_session`
- Отдельный сценарий `Power Nap 10-20 min`
- Утренний чек-ин после сна
- История сна
- Статистика за последние 7 дней
- Telegram-будильник:
  - установка по относительному или точному времени
  - случайный код для отключения
  - ограниченное количество повторных напоминаний
  - восстановление после перезапуска бота
- Настройки:
  - часовой пояс
  - язык профиля
  - предпочитаемое аудио
  - переключатель неприязни к белому шуму
  - формат времени
  - включение и отключение рекомендаций
- Экран Premium с feature flags и заглушками
- Поддержка Docker
- Unit-тесты

## Стек

- Python 3.12+
- aiogram 3
- SQLite
- SQLAlchemy 2.0 async
- APScheduler
- pydantic / pydantic-settings
- python-dotenv
- pytest / pytest-asyncio
- Docker / docker compose

## Структура проекта

```text
sleep_support_bot/
  app/
    config.py
    db.py
    models.py
    schemas.py
    scheduler.py
    recommendation_engine.py
    constants.py
    utils/
    services/
  bot/
    handlers/
    keyboards/
    states/
    texts/
    middlewares/
  tests/
  .env.example
  Dockerfile
  docker-compose.yml
  README.md
  main.py
````

## Как работает логика рекомендаций

Рекомендательная логика находится в файле `app/recommendation_engine.py` и построена как явная эвристическая система.

Она учитывает:

* тип запроса
* сколько пользователь спал прошлой ночью
* субъективное качество сна
* текущую сонливость
* текущий уровень стресса
* доступное свободное время
* историю за последние 7 дней
* аудиопредпочтения
* неприязнь к белому шуму
* желаемый режим дневного отдыха

Логика настраивается через файл `app/constants.py`.

## Локальный запуск

### 1. Создать файл окружения

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Затем нужно указать реальный токен бота в `.env`.

### 2. Создать виртуальное окружение

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Запустить бота

```bash
python main.py
```

SQLite-база будет создана в папке `./data/`.

## Запуск через Docker

### 1. Подготовить `.env`

```bash
cp .env.example .env
```

### 2. Запустить проект

```bash
docker compose up --build
```

Контейнер бота подключает папку `./data` для постоянного хранения SQLite-базы.

## Тесты

Запуск всех тестов:

```bash
pytest
```

## Переменные окружения

Пример `.env`:

```env
SSB_TELEGRAM_BOT_TOKEN=123456:replace_me
SSB_DATABASE_URL=sqlite+aiosqlite:///./data/sleep_support_bot.db
SSB_APP_TIMEZONE=Europe/Moscow
SSB_LOG_LEVEL=INFO
SSB_ALARM_REPEAT_INTERVAL_SECONDS=60
SSB_MAX_ALARM_REPEAT_ATTEMPTS=3
SSB_ALARM_CODE_LENGTH=4
SSB_DEFAULT_LANGUAGE=ru
SSB_DEFAULT_TIME_FORMAT=24h
```

## Замечания о безопасности

* Бот не является медицинским устройством.
* Он не ставит диагнозы и не назначает лечение.
* Рекомендации подаются как мягкая поддержка, а не как медицинские указания.
* Повторяющийся дисклеймер намеренно встроен в продуктовый текст.

## Идеи для расширения

* еженедельные запланированные инсайты
* планирование сна с учетом календаря и дедлайнов
* более глубокая персонализация с большим весом истории
* расширенный мультиязычный интерфейс
* структурированный onboarding и трекинг привычек

```
```
