from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib import request


MOCK_TOKEN = "local-mock-token"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Sleep Support Bot locally without Docker")
    parser.add_argument("--host", default=os.getenv("LOCAL_SERVER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("LOCAL_SERVER_PORT", os.getenv("PORT", "8000"))))
    parser.add_argument("--db", default=os.getenv("LOCAL_DB_PATH", "local_data/sleep_support.sqlite3"))
    parser.add_argument("--no-telegram", action="store_true", help="do not start Telegram polling even if TELEGRAM_BOT_TOKEN is set")
    parser.add_argument("--no-worker", action="store_true", help="disable local alarm worker")
    return parser.parse_args()


def is_real_token(token: str | None) -> bool:
    return bool(token and token.strip() and token.strip() != MOCK_TOKEN)


def send_telegram_message(token: str, chat_id: int, text: str) -> None:
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    api_request = request.Request(
        url=f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(api_request, timeout=10) as response:
        response.read()


async def alarm_worker_loop(telegram_token: str | None = None) -> None:
    from packages.services.facade import services

    while True:
        claimed = services.alarms.claim_due(datetime.now(timezone.utc), limit=50)
        for alarm in claimed:
            user = services.store.users_by_id.get(alarm.user_id)
            text = (
                "⏰ Будильник\n\n"
                "Пора мягко проснуться. Сядь, сделай пару спокойных вдохов и выпей воды.\n\n"
                f"Код отключения: {alarm.dismiss_code}\n"
                "После подъема нажми в боте кнопку ✅ Я проснулся."
            )
            if telegram_token and user is not None:
                try:
                    await asyncio.to_thread(send_telegram_message, telegram_token, user.telegram_id, text)
                    print(f"[alarm] sent to telegram_id={user.telegram_id} alarm_id={alarm.id}", flush=True)
                except Exception as exc:
                    print(f"[alarm] telegram send failed alarm_id={alarm.id}: {exc}", flush=True)
            else:
                print(
                    f"[alarm] user_id={alarm.user_id} alarm_id={alarm.id} "
                    f"intensity={alarm.wake_intensity.value} dismiss_code={alarm.dismiss_code}",
                    flush=True,
                )
            services.alarms.mark_failed_or_repeat(alarm.id, datetime.now(timezone.utc))
        await asyncio.sleep(1)


def start_worker_thread(telegram_token: str | None = None) -> threading.Thread:
    def runner() -> None:
        asyncio.run(alarm_worker_loop(telegram_token))

    thread = threading.Thread(target=runner, name="local-alarm-worker", daemon=True)
    thread.start()
    return thread


def start_telegram_thread() -> threading.Thread:
    def runner() -> None:
        try:
            from apps.bot.app.main import run_aiogram_bot

            asyncio.run(run_aiogram_bot())
        except Exception as exc:
            print(f"[telegram] polling stopped: {exc}", flush=True)

    thread = threading.Thread(target=runner, name="telegram-polling", daemon=True)
    thread.start()
    return thread


def print_startup(host: str, port: int, db_path: str, telegram_enabled: bool, worker_enabled: bool,
    admin_token_is_default: bool,
) -> None:
    print("\nSleep Support Bot запущен локально")
    print(f"API:       http://{host}:{port}")
    print(f"Docs:      http://{host}:{port}/docs")
    print(f"Health:    http://{host}:{port}/health")
    print(f"SQLite DB: {Path(db_path).resolve()}")
    print(f"Telegram:  {'polling запущен' if telegram_enabled else 'не запущен - TELEGRAM_BOT_TOKEN не задан'}")
    print(f"Worker:    {'alarm worker запущен' if worker_enabled else 'alarm worker выключен'}")
    if admin_token_is_default:
        print("Admin token: используется значение по умолчанию - замени ADMIN_TOKEN в Railway Variables")
    else:
        print("Admin token: задан через переменные окружения")
    print("Остановить: Ctrl+C\n")

def main() -> None:
    args = parse_args()
    os.environ.setdefault("APP_ENV", "local")
    os.environ["LOCAL_DB_PATH"] = args.db
    os.environ["LOCAL_SERVER_HOST"] = args.host
    os.environ["LOCAL_SERVER_PORT"] = str(args.port)

    try:
        import uvicorn
        from packages.core.config import get_settings
    except ImportError:
        print("Не найдены зависимости. Установи их командой: python -m pip install -r requirements-local.txt")
        sys.exit(1)

    settings = get_settings()
    token = settings.telegram_bot_token
    telegram_enabled = is_real_token(token) and not args.no_telegram
    if telegram_enabled:
        os.environ["BOT_MODE"] = "polling"
    else:
        os.environ.setdefault("BOT_MODE", "local")

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    if not args.no_worker:
        start_worker_thread(token if telegram_enabled else None)
    if telegram_enabled:
        start_telegram_thread()

    print_startup(
    args.host,
    args.port,
    args.db,
    telegram_enabled=telegram_enabled,
    worker_enabled=not args.no_worker,
    admin_token_is_default=settings.admin_token == "change-me-local-admin-token",
    )
    uvicorn.run("apps.api.app.main:app", host=args.host, port=args.port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
