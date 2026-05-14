# Real Telegram bot run

## 1. Получить токен

1. Открой Telegram
2. Найди `@BotFather`
3. Выполни `/newbot`
4. Скопируй токен вида `123456789:AA...`

Токен нельзя коммитить в GitHub и нельзя отправлять в чат.

## 2. Локальный запуск

Создай файл `.env` в корне проекта:

```env
APP_ENV=local
LOCAL_DB_PATH=local_data/sleep_support.sqlite3
LOCAL_SERVER_HOST=127.0.0.1
LOCAL_SERVER_PORT=8000
TELEGRAM_BOT_TOKEN=PASTE_REAL_TOKEN_HERE
ADMIN_TOKEN=change-me-local-admin-token
BILLING_PROVIDER=mock
LOG_LEVEL=INFO
METRICS_ENABLED=true
CONTENT_PATH=content
ENCRYPTION_KEY=local-development-key-change-me
```

Установи зависимости и запусти:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-local.txt
python main.py
```

После запуска работают сразу три части:

- FastAPI server: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- Telegram polling через `TELEGRAM_BOT_TOKEN`

Если токен не указан, Telegram polling не запускается, но API и локальная база работают.

## 3. Запуск на сервере

Для PaaS/VPS достаточно команды:

```bash
python main.py --host 0.0.0.0
```

Если платформа сама выдает переменную `PORT`, `main.py` автоматически ее подхватит.

Обязательные env vars на сервере:

```env
TELEGRAM_BOT_TOKEN=real_token_from_botfather
LOCAL_DB_PATH=local_data/sleep_support.sqlite3
ADMIN_TOKEN=replace_with_long_random_secret
ENCRYPTION_KEY=replace_with_long_random_secret
```

Для постоянного хранения SQLite нужен persistent disk/volume. Без persistent disk база может пропасть после redeploy.
