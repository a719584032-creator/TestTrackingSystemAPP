"""Authentication helpers for storing tokens securely."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config.settings import SETTINGS
from utils.security import decrypt_password, encrypt_password
from utils.storage import load_json, save_json


@dataclass(slots=True)
class RememberMePayload:
    """Serialized payload persisted to disk."""

    username: str
    password_cipher: str

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> "RememberMePayload":
        username = payload.get("username")
        cipher = payload.get("password") or payload.get("password_cipher")
        if not username or not cipher:
            raise ValueError("missing username/password")
        return cls(username=username, password_cipher=cipher)

    def to_dict(self) -> dict[str, str]:
        return {"username": self.username, "password": self.password_cipher}

    def decrypt(self) -> "RememberedCredentials":
        password = decrypt_password(self.password_cipher)
        if password is None:
            raise ValueError("无法解密存储的密码")
        return RememberedCredentials(username=self.username, password=password)


@dataclass(slots=True)
class RememberedCredentials:
    """Plain-text credentials returned to the caller."""

    username: str
    password: str


class AuthStore:
    """Reads and writes the remember-me payload."""

    def __init__(self) -> None:
        self._path = SETTINGS.remember_me_file

    def load(self) -> Optional[RememberedCredentials]:
        payload = load_json(self._path)
        if not payload:
            return None
        try:
            stored = RememberMePayload.from_dict(payload)
            return stored.decrypt()
        except ValueError:
            self.clear()
            return None

    def save(self, credentials: RememberedCredentials) -> None:
        cipher = encrypt_password(credentials.password)
        payload = RememberMePayload(username=credentials.username, password_cipher=cipher)
        save_json(self._path, payload.to_dict())

    def clear(self) -> None:
        if self._path.exists():
            self._path.unlink()
