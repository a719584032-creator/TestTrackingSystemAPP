"""Qt friendly wrapper around the legacy monitoring implementation."""
from __future__ import annotations

import threading
from typing import Sequence, Tuple

from PyQt5 import QtCore

from ..core.monitor_parser import MonitoringAction
from monitoring.patvs_monitor import Patvs_Fuction


class MonitoringManager(QtCore.QObject):
    """Starts and stops hardware monitoring workflows."""

    log_generated = QtCore.pyqtSignal(str)
    monitoring_finished = QtCore.pyqtSignal()
    monitoring_error = QtCore.pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._worker: Patvs_Fuction | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        if self._worker is None:
            return
        self._worker.is_running = False

    def start(self, case_id: int, actions: Sequence[MonitoringAction], start_time: str) -> None:
        if self.is_running():
            self.monitoring_error.emit("已有监控任务正在执行，请先停止当前任务")
            return

        legacy_actions: Tuple[Tuple[str, float], ...] = tuple((a.name, a.amount) for a in actions)

        adapter = _WindowAdapter(self)
        self._worker = Patvs_Fuction(window=adapter, is_running=True)

        def run_monitor() -> None:
            try:
                self._worker.run_main(case_id, legacy_actions, start_time)
            except Exception as exc:  # pragma: no cover - hardware integration
                self.monitoring_error.emit(str(exc))
            finally:
                self._stop_worker()

        self._thread = threading.Thread(target=run_monitor, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    def _stop_worker(self) -> None:
        worker = self._worker
        thread = self._thread
        self._worker = None
        self._thread = None
        if worker:
            worker.is_running = False
        if thread and thread is not threading.current_thread():
            thread.join(timeout=0)
        self.monitoring_finished.emit()


class _WindowAdapter:
    """Bridge object that maps legacy callbacks to Qt signals."""

    def __init__(self, manager: MonitoringManager) -> None:
        self._manager = manager

    def add_log_message(self, message: str) -> None:
        self._manager.log_generated.emit(str(message))

    def after_test(self) -> None:
        self._manager.monitoring_finished.emit()
