from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_timezone(timezone_name: str | None) -> ZoneInfo:
    if not timezone_name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def parse_hhmm(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError("Ожидался формат HH:MM.")

    hours = int(parts[0])
    minutes = int(parts[1])
    if not 0 <= hours <= 23 or not 0 <= minutes <= 59:
        raise ValueError("Время должно быть в диапазоне 00:00-23:59.")
    return time(hour=hours, minute=minutes)


def local_clock_to_utc(time_string: str, timezone_name: str) -> datetime:
    parsed_time = parse_hhmm(time_string)
    user_tz = get_timezone(timezone_name)
    now_local = utc_now().astimezone(user_tz)
    candidate = datetime.combine(now_local.date(), parsed_time, tzinfo=user_tz)
    if candidate <= now_local:
        candidate = candidate + timedelta(days=1)
    return candidate.astimezone(timezone.utc)


def minutes_from_now_to_utc(minutes: int) -> datetime:
    return utc_now() + timedelta(minutes=minutes)


def to_user_timezone(dt: datetime, timezone_name: str) -> datetime:
    return dt.astimezone(get_timezone(timezone_name))


def format_datetime_for_user(dt: datetime, timezone_name: str, time_format: str = "24h") -> str:
    localized = to_user_timezone(dt, timezone_name)
    format_string = "%I:%M %p" if time_format == "12h" else "%H:%M"
    return localized.strftime(f"%d.%m.%Y {format_string}")


def format_minutes(minutes: int | None) -> str:
    if minutes is None:
        return "не указано"
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} ч {mins} мин"
    if hours:
        return f"{hours} ч"
    return f"{mins} мин"
