"""Path helpers for root directories."""
from __future__ import annotations

import os
from pathlib import Path


def get_patvs_root() -> Path:
    """Create and return the root directory."""
    default = Path("C:/FEIYAN")
    root_env = os.environ.get("FEIYAN_ROOT", str(default))
    root = Path(root_env)
    root.mkdir(parents=True, exist_ok=True)
    return root
