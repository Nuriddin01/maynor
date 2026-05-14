from __future__ import annotations

import hmac
from hashlib import sha256


def secure_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode(), right.encode())


def fingerprint(value: str) -> str:
    return sha256(value.encode()).hexdigest()
