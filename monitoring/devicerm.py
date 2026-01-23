# -*- coding: utf-8 -*-
# 检测设备热插拔事件 并在控制台输出 ，依赖库 pywin32
# WinApi 参考文档 http://www.yfvb.com/help/win32sdk/    https://timgolden.me.uk/pywin32-docs/contents.html
import win32con
import win32gui
import win32api
import win32gui_struct
from datetime import datetime
from PyQt5 import QtCore
import logging
import pywintypes
import winerror
import time

logger = logging.getLogger(__name__)

DEFAULT_BATCH_WINDOW = 3.0


class _WxCompat:
    @staticmethod
    def CallAfter(func, *args, **kwargs):
        QtCore.QTimer.singleShot(0, lambda: func(*args, **kwargs))


wx = _WxCompat()
import uuid

GUID_DEVINTERFACE_USB_DEVICE = "{A5DCBF10-6530-11D2-901F-00C04FB951ED}"

class Notification:
    def __init__(self, context, cycles_count, target_cycles, batch_window: float | None = None):
        self.context = context
        try:
            self.cycles_count = int(float(cycles_count))
        except (TypeError, ValueError):
            self.cycles_count = 0
        try:
            self.target_cycles = float(target_cycles)
        except (TypeError, ValueError):
            self.target_cycles = 0.0
        self.window = context.window
        self.hwnd = None
        self.hdn = None
        self.class_name = f"DeviceChange_WindowClass_{uuid.uuid4()}"
        try:
            self.batch_window = (
                max(0.0, float(batch_window))
                if batch_window is not None
                else float(DEFAULT_BATCH_WINDOW)
            )
        except (TypeError, ValueError):
            self.batch_window = float(DEFAULT_BATCH_WINDOW)
        self._last_removal_time = None
        self.init_notification_window()
        logger.info(
            "Initialized Notification with cycles_count: %s, target_cycles: %s",
            self.cycles_count,
            self.target_cycles,
        )

    def init_notification_window(self):
        message_map = {win32con.WM_DEVICECHANGE: self.onDeviceChange}
        wc = win32gui.WNDCLASS()
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = self.class_name  # 使用唯一的类名
        wc.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW
        wc.lpfnWndProc = message_map
        win32gui.RegisterClass(wc)  # 由于类名唯一，所以不需要捕获错误

        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow(
            wc.lpszClassName,
            "Device Change",
            style,
            0, 0,
            win32con.CW_USEDEFAULT,
            win32con.CW_USEDEFAULT,
            0, 0,
            wc.hInstance,
            None
        )

        dbt_dev_broadcast_deviceinterface = win32gui_struct.PackDEV_BROADCAST_DEVICEINTERFACE(GUID_DEVINTERFACE_USB_DEVICE)
        self.hdn = win32gui.RegisterDeviceNotification(
            self.hwnd,
            dbt_dev_broadcast_deviceinterface,
            win32con.DEVICE_NOTIFY_WINDOW_HANDLE
        )

    def onDeviceChange(self, hwnd, message, wparam, lparam):
        dbch = win32gui_struct.UnpackDEV_BROADCAST(lparam)
        if wparam == win32con.DBT_DEVICEREMOVECOMPLETE:
            now = time.monotonic()
            if (
                self.batch_window
                and self._last_removal_time is not None
                and now - self._last_removal_time < self.batch_window
            ):
                logger.debug("USB 插拔事件在短时间内重复触发，已合并计数。")
            else:
                self.cycles_count += 1
                self.context.log(
                    f"检测到 USB 设备移除: {dbch.name}，当前插拔次数: {self.cycles_count}"
                )
                self.context.record_count_progress_if_current(
                    self.target_cycles,
                    self.cycles_count,
                    expected_keys={"usb插拔", "s3插拔"},
                )
            self._last_removal_time = now
        elif wparam == win32con.DBT_DEVICEARRIVAL:
            pass
            # 可在此输出调试日志，例如记录设备名与累计插拔次数
        if self.target_cycles and self.cycles_count >= self.target_cycles:
            self.context.record_count_progress_if_current(
                self.target_cycles,
                self.cycles_count,
                expected_keys={"usb插拔", "s3插拔"},
            )
            self.context.log(
                f"USB 插拔任务已完成 {self.cycles_count} 次，目标次数为 {self.target_cycles} 次。"
            )
            win32gui.PostQuitMessage(0)

        return 1

    def messageLoop(self):
        win32gui.PumpMessages()



