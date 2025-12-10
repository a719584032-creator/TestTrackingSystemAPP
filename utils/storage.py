"""用于持久化轻量级 JSON 数据的辅助工具。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path) -> Dict[str, Any]:
    """返回 *path* 指向的 JSON 内容；若文件不存在或解析失败，则返回空字典。"""

    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    """将 *payload* 写入 *path*，使用 UTF-8 编码保存 JSON。"""

    # 确保目录存在
    path.parent.mkdir(parents=True, exist_ok=True)

    # 写入格式化的 JSON 内容（ensure_ascii=False 保持中文等字符原样）
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
