"""Convenience launcher for running the desktop client directly."""
from __future__ import annotations

import sys

from ui.application import main as launch


def main() -> int:
    """Launch the UI application and return its exit code."""

    return launch()


if __name__ == "__main__":  # pragma: no cover - 命令行入口
    sys.exit(main())
