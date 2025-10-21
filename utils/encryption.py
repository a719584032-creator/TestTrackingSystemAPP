"""Utility helpers for encoding execution timestamps."""
from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime
from typing import Optional

from ..config import APP_CONFIG


def _sign(value: str) -> str:
    secret = APP_CONFIG.secret_key.encode("utf-8")
    return hmac.new(secret, value.encode("utf-8"), hashlib.sha256).hexdigest()


def encode_timestamp(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    millis = int(dt.timestamp() * 1000)
    payload = f"{millis}.{_sign(str(millis))}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")
