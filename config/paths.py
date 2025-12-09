"""用于获取日志根目录"""
from __future__ import annotations

import os
from pathlib import Path


def get_patvs_root() -> Path:
    """创建并返回根目录"""

    default = Path("C:/PATVS")
    root_env = os.environ.get("PATVS_ROOT", str(default))
    root = Path(root_env)
    root.mkdir(parents=True, exist_ok=True)
    return root
