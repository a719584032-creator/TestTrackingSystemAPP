"""Helper utilities for packaging the client with PyInstaller."""
from __future__ import annotations

import os
import pkgutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"


def _collect_hidden_imports(packages: list[str]) -> list[str]:
    """Return a list of all modules that should be force-imported.

    PyInstaller struggles to discover dynamically imported modules inside our
    package namespaces (``ui``, ``services`` …).  Walking the package tree and
    feeding the discovered modules as ``--hidden-import`` arguments guarantees
    they are bundled inside the executable.
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


def build_executable(output_dir: str = "dist") -> None:
    """Build the standalone executable using the current project layout."""

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

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
        "patvs-client",
        "--distpath",
        str(ROOT / output_dir),
        "--workpath",
        str(BUILD_DIR / "work"),
        "--specpath",
        str(BUILD_DIR),
        "--paths",
        str(ROOT),
        "--noconsole"
    ]

    for source, destination in data_entries:
        cmd.extend([
            "--add-data",
            f"{source}{os.pathsep}{destination}",
        ])

    for module_name in hidden_imports:
        cmd.extend(["--hidden-import", module_name])

    cmd.append(str(ROOT / "main.py"))

    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    build_executable()
