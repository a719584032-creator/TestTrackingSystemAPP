"""Runtime settings helper for caching filters and UI state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .storage import load_json, save_json


@dataclass
class PlanFilters:
    directory: Optional[str] = None
    device_model: Optional[str] = None
    priority: Optional[str] = None
    result: Optional[str] = None


class SettingsStore:
    FILE_NAME = "settings.json"

    def __init__(self) -> None:
        self._data: Dict[str, Dict] = load_json(self.FILE_NAME)

    def get_filters(self) -> PlanFilters:
        payload = self._data.get("filters", {})
        return PlanFilters(
            directory=payload.get("directory"),
            device_model=payload.get("device_model"),
            priority=payload.get("priority"),
            result=payload.get("result"),
        )

    def save_filters(self, filters: PlanFilters) -> None:
        self._data["filters"] = {
            "directory": filters.directory,
            "device_model": filters.device_model,
            "priority": filters.priority,
            "result": filters.result,
        }
        save_json(self.FILE_NAME, self._data)
