from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str


class DomainValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        message = "; ".join(f"{issue.field}: {issue.message}" for issue in issues)
        super().__init__(message)


def require_range(field: str, value: int, min_value: int, max_value: int) -> ValidationIssue | None:
    if min_value <= value <= max_value:
        return None
    return ValidationIssue(field, f"must be between {min_value} and {max_value}")


def validate_sleep_numbers(
    slept_last_night_minutes: int,
    quality: int,
    sleepiness: int,
    stress: int,
    free_minutes: int,
) -> None:
    issues = [
        require_range("slept_last_night_minutes", slept_last_night_minutes, 0, 24 * 60),
        require_range("quality", quality, 1, 5),
        require_range("sleepiness", sleepiness, 1, 5),
        require_range("stress", stress, 1, 5),
        require_range("free_minutes", free_minutes, 1, 240),
    ]
    normalized = [issue for issue in issues if issue is not None]
    if normalized:
        raise DomainValidationError(normalized)
