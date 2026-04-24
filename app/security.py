from __future__ import annotations

from dataclasses import dataclass


SENSITIVE_KEYS = {"telegram_bot_token", "code", "password", "secret"}


def mask_sensitive(value: str, visible: int = 2) -> str:
    if len(value) <= visible:
        return "*" * len(value)
    return f"{'*' * (len(value) - visible)}{value[-visible:]}"


def redact_payload(payload: dict) -> dict:
    out = {}
    for key, value in payload.items():
        if key.lower() in SENSITIVE_KEYS and isinstance(value, str):
            out[key] = mask_sensitive(value)
        else:
            out[key] = value
    return out


@dataclass(frozen=True)
class SecurityNote:
    title: str
    description: str
