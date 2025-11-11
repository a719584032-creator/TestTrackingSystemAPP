"""Lightweight encryption helpers for sensitive credentials."""
from __future__ import annotations

import base64
import datetime as dt
import getpass
import hashlib
import hmac
import platform
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


def _derive_key() -> bytes:
    """Derive a stable key bound to the current machine and user."""

    user = getpass.getuser()
    node = platform.node()
    fingerprint = f"{user}:{node}".encode("utf-8")
    digest = hashlib.sha256(fingerprint).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_password(password: str) -> str:
    """Return an encrypted representation of *password*."""

    if not password:
        raise ValueError("password must not be empty")
    cipher = Fernet(_derive_key())
    token = cipher.encrypt(password.encode("utf-8"))
    return token.decode("ascii")


def decrypt_password(token: str) -> Optional[str]:
    """Return the decrypted password stored in *token* if possible."""

    if not token:
        return None
    cipher = Fernet(_derive_key())
    try:
        return cipher.decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def _parse_datetime_to_utc(value: str) -> dt.datetime:
    """Parse *value* as ISO datetime string and convert to UTC."""

    trimmed = (value or "").strip()
    if not trimmed:
        raise ValueError("value must not be empty")
    iso_candidate = trimmed
    if iso_candidate.endswith("Z"):
        iso_candidate = iso_candidate[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(iso_candidate)
    except ValueError as exc:
        raise ValueError("invalid datetime format") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    else:
        parsed = parsed.astimezone(dt.timezone.utc)
    return parsed


def encode_timestamp_token(value: str, secret: str) -> str:
    """Encode *value* as a timestamp token signed with *secret*."""

    if not secret:
        raise ValueError("secret must not be empty")
    timestamp = _parse_datetime_to_utc(value)
    millis = int(timestamp.timestamp() * 1000)
    timestamp_part = str(millis)
    signature = hmac.new(
        secret.encode("utf-8"),
        timestamp_part.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    token = f"{timestamp_part}.{signature}"
    encoded = base64.urlsafe_b64encode(token.encode("utf-8")).decode("ascii")
    return encoded
