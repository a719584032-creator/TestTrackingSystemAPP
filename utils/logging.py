"""Application-wide logging utilities."""
from __future__ import annotations

import datetime as dt
import logging
import sys
import traceback
from pathlib import Path

from config.settings import SETTINGS


def configure_logging() -> Path:
    """Configure root logging handlers and return the active log directory."""

    log_root = SETTINGS.log_root
    log_dir = log_root / dt.datetime.now().strftime("%Y%m%d")
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "application.log"

    formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(name)s - %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console)
    root_logger.addHandler(file_handler)

    install_exception_hook(log_dir / "crash.log")
    return log_dir


def install_exception_hook(crash_file: Path) -> None:
    """Ensure uncaught exceptions are persisted to *crash_file*."""

    def handle_exception(exc_type, exc_value, exc_traceback):  # type: ignore[override]
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logging.critical("应用发生未处理异常:\n%s", message)
        crash_file.parent.mkdir(parents=True, exist_ok=True)
        with crash_file.open("a", encoding="utf-8") as handle:
            handle.write(f"[{dt.datetime.now().isoformat()}] {message}\n")

    sys.excepthook = handle_exception  # type: ignore[assignment]

