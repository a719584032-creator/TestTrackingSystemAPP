"""Configuration helpers for the TTS desktop client."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .paths import get_patvs_root


APP_NAME = "Test Tracking System"
CONFIG_DIR = Path.home() / ".tts_client"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
PATVS_ROOT = get_patvs_root()


@dataclass(slots=True)
class ApiSettings:
    """Runtime API settings used by the HTTP client."""

    base_url: str = "http://10.184.46.54:5173/api"
    #base_url: str = "http://10.184.37.17:5173/api"

    timeout: int = 30


@dataclass(slots=True)
class OTASettings:
    """Settings that describe the OTA update channel."""

    manifest_url: str = "https://ota.example.com/tts/manifest.json"
    download_dir: Path = CONFIG_DIR / "downloads"

    def ensure_dirs(self) -> None:
        self.download_dir.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class ClientSettings:
    """Aggregate configuration object for the desktop client."""

    api: ApiSettings = ApiSettings()
    ota: OTASettings = OTASettings()
    remember_me_file: Path = PATVS_ROOT / "credentials.json"
    ui_state_file: Path = CONFIG_DIR / "ui_state.json"
    window_state_file: Path = CONFIG_DIR / "window_state.json"
    monitoring_cache_file: Path = CONFIG_DIR / "monitoring_state.json"
    log_root: Path = PATVS_ROOT
    monitoring_temp_file: Path = PATVS_ROOT / "temp_action_and_num.json"


SETTINGS = ClientSettings()
