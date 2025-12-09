""" 项目运行入口 """
from __future__ import annotations

import sys

from utils.instance_allocator import ensure_instance_paths


def main() -> int:
    """启动 UI 程序"""

    ensure_instance_paths()

    from ui.application import main as launch  # 延后导入，确保实例目录先设置

    return launch()


if __name__ == "__main__":  # pragma: no cover - 命令行入口
    sys.exit(main())
