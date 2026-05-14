# Repository audit and implementation plan

## Audit

The workspace did not contain an existing application repository. Source materials were course/project files about electronic business, mobile UX, business models, privacy/security, legal offer, marketing, unit economics and backlog prioritization.

## Implementation plan

1. Create monorepo with app/domain/integration separation.
2. Implement pure domain logic first: recommendations, alarms, consent, stats, billing lifecycle.
3. Add FastAPI admin/backend API.
4. Add Telegram bot adapter and local bot sandbox.
5. Add PostgreSQL schema and Alembic migration.
6. Add analytics events and KPI summary basis.
7. Add legal, product, architecture and business docs.
8. Add tests and local verification commands.
9. Package project for handoff.

## Target architecture

- Bot and API are separate apps.
- Domain logic is framework-independent.
- Billing, content and analytics have explicit service boundaries.
- Alarms are persisted and idempotent by design.
- Privacy/consent is enforced before recommendation generation.
