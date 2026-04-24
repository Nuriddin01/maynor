from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def parse_int(value: str) -> int:
    normalized = value.strip().replace(",", ".")
    if "." in normalized:
        raise ValueError("Нужно целое число без дробной части.")
    return int(normalized)


def parse_int_in_range(value: str, min_value: int, max_value: int) -> int:
    parsed = parse_int(value)
    if not min_value <= parsed <= max_value:
        raise ValueError(f"Нужно число в диапазоне {min_value}-{max_value}.")
    return parsed


def parse_minutes(value: str, max_value: int = 1440) -> int:
    return parse_int_in_range(value, 0, max_value)


def parse_scale_1_5(value: str) -> int:
    return parse_int_in_range(value, 1, 5)


def parse_yes_no(value: str) -> bool:
    normalized = value.strip().lower()
    yes_variants = {"да", "yes", "y", "ага"}
    no_variants = {"нет", "no", "n"}
    if normalized in yes_variants:
        return True
    if normalized in no_variants:
        return False
    raise ValueError("Нужно выбрать «Да» или «Нет».")


def validate_timezone_name(value: str) -> str:
    timezone_name = value.strip()
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Не удалось распознать часовой пояс.") from exc
    return timezone_name
