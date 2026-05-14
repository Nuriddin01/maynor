from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from packages.domain.models import ConsentType


@dataclass(frozen=True)
class ConsentVersion:
    type: ConsentType
    version: str
    required: bool
    text_hash: str
    active_from: datetime


@dataclass(frozen=True)
class UserConsent:
    user_id: UUID
    type: ConsentType
    version: str
    accepted: bool
    accepted_at: datetime | None
    revoked_at: datetime | None = None


class ConsentService:
    def __init__(self, versions: tuple[ConsentVersion, ...]) -> None:
        self._versions = versions

    def active_versions(self) -> tuple[ConsentVersion, ...]:
        return self._versions

    def can_use_core_product(self, consents: tuple[UserConsent, ...]) -> bool:
        accepted = {(item.type, item.version) for item in consents if item.accepted and item.revoked_at is None}
        for version in self._versions:
            if version.required and (version.type, version.version) not in accepted:
                return False
        return True

    def can_send_marketing(self, consents: tuple[UserConsent, ...]) -> bool:
        return any(
            item.type == ConsentType.MARKETING and item.accepted and item.revoked_at is None
            for item in consents
        )
