"""OTA update helpers for the desktop client."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests

from config.settings import SETTINGS
from utils.exceptions import NetworkError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UpdateInfo:
    version: str
    release_notes: str
    download_url: str


class OTAUpdater:
    """Queries the OTA manifest and exposes update metadata."""

    def __init__(self) -> None:
        self._settings = SETTINGS.ota
        self._settings.ensure_dirs()

    def check(self) -> Optional[UpdateInfo]:
        url = self._settings.manifest_url
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Failed to query OTA manifest: %s", exc)
            raise NetworkError(str(exc)) from exc
        payload = response.json()
        if not payload:
            return None
        return UpdateInfo(
            version=payload.get("version", ""),
            release_notes=payload.get("notes", ""),
            download_url=payload.get("download_url", ""),
        )
