# Architecture

## Components

- `apps/bot` - Telegram bot adapter and local sandbox bot
- `apps/api` - FastAPI backend/admin API
- `apps/worker` - alarm/background worker
- `packages/domain` - pure domain logic: recommendations, alarms, stats, consent
- `packages/services` - application service facade
- `packages/billing` - plans, provider abstraction, mock provider
- `packages/content` - seed content and content registry
- `packages/analytics` - analytics events and summaries
- `packages/persistence` - SQLAlchemy model definitions
- `migrations` - Alembic migrations

## Boundaries

Domain modules do not depend on FastAPI, aiogram or database libraries. This keeps recommendation logic, billing lifecycle, alarms and stats testable.

## Alarm reliability

Alarms are persisted with:

- `status`
- `due_at`
- `idempotency_key`
- `repeats_done`
- `max_repeats`

The worker claims due alarms by changing status from `scheduled` to `firing`, preventing repeated processing. Production DB repository should use row-level locking with `FOR UPDATE SKIP LOCKED`.

## Billing

The billing provider boundary supports local mock checkout and production providers. Telegram Stars can be implemented behind the same interface.

## Security

Admin API is separated from Telegram bot user flow. Static token is acceptable only for local/dev; production should use stronger auth, admin users, password hashing and optional SSO.
