# Local run without Docker

Запуск проекта сделан максимально простым:

```bash
python main.py
```

По умолчанию сервер поднимается на `127.0.0.1:8000`, а данные пишутся в `local_data/sleep_support.sqlite3`.

## Настройки

Если нужен настоящий Telegram-бот, добавь токен в `.env`:

```env
TELEGRAM_BOT_TOKEN=123456789:AA...
```

После этого `python main.py` сам запустит polling. Если токена нет, будет работать только локальный API и SQLite.

Можно использовать аргументы:

```bash
python main.py --host 127.0.0.1 --port 8080 --db local_data/demo.sqlite3
```

Или переменные окружения:

```bash
LOCAL_SERVER_HOST=127.0.0.1
LOCAL_SERVER_PORT=8000
LOCAL_DB_PATH=local_data/sleep_support.sqlite3
```

## Что сохраняется в SQLite

- пользователи
- согласия
- sleep check-ins
- рекомендации
- будильники
- analytics events
- платежные намерения
- подписки
- audit logs

## Почему SQLite

Для учебной защиты и локальной демонстрации SQLite удобнее Docker/PostgreSQL:

- не нужен Docker Desktop
- нет сетевых сервисов
- база лежит одним файлом
- легко показать, что данные сохраняются после перезапуска
- можно перенести проект архивом

Для настоящего production можно заменить local repositories на PostgreSQL repositories, не меняя domain-логику.

## Новые сценарии из User Stories

### Рассчитать отбой

```bash
curl -X PUT http://127.0.0.1:8000/users/100/profile \
  -H "Content-Type: application/json" \
  -d '{"wake_time":"07:30","timezone":"UTC","target_sleep_minutes":480,"default_nap_duration":15}'

curl -X POST http://127.0.0.1:8000/planning/bedtime \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":100,"reminder_enabled":true}'
```

### Power nap / медитация

```bash
curl -X POST http://127.0.0.1:8000/recommendations/day-recovery \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":100,"choice":"power_nap","free_minutes":15,"reminder_enabled":true}'

curl -X POST http://127.0.0.1:8000/recommendations/day-recovery \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":100,"choice":"meditation","free_minutes":10,"reminder_enabled":true}'
```

### Быстро заснуть / хорошее пробуждение

```bash
curl -X POST http://127.0.0.1:8000/recommendations/sleep-technique \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":100,"kind":"quick_sleep","quality":3}'

curl -X POST http://127.0.0.1:8000/recommendations/sleep-technique \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":100,"kind":"good_wake","wake_feeling":3}'
```

### Оценка полезности рекомендации

```bash
curl -X POST http://127.0.0.1:8000/recommendations/feedback \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":100,"recommendation_id":"<uuid>","helpfulness":5,"note":"помогло"}'
```
