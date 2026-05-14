from __future__ import annotations

from fastapi import Header, HTTPException, status

from packages.core.config import get_settings
from packages.core.security import secure_equals


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not x_admin_token or not secure_equals(x_admin_token, settings.admin_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin token required")
