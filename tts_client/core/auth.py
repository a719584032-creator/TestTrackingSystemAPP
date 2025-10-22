"""Authentication helpers for storing tokens securely."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import SETTINGS
from .storage import load_json, save_json


@dataclass(slots=True)
class RememberMePayload:
    """Represents saved credentials for automatic login."""

    username: str
    token: str

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> "RememberMePayload":
        username = payload.get("username")
        token = payload.get("token")
        if not username or not token:
            raise ValueError("missing username/token")
        return cls(username=username, token=token)

    def to_dict(self) -> dict[str, str]:
        return {"username": self.username, "token": self.token}


class AuthStore:
    """Reads and writes the remember-me payload."""

    def __init__(self) -> None:
        self._path = SETTINGS.remember_me_file

    def load(self) -> Optional[RememberMePayload]:
        payload = load_json(self._path)
        if not payload:
            return None
        try:
            return RememberMePayload.from_dict(payload)
        except ValueError:
            return None

    def save(self, payload: RememberMePayload) -> None:
        save_json(self._path, payload.to_dict())

    def clear(self) -> None:
        if self._path.exists():
            self._path.unlink()
