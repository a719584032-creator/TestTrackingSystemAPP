"""Program entry point that delegates to the Qt application bootstrap."""
from __future__ import annotations

import sys

from ui.application import main as run_application


def main() -> int:
    """Launch the desktop client and return the exit code."""

    return run_application()


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
