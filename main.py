"""Compatibility entry point that delegates to the refactored client."""
from __future__ import annotations

import sys

from tts_client.app import main


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
