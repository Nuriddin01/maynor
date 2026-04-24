# Sleep Support Bot

Sleep Support Bot is a production-ready MVP+ Telegram bot for sleep support and short recovery sessions. It helps users prepare for night sleep, take a daytime break, run a power nap flow, save wake check-ins, review history, see lightweight analytics, and manage alarms directly inside Telegram.

The bot is intentionally honest and safe:

- no medical diagnoses
- no claims about curing insomnia
- no pseudo-science
- soft, transparent heuristics instead of black-box recommendations
- a repeated disclaimer where it matters:
  `Бот не заменяет врача. Если проблемы со сном стали постоянными или сильно мешают жизни, лучше обратиться к специалисту.`

## Features

- Night sleep wind-down flow with adaptive scenarios:
  - `ultra_short_wind_down`
  - `short_wind_down`
  - `standard_wind_down`
  - `calm_night_protocol`
- Day rest flow with:
  - `recovery_break`
  - `short_day_rest`
  - `guided_nap_attempt`
  - `long_rest_session`
- Dedicated `Power Nap 10-20 min` flow
- Wake check-in after sleep
- Sleep history
- Stats for the last 7 days
- Telegram alarm with:
  - relative or exact-time scheduling
  - random stop code
  - limited repeated reminders
  - restoration after bot restart
- Settings:
  - timezone
  - profile language
  - preferred audio
  - white noise dislike toggle
  - time format
  - recommendation toggles
- Premium screen with feature flags and stubs
- Docker support
- Unit tests

## Stack

- Python 3.12+
- aiogram 3
- SQLite
- SQLAlchemy 2.0 async
- APScheduler
- pydantic / pydantic-settings
- python-dotenv
- pytest / pytest-asyncio
- Docker / docker compose

## Project Structure

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
```

## How Recommendation Logic Works

The recommendation engine is an explicit heuristic system located in `app/recommendation_engine.py`.

It takes into account:

- request type
- how long the user slept last night
- subjective sleep quality
- current sleepiness
- current stress
- free time available
- last 7 days of history
- audio preferences
- white noise dislike
- preferred mode intent for day rest

The logic is configurable through `app/constants.py`.

## Local Run

### 1. Create environment file

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then set a real bot token in `.env`.

### 2. Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the bot

```bash
python main.py
```

The SQLite database will be created under `./data/`.

## Run With Docker

### 1. Prepare `.env`

```bash
cp .env.example .env
```

### 2. Start the project

```bash
docker compose up --build
```

The bot container mounts `./data` for persistent SQLite storage.

## Tests

Run all tests:

```bash
pytest
```

## Environment Variables

Example `.env`:

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

## Notes About Safety

- The bot is not a medical device.
- It does not diagnose or prescribe treatment.
- Recommendations are framed as gentle support, not medical guidance.
- The recurring disclaimer is part of product copy on purpose.

## Extension Ideas

- weekly scheduled insights
- calendar and deadline-aware sleep planning
- deeper personalization with more historical weighting
- richer multilingual UI
- structured onboarding and habit tracking
