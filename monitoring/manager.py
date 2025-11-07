"""Qt friendly wrapper around the legacy monitoring implementation."""
from __future__ import annotations

import logging
import threading
from typing import Sequence, Tuple

from PyQt5 import QtCore

from .patvs_monitor import Patvs_Fuction
from .parser import MonitoringAction


class MonitoringManager(QtCore.QObject):
    """Starts and stops hardware monitoring workflows."""

    log_generated = QtCore.pyqtSignal(str)
    monitoring_finished = QtCore.pyqtSignal()
    monitoring_error = QtCore.pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._worker: Patvs_Fuction | None = None
        self._thread: threading.Thread | None = None
        self._thread_done = threading.Event()
        self._thread_join_timeout = 3.0
        self._logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        if self._worker is None:
            return
        self._worker.is_running = False
        self._worker.stop_message_loop()
        # 立即唤醒可能正在等待动作完成的主调度线程，避免阻塞
        self._worker.action_complete.set()

        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            finished = self._thread_done.wait(timeout=self._thread_join_timeout)
            if not finished:
                self._logger.warning(
                    "Monitoring thread did not exit within %.1fs. Continuing shutdown.",
                    self._thread_join_timeout,
                )

    def discard_session_state(self) -> None:
        """Clear any persisted monitoring progress for the active worker."""

        worker = self._worker
        if worker is not None:
            worker.request_session_reset()
        else:
            Patvs_Fuction.remove_temp_file()

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

        self._thread_done.clear()
        self._thread = threading.Thread(target=run_monitor, daemon=True, name="MonitoringWorker")
        self._thread.start()

    # ------------------------------------------------------------------
    def _stop_worker(self) -> None:
        worker = self._worker
        thread = self._thread
        self._worker = None
        if worker:
            worker.is_running = False
            worker.stop_message_loop()
            worker.action_complete.set()
        if thread:
            if thread is threading.current_thread():
                self._thread = None
            else:
                thread.join(timeout=self._thread_join_timeout)
                if thread.is_alive():
                    self._logger.warning(
                        "Monitoring thread still alive after %.1fs timeout.",
                        self._thread_join_timeout,
                    )
                    self._thread = thread
                else:
                    self._thread = None
        else:
            self._thread = None
        self._thread_done.set()
        self.monitoring_finished.emit()


class _WindowAdapter:
    """Bridge object that maps legacy callbacks to Qt signals."""

    def __init__(self, manager: MonitoringManager) -> None:
        self._manager = manager

    def add_log_message(self, message: str) -> None:
        self._manager.log_generated.emit(str(message))

    # def after_test(self) -> None:
        # self._manager.monitoring_finished.emit()
        # pass
