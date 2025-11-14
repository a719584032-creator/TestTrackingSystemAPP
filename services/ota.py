"""OTA update helpers for the desktop client."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests

from config.settings import SETTINGS
from utils.exceptions import NetworkError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UpdateInfo:
    version: str
    release_notes: str
    download_url: str
    checksum: str = ""


class OTAUpdater:
    """Queries the OTA manifest and exposes update metadata."""

    def __init__(self) -> None:
        self._settings = SETTINGS.ota
        self._api_settings = SETTINGS.api
        self._settings.ensure_dirs()
        self._origin: str | None = None

    def check(self) -> Optional[UpdateInfo]:
        url = urljoin(self._server_origin(), "/api/ota/latest")
        try:
            response = requests.get(url, timeout=self._api_settings.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Failed to query OTA manifest: %s", exc)
            raise NetworkError(str(exc)) from exc

        payload = response.json()
        manifest = self._extract_manifest(payload)
        if not manifest:
            return None

        return UpdateInfo(
            version=str(manifest.get("version", "")),
            release_notes=str(manifest.get("notes", "")),
            download_url=self._resolve_download_url(manifest.get("download_url", "")),
            checksum=str(manifest.get("checksum", "")),
        )

    def _server_origin(self) -> str:
        if self._origin:
            return self._origin

        parsed = urlparse(self._api_settings.base_url)
        if parsed.scheme and parsed.netloc:
            self._origin = f"{parsed.scheme}://{parsed.netloc}"
            return self._origin
        raise NetworkError("API base URL 配置无效，无法构建 OTA 接口。")

    def _extract_manifest(self, payload: Any) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            logger.warning("Unexpected OTA payload: %s", payload)
            return None

        # 新接口：{"code": 200, "data": {...}}
        if "data" in payload:
            code = payload.get("code", 200)
            if code != 200:
                message = payload.get("message") or "OTA 接口返回异常。"
                logger.warning("OTA latest responded with code %s: %s", code, message)
                raise NetworkError(message)
            data = payload.get("data")
            if isinstance(data, dict):
                return data
            logger.warning("OTA payload data is not a dict: %s", data)
            return None

        # 兼容旧格式：直接返回 manifest 内容
        return payload

    def _resolve_download_url(self, url: str) -> str:
        if not url:
            return ""

        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return url

        normalized = url if url.startswith("/") else f"/{url}"
        return urljoin(self._server_origin(), normalized)
