"""Authentication helpers for storing and retrieving login information."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import APP_CONFIG


@dataclass
class AuthTokens:
    token: str
    expires_in: int


@dataclass
class RememberMePayload:
    username: str
    token: str


class AuthStore:
    """Persist authentication tokens to disk when remember-me is enabled."""

    def __init__(self, storage_path: Optional[str] = None) -> None:
        self._storage_path = Path(storage_path or APP_CONFIG.remember_me_file)
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Optional[RememberMePayload]:
        if not self._storage_path.exists():
            return None
        try:
            data = json.loads(self._storage_path.read_text(encoding="utf-8"))
            if not data.get("username") or not data.get("token"):
                return None
            return RememberMePayload(username=data["username"], token=data["token"])
        except Exception:
            return None

    def save(self, payload: RememberMePayload) -> None:
        data = {"username": payload.username, "token": payload.token}
        self._storage_path.write_text(json.dumps(data), encoding="utf-8")

    def clear(self) -> None:
        if self._storage_path.exists():
            self._storage_path.unlink()
