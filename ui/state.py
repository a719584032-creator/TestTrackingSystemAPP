"""Persists lightweight UI state such as window geometry."""
from __future__ import annotations

from typing import Optional

from PyQt5 import QtCore

from config.settings import SETTINGS
from utils.storage import load_json, save_json


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
