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


class _WxCompat:
    @staticmethod
    def CallAfter(func, *args, **kwargs):
        QtCore.QTimer.singleShot(0, lambda: func(*args, **kwargs))


wx = _WxCompat()
import uuid

GUID_DEVINTERFACE_USB_DEVICE = "{A5DCBF10-6530-11D2-901F-00C04FB951ED}"

class Notification:
    def __init__(self, cycles_count, target_cycles, window):
        self.cycles_count = cycles_count   # 初始化插拔次数
        self.target_cycles = target_cycles  # 目标的插拔次数
        self.window = window
        self.hwnd = None
        self.hdn = None
        self.class_name = f"DeviceChange_WindowClass_{uuid.uuid4()}"
        self.init_notification_window()
        logger.info(f"Initialized Notification with cycles_count: {self.cycles_count}, target_cycles: {self.target_cycles}")

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
            self.cycles_count += 1
            message = f"Device {dbch.name} removed, current count: {self.cycles_count}"
            wx.CallAfter(self.window.add_log_message, message)
        elif wparam == win32con.DBT_DEVICEARRIVAL:
            message = f"Device {dbch.name} arrived, current count: {self.cycles_count}"
            wx.CallAfter(self.window.add_log_message, message)
        if self.cycles_count >= self.target_cycles:
            message = f"检测到已完成设备插拔目标次数: {self.cycles_count}"
            wx.CallAfter(self.window.add_log_message, message)
            win32gui.PostQuitMessage(0)

        return 1

    def messageLoop(self):
        win32gui.PumpMessages()




