from __future__ import annotations

import secrets
import string


def generate_alarm_code(length: int = 4) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))
