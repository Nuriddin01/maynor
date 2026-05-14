from __future__ import annotations

from datetime import datetime, timezone

from packages.domain.consent import ConsentService, ConsentVersion, UserConsent
from packages.domain.models import ConsentType, new_uuid


def test_core_usage_requires_required_consents() -> None:
    user_id = new_uuid()
    versions = (
        ConsentVersion(ConsentType.CORE, "v1", True, "hash", datetime.now(timezone.utc)),
        ConsentVersion(ConsentType.PRIVACY, "v1", True, "hash", datetime.now(timezone.utc)),
        ConsentVersion(ConsentType.MARKETING, "v1", False, "hash", datetime.now(timezone.utc)),
    )
    service = ConsentService(versions)

    assert service.can_use_core_product(()) is False
    assert service.can_use_core_product(
        (
            UserConsent(user_id, ConsentType.CORE, "v1", True, datetime.now(timezone.utc)),
            UserConsent(user_id, ConsentType.PRIVACY, "v1", True, datetime.now(timezone.utc)),
        )
    ) is True
