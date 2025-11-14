"""Service layer that communicates with remote APIs and local storage."""
from __future__ import annotations

from .api_client import ApiClient, encode_attachment
from .auth import AuthStore, RememberedCredentials
from .ota import OTAUpdater, UpdateInfo
from .update_manager import UpdateManager

__all__ = [
    "ApiClient",
    "AuthStore",
    "RememberedCredentials",
    "OTAUpdater",
    "UpdateInfo",
    "UpdateManager",
    "encode_attachment",
]
