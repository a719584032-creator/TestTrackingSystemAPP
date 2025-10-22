"""Shared filesystem helpers for PATVS specific storage locations."""
from __future__ import annotations

import os
from pathlib import Path


def get_patvs_root() -> Path:
    """Return the base directory for PATVS assets, creating it if missing."""

    default = Path("C:/PATVS") if os.name == "nt" else Path.home() / "PATVS"
    root_env = os.environ.get("PATVS_ROOT", str(default))
    root = Path(root_env)
    root.mkdir(parents=True, exist_ok=True)
    return root

