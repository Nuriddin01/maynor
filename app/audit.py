from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from app.security import redact_payload


class AuditService:
    async def track_event(self, session: AsyncSession, event_name: str, user_id: int | None = None, details: dict | None = None) -> None:
        event = AuditLog(user_id=user_id, event_name=event_name, details_json=redact_payload(details or {}))
        session.add(event)
        await session.commit()
