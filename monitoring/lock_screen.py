# -*- coding: utf-8 -*-
# 检测电脑锁屏事件
import ctypes
import win32api
import win32con
import win32gui
import win32ts
import uuid
from PyQt5 import QtCore
import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)


if TYPE_CHECKING:  # pragma: no cover
    from .patvs_monitor import Patvs_Fuction


class _WxCompat:
    @staticmethod
    def CallAfter(func, *args, **kwargs):
        QtCore.QTimer.singleShot(0, lambda: func(*args, **kwargs))


wx = _WxCompat()

# 定义WM_WTSSESSION_CHANGE常量的值
WM_WTSSESSION_CHANGE = 0x2B1

WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8


class WTSSESSION_NOTIFICATION(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint),
                ("dwSessionId", ctypes.c_uint)]


class SessionNotificationHandler:
    def __init__(self, context: "Patvs_Fuction", target_cycles, initial_count=0):
        self.hwnd = None
        self.context = context
        self.window = context.window
        self.className = f"suopin_WindowClass_{uuid.uuid4()}"
        self.target_cycles = target_cycles
        try:
            self.lock_count = int(float(initial_count))
        except (TypeError, ValueError):
            self.lock_count = 0
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self.wnd_proc
        wc.lpszClassName = self.className
        self.class_atom = win32gui.RegisterClass(wc)
        self.hwnd = win32gui.CreateWindow(self.class_atom,
                                          self.className,
                                          0,
                                          0, 0, 0, 0,
                                          0, 0, 0, None)
        win32ts.WTSRegisterSessionNotification(self.hwnd, win32ts.NOTIFY_FOR_THIS_SESSION)

    def wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_WTSSESSION_CHANGE:  # 使用自定义的常量
            if wparam == WTS_SESSION_LOCK:
                self.lock_count += 1
                self.context.log(f"会话已锁定. 锁屏次数: {self.lock_count}")
                self.context.record_count_progress_if_current(
                    self.target_cycles, self.lock_count, expected_keys={"锁屏"}
                )
                if self.target_cycles and self.lock_count >= self.target_cycles:
                    self.context.record_count_progress_if_current(
                        self.target_cycles,
                        self.lock_count,
                        expected_keys={"锁屏"},
                    )
                    self.context.log(
                        f"已完成目标锁屏次数: {self.target_cycles} ，Exiting..."
                    )
                    win32ts.WTSUnRegisterSessionNotification(self.hwnd)
                    win32gui.DestroyWindow(self.hwnd)
                    win32gui.PostQuitMessage(0)
            elif wparam == WTS_SESSION_UNLOCK:
                #wx.CallAfter(self.window.add_log_message, "会话已解锁")
                pass
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def run(self):
        self.context.log("开始监控电脑锁屏事件")
        try:
            win32gui.PumpMessages()
        except KeyboardInterrupt:
            self.context.log("停止电脑锁屏监控.......")
            win32ts.WTSUnRegisterSessionNotification(self.hwnd)
            win32gui.DestroyWindow(self.hwnd)
            win32gui.UnregisterClass(self.class_atom, None)
        except Exception as e:
            logger.error(f"未知错误 {e}")


def monitor_locks(context: "Patvs_Fuction", target_cycles, remaining_cycles=None):
    try:
        total_target = float(target_cycles)
    except (TypeError, ValueError):
        total_target = 0.0
    if total_target <= 0:
        context.log("锁屏目标次数为 0，自动跳过。")
        context.record_count_progress_if_current(0, 0, expected_keys={"锁屏"})
        return

    if remaining_cycles is None:
        remaining = total_target
    else:
        try:
            remaining = float(remaining_cycles)
        except (TypeError, ValueError):
            remaining = total_target
    remaining = max(0.0, min(total_target, remaining))
    completed = max(0.0, total_target - remaining)

    if completed > 0:
        context.log(
            f"锁屏已累计 {completed:g} 次，剩余 {max(0.0, total_target - completed):g} 次。"
        )

    handler = SessionNotificationHandler(context, total_target, initial_count=completed)
    handler.run()
