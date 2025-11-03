"""Helper script that delegates to :mod:`build` to create an executable."""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))

    from build import build_executable

    build_executable()


if __name__ == "__main__":
    main()
