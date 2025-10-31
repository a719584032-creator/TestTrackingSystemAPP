"""Lightweight encryption helpers for sensitive credentials."""
from __future__ import annotations

import base64
import getpass
import hashlib
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

