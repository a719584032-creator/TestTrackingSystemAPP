"""Qt friendly wrapper around the legacy monitoring implementation."""
from __future__ import annotations

import logging
import threading
from importlib import import_module, util as importlib_util
from typing import Sequence, Tuple

from PyQt5 import QtCore

from .patvs_monitor import Patvs_Fuction
from .parser import MonitoringAction


logger = logging.getLogger(__name__)

_WIN32API_SPEC = importlib_util.find_spec("win32api")
if _WIN32API_SPEC is not None:
    win32api = import_module("win32api")
else:  # pragma: no cover - platform dependent
    win32api = None

WM_QUIT = 0x0012


class MonitoringManager(QtCore.QObject):
    """Starts and stops hardware monitoring workflows."""

    log_generated = QtCore.pyqtSignal(str)
    monitoring_finished = QtCore.pyqtSignal()
    monitoring_error = QtCore.pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._worker: Patvs_Fuction | None = None
        self._thread: threading.Thread | None = None
        self._active_actions: Tuple[str, ...] = ()

    # ------------------------------------------------------------------
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self, *, force_message_loop_stop: bool = False) -> None:
        if self._worker is None:
            return
        self._worker.is_running = False
        # 立即唤醒可能正在等待动作完成的主调度线程，避免阻塞
        self._worker.action_complete.set()
        if force_message_loop_stop and self._requires_message_loop_stop():
            self._request_message_loop_exit()

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
        self._active_actions = tuple(name.strip().lower() for name, _ in legacy_actions)

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
        self._active_actions = ()
        if worker:
            worker.is_running = False
            worker.action_complete.set()
        if thread and thread is not threading.current_thread():
            thread.join(timeout=0)
        self.monitoring_finished.emit()

    # ------------------------------------------------------------------
    def _requires_message_loop_stop(self) -> bool:
        for name in self._active_actions:
            if "usb插拔" in name or "锁屏" in name:
                return True
        return False

    def _request_message_loop_exit(self) -> None:
        worker = self._worker
        if worker is None:
            return

        callback_executed = worker.request_message_loop_shutdown()
        if callback_executed:
            logger.debug("已调用监控上下文注册的消息循环终止回调")

        thread_id = worker.msg_loop_thread_id
        if not thread_id:
            if callback_executed:
                logger.debug("消息循环线程已清除，不再发送 WM_QUIT")
            return

        if win32api is None:  # pragma: no cover - platform dependent
            logger.debug(
                "win32api 不可用，无法向监控消息循环线程 %s 发送 WM_QUIT", thread_id
            )
            return

        try:
            win32api.PostThreadMessage(int(thread_id), WM_QUIT, 0, 0)
        except Exception as exc:  # pragma: no cover - hardware interaction
            logger.warning(
                "向监控消息循环线程 %s 发送 WM_QUIT 失败: %s", thread_id, exc
            )
        else:
            logger.debug(
                "已向监控消息循环线程 %s 发送 WM_QUIT (callback_executed=%s)",
                thread_id,
                callback_executed,
            )
        finally:
            worker.msg_loop_thread_id = None


class _WindowAdapter:
    """Bridge object that maps legacy callbacks to Qt signals."""

    def __init__(self, manager: MonitoringManager) -> None:
        self._manager = manager

    def add_log_message(self, message: str) -> None:
        self._manager.log_generated.emit(str(message))

    def after_test(self) -> None:
        self._manager.monitoring_finished.emit()
