"""Static resource helpers (icons, translations, etc.)."""
from __future__ import annotations

from pathlib import Path

RESOURCE_DIR = Path(__file__).resolve().parent

__all__ = ["RESOURCE_DIR"]
