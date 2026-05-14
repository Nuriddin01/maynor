from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from packages.core.config import get_settings
from packages.core.logging import configure_logging
from packages.services.facade import services

logger = logging.getLogger(__name__)


async def alarm_worker_loop(poll_interval_seconds: float = 1.0) -> None:
    while True:
        claimed = services.alarms.claim_due(datetime.now(timezone.utc), limit=50)
        for alarm in claimed:
            logger.info("alarm firing user_id=%s alarm_id=%s intensity=%s", alarm.user_id, alarm.id, alarm.wake_intensity.value)
            services.alarms.mark_failed_or_repeat(alarm.id, datetime.now(timezone.utc))
        await asyncio.sleep(poll_interval_seconds)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    await alarm_worker_loop()


if __name__ == "__main__":
    asyncio.run(main())
