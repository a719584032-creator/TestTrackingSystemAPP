"""Generic local storage helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .config import APP_CONFIG


def load_json(name: str) -> Dict[str, Any]:
    path = Path(APP_CONFIG.data_dir, name)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json(name: str, data: Dict[str, Any]) -> None:
    path = Path(APP_CONFIG.data_dir, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
