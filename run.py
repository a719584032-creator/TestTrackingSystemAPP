""" 项目运行入口 """
from __future__ import annotations

import sys

from ui.application import main as launch


def main() -> int:
    """启动 UI 程序"""

    return launch()


if __name__ == "__main__":  # pragma: no cover - 命令行入口
    sys.exit(main())
