"""PyQt friendly wrapper around the legacy monitoring logic."""
from __future__ import annotations

import threading
from typing import Callable, Sequence, Tuple

from PyQt5 import QtCore

from .patvs_monitor import Patvs_Fuction


class MonitorEvent(QtCore.QObject):
    log_generated = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)


class _WindowAdapter:
    def __init__(self, signaler: MonitorEvent, on_complete: Callable[[], None]) -> None:
        self._signaler = signaler
        self._on_complete = on_complete

    # Legacy callbacks -------------------------------------------------
    def add_log_message(self, message: str) -> None:
        self._signaler.log_generated.emit(str(message))

    def after_test(self) -> None:
        self._on_complete()


class MonitoringController(QtCore.QObject):
    """High level controller responsible for orchestrating monitoring tasks."""

    log_generated = QtCore.pyqtSignal(str)
    monitoring_finished = QtCore.pyqtSignal()
    monitoring_error = QtCore.pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._event = MonitorEvent()
        self._event.log_generated.connect(self.log_generated)
        self._event.finished.connect(self.monitoring_finished)
        self._event.error.connect(self.monitoring_error)
        self._worker: Patvs_Fuction | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    def is_running(self) -> bool:
        return self._worker is not None and self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        if self._worker is None:
            return
        self._worker.stop_event = False

    def start(self, case_id: int, actions: Sequence[Tuple[str, float]], start_time: str) -> None:
        if self.is_running():
            self.monitoring_error.emit("已有监控任务正在运行，请先停止当前任务")
            return

        adapter = _WindowAdapter(self._event, self._handle_finish)
        self._worker = Patvs_Fuction(window=adapter, stop_event=True)

        def run_monitor():
            try:
                self._worker.run_main(case_id, actions, start_time)
            except Exception as exc:  # pragma: no cover - hardware interaction
                self._event.error.emit(str(exc))
            finally:
                self._stop_worker()

        self._thread = threading.Thread(target=run_monitor, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    def _handle_finish(self) -> None:
        self.monitoring_finished.emit()
        self._stop_worker()

    def _stop_worker(self) -> None:
        worker = self._worker
        thread = self._thread
        self._worker = None
        self._thread = None
        if thread:
            thread.join(timeout=0)
        if worker:
            worker.stop_event = False
