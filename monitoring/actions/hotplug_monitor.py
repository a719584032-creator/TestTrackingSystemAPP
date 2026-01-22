"""设备接口级别热插拔监控。"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import TYPE_CHECKING, Iterable, Optional, Tuple

import pywintypes
import win32api
import win32con
import win32gui
import win32gui_struct

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction

logger = logging.getLogger(__name__)

GUID_DEVINTERFACE_USB_DEVICE = "{A5DCBF10-6530-11D2-901F-00C04FB951ED}"
GUID_DEVINTERFACE_DISK = "{53F56307-B6BF-11D0-94F2-00A0C91EFB8B}"
#GUID_DEVINTERFACE_HID = "{4D1E55B2-F16F-11CF-88CB-001111000030}"
GUID_DEVINTERFACE_NET = "{CAC88484-7515-4C03-82E6-71A87ABAC361}"

DEFAULT_CLASS_GUIDS: Tuple[str, ...] = (
    GUID_DEVINTERFACE_USB_DEVICE,
    GUID_DEVINTERFACE_DISK,
    # GUID_DEVINTERFACE_HID,
    GUID_DEVINTERFACE_NET,
)
DEFAULT_BATCH_WINDOW = 3


def _normalize_key(value) -> str:
    try:
        return str(value).lower().replace(" ", "")
    except Exception:
        return ""


class InterfaceNotification:
    def __init__(
        self,
        context,
        cycles_count,
        target_cycles,
        *,
        class_guids=None,
        expected_keys=None,
        action_label="设备接口热插拔",
        log_arrival=False,
        dedupe_window=0.6,
        batch_window=DEFAULT_BATCH_WINDOW,
    ):
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
        self.hdn: list[int] = []
        self.class_name = f"DeviceChange_WindowClass_{uuid.uuid4()}"
        self.class_guids = tuple(class_guids or DEFAULT_CLASS_GUIDS)
        self.expected_keys = {
            _normalize_key(key)
            for key in (expected_keys or {"hotplug"})
            if key is not None
        }
        self.action_label = action_label
        self.log_arrival = bool(log_arrival)
        try:
            self.dedupe_window = max(0.0, float(dedupe_window))
        except (TypeError, ValueError):
            self.dedupe_window = 0.0
        try:
            self.batch_window = max(0.0, float(batch_window))
        except (TypeError, ValueError):
            self.batch_window = 0.0
        self._event_cache: dict[tuple[int, str], float] = {}
        self._last_removal_time: float | None = None
        self.init_notification_window()
        logger.info(
            "Initialized Hotplug Notification with cycles_count: %s, target_cycles: %s",
            self.cycles_count,
            self.target_cycles,
        )

    def init_notification_window(self):
        # 通过隐藏窗口接收设备变更广播
        message_map = {win32con.WM_DEVICECHANGE: self.onDeviceChange}
        wc = win32gui.WNDCLASS()
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = self.class_name
        wc.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW
        wc.lpfnWndProc = message_map
        win32gui.RegisterClass(wc)

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
            None,
        )

        # 为各类设备接口注册通知，捕获插拔事件
        for guid in self.class_guids:
            try:
                dbt_dev_broadcast_deviceinterface = (
                    win32gui_struct.PackDEV_BROADCAST_DEVICEINTERFACE(guid)
                )
                handle = win32gui.RegisterDeviceNotification(
                    self.hwnd,
                    dbt_dev_broadcast_deviceinterface,
                    win32con.DEVICE_NOTIFY_WINDOW_HANDLE,
                )
                if handle:
                    self.hdn.append(handle)
                else:
                    logger.warning(
                        "RegisterDeviceNotification returned NULL for %s", guid
                    )
            except pywintypes.error as exc:
                logger.warning(
                    "RegisterDeviceNotification failed for %s: %s", guid, exc
                )
        if not self.hdn:
            logger.warning(
                "No device interface notification registered, hotplug monitoring may not work."
            )

    def onDeviceChange(self, hwnd, message, wparam, lparam):
        try:
            dbch = win32gui_struct.UnpackDEV_BROADCAST(lparam)
        except (pywintypes.error, ValueError) as exc:
            logger.debug("Failed to unpack device broadcast: %s", exc)
            return 1
        device_name = (getattr(dbch, "name", None) or "Unknown device").strip()
        device_key = device_name.lower()
        cache_key = (int(wparam), device_key)
        now = time.monotonic()
        # 同一设备短时间重复事件（如到达+配置）需要去重
        if (
            self.dedupe_window
            and cache_key in self._event_cache
            and now - self._event_cache[cache_key] < self.dedupe_window
        ):
            logger.debug("Deduping hotplug event: %s", device_name)
            return 1
        self._event_cache[cache_key] = now
        if wparam == win32con.DBT_DEVICEREMOVECOMPLETE:
            merged = False
            if (
                self.batch_window
                and self._last_removal_time is not None
                and now - self._last_removal_time < self.batch_window
            ):
                merged = True
            self._last_removal_time = now
            if merged:
                logger.debug(
                    f"检测到 {self.action_label}移除: {device_name}，已合并为同一次插拔"
                )
            else:
                self.cycles_count += 1
                logger.debug(
                    f"检测到 {self.action_label}移除: {device_name}，当前插拔次数: {self.cycles_count}"
                )
                self.context.log(f"当前插拔次数: {self.cycles_count}")
                self.context.record_count_progress_if_current(
                    self.target_cycles,
                    self.cycles_count,
                    expected_keys=self.expected_keys,
                )
        elif wparam == win32con.DBT_DEVICEARRIVAL and self.log_arrival:
            logger.debug(f"检测到 {self.action_label}接入: {device_name}")

        # 达到目标次数，记录进度并退出消息循环
        if self.target_cycles and self.cycles_count >= self.target_cycles:
            self.context.record_count_progress_if_current(
                self.target_cycles,
                self.cycles_count,
                expected_keys=self.expected_keys,
            )
            self.context.log(
                f"{self.action_label}任务已完成 {self.cycles_count} 次，目标次数为 {self.target_cycles} 次。"
            )
            win32gui.PostQuitMessage(0)

        return 1

    def messageLoop(self):
        try:
            # 阻塞等待窗口消息，直到 PostQuitMessage
            win32gui.PumpMessages()
        finally:
            self._cleanup()

    def _cleanup(self):
        # 释放已注册的通知和窗口句柄
        for handle in self.hdn or []:
            try:
                win32gui.UnregisterDeviceNotification(handle)
            except pywintypes.error as exc:
                logger.debug("Failed to unregister device notification: %s", exc)
        if self.hwnd:
            try:
                win32gui.DestroyWindow(self.hwnd)
            except pywintypes.error as exc:
                logger.debug("Failed to destroy notification window: %s", exc)
            self.hwnd = None


def run(
    context: "Patvs_Fuction",
    target_cycles: float,
    hotplug_done_event: Optional[threading.Event] = None,
    *,
    remaining_cycles: float | None = None,
    class_guids: Iterable[str] = DEFAULT_CLASS_GUIDS,
) -> None:
    """监控接口级别的设备热插拔事件，覆盖 Type-C、USB-A 等。"""

    try:
        total_target = float(target_cycles)
    except (TypeError, ValueError):
        total_target = 0.0
    if total_target <= 0:
        # 未配置目标次数时直接跳过监控
        context.log("设备接口热插拔目标次数为 0，自动跳过。")
        if hotplug_done_event:
            hotplug_done_event.set()
        else:
            context.action_complete.set()
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
            f"设备接口热插拔已累计 {completed:g} 次，剩余 {max(0.0, total_target - completed):g} 次。"
        )

    # 创建设备热插拔通知窗口并进入消息循环
    notification = InterfaceNotification(
        context,
        completed,
        total_target,
        class_guids=tuple(class_guids) if class_guids else DEFAULT_CLASS_GUIDS,
        expected_keys={"hotplug"},
        action_label="设备接口热插拔",
        log_arrival=True,
        dedupe_window=0.6,
    )
    try:
        notification.messageLoop()
    finally:
        context.clear_message_loop_thread(threading.get_ident())
        context.log("停止设备接口热插拔监控.")
        if hotplug_done_event:
            hotplug_done_event.set()
        else:
            context.action_complete.set()
