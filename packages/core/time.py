from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception as exc:
        raise ValueError("invalid timezone") from exc


def to_user_time(moment: datetime, timezone_name: str) -> datetime:
    return moment.astimezone(parse_timezone(timezone_name))
