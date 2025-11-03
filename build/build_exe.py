"""Helper script for building a standalone executable via PyInstaller."""
from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = PROJECT_ROOT / "build"
BUILD_DIR.mkdir(parents=True, exist_ok=True)


def build() -> None:
    spec_file = BUILD_DIR / "patvs_client.spec"
    if spec_file.exists():
        spec_file.unlink()
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "TTSClient",
        "--add-data",
        f"{(PROJECT_ROOT / 'resources').as_posix()}{':resources'}",
        (PROJECT_ROOT / "main.py").as_posix(),
    ]
    subprocess.check_call(cmd, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    build()
