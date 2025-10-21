"""Simple OTA updater that checks a JSON feed for new versions."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

from .config import APP_CONFIG

LOGGER = logging.getLogger(__name__)


@dataclass
class UpdateInfo:
    version: str
    download_url: str
    release_notes: Optional[str] = None


class OTAUpdater:
    def __init__(self, feed_url: Optional[str] = None) -> None:
        self.feed_url = feed_url or APP_CONFIG.ota_feed_url
        self.download_dir = Path(APP_CONFIG.ota_download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def check_for_updates(self) -> Optional[UpdateInfo]:
        try:
            response = requests.get(self.feed_url, timeout=10)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # pragma: no cover - network issue
            LOGGER.warning("Failed to check updates: %s", exc)
            return None
        latest = payload.get("latest")
        if not latest:
            return None
        version = latest.get("version")
        download_url = latest.get("url")
        if not version or not download_url:
            return None
        if version == APP_CONFIG.version:
            return None
        return UpdateInfo(version=version, download_url=download_url, release_notes=latest.get("notes"))

    def download(self, update_info: UpdateInfo) -> Optional[Path]:
        try:
            response = requests.get(update_info.download_url, timeout=30, stream=True)
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - network issue
            LOGGER.error("Failed to download update: %s", exc)
            return None
        file_name = self.download_dir / f"patvs-client-{update_info.version}.exe"
        with file_name.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)
        return file_name
