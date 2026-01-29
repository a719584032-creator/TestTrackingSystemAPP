"""Qt 监控管理封装 """
from __future__ import annotations

import logging
import threading
from typing import Sequence, Tuple

from PyQt5 import QtCore

from .patvs_monitor import Patvs_Fuction
from .parser import MonitoringAction


class MonitoringManager(QtCore.QObject):
    """负责启动和停止硬件监控流程的 Qt 对象。"""

    log_generated = QtCore.pyqtSignal(str)
    monitoring_finished = QtCore.pyqtSignal()
    monitoring_error = QtCore.pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._worker: Patvs_Fuction | None = None
        self._thread: threading.Thread | None = None
        self._thread_done = threading.Event()  # 标记后台监控线程是否已完整退出
        self._thread_join_timeout = 3.0
        self._logger = logging.getLogger(__name__)
        # 该事件用于确保 _stop_worker 只执行一次，避免多线程重复清理
        self._cleanup_guard = threading.Lock()

    # ------------------------------------------------------------------
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        # 已经被清理或未启动则直接返回，避免多余操作
        if self._worker is None:
            return
        self._signal_worker_stop()
        # 使用事件等待后台线程自行收尾；正常情况下 run_main 会很快退出
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            finished = self._thread_done.wait(timeout=self._thread_join_timeout)
            if not finished:
                self._logger.warning(
                    "Monitoring thread did not exit within %.1fs. Forcing cleanup.",
                    self._thread_join_timeout,
                )
                # 超时仍未退出则强制清理，防止新的监控任务无法启动
                self._stop_worker(join_timeout=0.0)
                self.monitoring_error.emit("监控线程退出超时，系统已强制释放监控资源")

    def _signal_worker_stop(self) -> None:
        """向遗留监控逻辑发出退出信号，解除所有等待。"""

        worker = self._worker
        if worker is None:
            return
        worker.is_running = False
        worker.stop_message_loop()
        # 立即唤醒可能正在等待动作完成的主调度线程，避免阻塞
        worker.action_complete.set()

    def discard_session_state(self) -> None:
        """清理当前监控任务的持久化进度。"""

        worker = self._worker
        if worker is not None:
            worker.request_session_reset()
        else:
            Patvs_Fuction.remove_temp_file()

    def start(
        self,
        case_id: str,
        actions: Sequence[MonitoringAction],
        start_time: str,
        *,
        audio_log_files: Sequence[str] | None = None,
    ) -> None:
        # 同一时间只允许一个监控任务运行
        if self.is_running():
            self.monitoring_error.emit("已有监控任务正在执行，请先停止当前任务")
            return

        # 将解析后的动作转换为遗留接口需要的元组形式
        legacy_actions: Tuple[Tuple[str, float], ...] = tuple((a.name, a.amount) for a in actions)

        adapter = _WindowAdapter(self)
        self._worker = Patvs_Fuction(window=adapter, is_running=True)
        if audio_log_files:
            self._worker.update_audio_log_files(audio_log_files)

        def run_monitor() -> None:
            # 使用守护线程运行遗留监控脚本，保持界面主线程顺畅
            try:
                self._worker.run_main(case_id, legacy_actions, start_time)
            except Exception as exc:  # pragma: no cover - 硬件层集成异常不易稳定复现
                self.monitoring_error.emit(str(exc))
            finally:
                self._stop_worker()

        # 启动前先重置线程完成标志，确保等待逻辑可用
        self._thread_done.clear()
        self._thread = threading.Thread(target=run_monitor, daemon=True, name="MonitoringWorker")
        # 后台线程启动后，界面主线程可继续响应用户操作
        self._thread.start()

    # ------------------------------------------------------------------
    def _stop_worker(self, *, join_timeout: float | None = None) -> None:
        # 多线程场景下可能被主线程和监控线程同时调用，通过事件保证只清理一次
        if self._thread_done.is_set():
            return
        with self._cleanup_guard:
            if self._thread_done.is_set():
                return
            self._signal_worker_stop()
            worker = self._worker
            thread = self._thread
            # 清空引用以便后续重新创建监控任务
            self._worker = None
            self._thread = None

            timeout = self._thread_join_timeout if join_timeout is None else max(join_timeout, 0.0)
            if thread:
                if thread is threading.current_thread():
                    # 监控线程自己调用时不允许 join，直接交由 finally 分支退出
                    pass
                else:
                    thread.join(timeout=timeout)
                    if thread.is_alive():
                        self._logger.warning(
                            "Monitoring thread still alive after %.1fs timeout.",
                            timeout,
                        )
            self._thread_done.set()
            # 无论是正常结束还是强制中断，都统一向界面报告收尾完成
            self.monitoring_finished.emit()


class _WindowAdapter:
    """将遗留回调桥接到 Qt 信号的适配器。"""

    def __init__(self, manager: MonitoringManager) -> None:
        self._manager = manager

    def add_log_message(self, message: str) -> None:
        self._manager.log_generated.emit(str(message))

    def after_test(self) -> None:
        # 统一由 MonitoringManager._stop_worker 触发监控完成事件，避免重复通知
        return
