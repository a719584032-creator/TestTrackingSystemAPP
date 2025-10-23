"""Persists lightweight UI and workflow state for the desktop client."""
from __future__ import annotations

from typing import Any, Dict, Optional

from PyQt5 import QtCore

from .config import SETTINGS
from .storage import load_json, save_json


class WindowStateStore:
    """Stores and restores main window geometry."""

    def __init__(self) -> None:
        self._path = SETTINGS.window_state_file

    def save(self, geometry: QtCore.QByteArray, state: QtCore.QByteArray) -> None:
        payload = {
            "geometry": bytes(geometry).hex(),
            "state": bytes(state).hex(),
        }
        save_json(self._path, payload)

    def load(self) -> tuple[Optional[QtCore.QByteArray], Optional[QtCore.QByteArray]]:
        payload = load_json(self._path)
        if not payload:
            return None, None
        geometry = payload.get("geometry")
        state = payload.get("state")
        return (
            QtCore.QByteArray.fromHex(geometry.encode("ascii")) if geometry else None,
            QtCore.QByteArray.fromHex(state.encode("ascii")) if state else None,
        )


class ExecutionStateStore:
    """Persists per-user execution workflow progress for crash recovery."""

    def __init__(self) -> None:
        self._path = SETTINGS.monitoring_cache_file

    def load(self, user_key: str) -> Dict[str, Any]:
        """Return the stored execution state for *user_key*."""

        if not user_key:
            return {}
        payload = load_json(self._path)
        state = payload.get(user_key)
        return state if isinstance(state, dict) else {}

    def save(self, user_key: str, state: Dict[str, Any]) -> None:
        """Persist *state* for *user_key*."""

        if not user_key:
            return
        payload = load_json(self._path)
        if state:
            payload[user_key] = state
        else:
            payload.pop(user_key, None)
        save_json(self._path, payload)

    def clear(self, user_key: str) -> None:
        """Remove any persisted state for *user_key*."""

        if not user_key:
            return
        payload = load_json(self._path)
        if user_key in payload:
            payload.pop(user_key, None)
            save_json(self._path, payload)
