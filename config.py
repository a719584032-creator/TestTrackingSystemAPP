"""Application configuration for the PATVS desktop client."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ApiConfig:
    """REST API related configuration."""

    base_url: str = os.getenv("PATVS_API_BASE_URL", "http://10.184.37.17:5173/api")
    timeout_seconds: int = int(os.getenv("PATVS_API_TIMEOUT", "30"))


@dataclass(frozen=True)
class AppConfig:
    """General application configuration constants."""

    app_name: str = "PATVS 桌面客户端"
    version: str = os.getenv("PATVS_CLIENT_VERSION", "3.0.0")
    secret_key: str = os.getenv("PATVS_SECRET_KEY", "dev-secret-key")
    data_dir: str = os.getenv(
        "PATVS_DATA_DIR",
        os.path.join(os.path.expanduser("~"), ".patvs_client"),
    )
    remember_me_file: str = os.path.join(data_dir, "auth.json")
    ota_feed_url: str = os.getenv("PATVS_OTA_FEED", "https://update.example.com/patvs/feed.json")
    ota_download_dir: str = os.path.join(data_dir, "updates")


API_CONFIG = ApiConfig()
APP_CONFIG = AppConfig()
