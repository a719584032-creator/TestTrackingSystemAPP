"""PyInstaller 打包工具"""
from __future__ import annotations

import os
import pkgutil
import subprocess
import sys
from pathlib import Path

from config.settings import APP_VERSION

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
DIST_ROOT = ROOT / "dist"
APP_NAME = "feiyan-app"


def _collect_hidden_imports(packages: list[str]) -> list[str]:
    """
    获取项目所有依赖包
    """

    hidden: set[str] = set()
    for package in packages:
        hidden.add(package)
        package_path = ROOT / package
        if not package_path.exists():
            continue
        for module in pkgutil.walk_packages([str(package_path)], f"{package}."):
            hidden.add(module.name)
    return sorted(hidden)


def _collect_data_directories(directories: list[str]) -> list[tuple[str, str]]:
    """Return ``(source, destination)`` tuples for data directories."""

    data_entries: list[tuple[str, str]] = []
    for directory in directories:
        path = ROOT / directory
        if path.is_dir():
            data_entries.append((str(path), directory))
    return data_entries


def build_executable(output_root: str = "dist") -> None:
    """打包"""

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)
    versioned_dist = ROOT / output_root / f"{APP_NAME}-{APP_VERSION}"
    versioned_dist.mkdir(parents=True, exist_ok=True)

    packages = [
        "config",
        "monitoring",
        "models",
        "services",
        "ui",
        "utils",
        "widgets",
    ]
    data_dirs = ["resources", "data", "config"]

    hidden_imports = _collect_hidden_imports(packages)
    data_entries = _collect_data_directories(data_dirs)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        APP_NAME,
        "--distpath",
        str(versioned_dist),
        "--workpath",
        str(BUILD_DIR / "work"),
        "--specpath",
        str(BUILD_DIR),
        "--paths",
        str(ROOT),
        "--noconsole",
    ]

    for source, destination in data_entries:
        cmd.extend(
            [
                "--add-data",
                f"{source}{os.pathsep}{destination}",
            ]
        )

    for module_name in hidden_imports:
        cmd.extend(["--hidden-import", module_name])

    cmd.append(str(ROOT / "run.py"))

    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    build_executable()
