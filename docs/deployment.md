# Deployment

## Local-first deployment

Основной режим проекта - локальный запуск без Docker:

```bash
python main.py
```

Сервер поднимается на `127.0.0.1:8000`, база создается в `local_data/sleep_support.sqlite3`.

## Local production-like demo

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-local.txt
python main.py --host 127.0.0.1 --port 8000 --db local_data/sleep_support.sqlite3
```

## Environment

```text
LOCAL_DB_PATH=local_data/sleep_support.sqlite3
LOCAL_SERVER_HOST=127.0.0.1
LOCAL_SERVER_PORT=8000
ADMIN_TOKEN=change-me-local-admin-token
TELEGRAM_BOT_TOKEN=local-mock-token
BOT_MODE=local
```

## Data backup

Для локального проекта достаточно копировать файл SQLite:

```bash
cp local_data/sleep_support.sqlite3 backups/sleep_support_$(date +%F).sqlite3
```

## Future production

Для реального публичного запуска стоит заменить SQLite на PostgreSQL repository layer, подключить полноценную admin auth, real billing provider, backup policy и monitoring.
