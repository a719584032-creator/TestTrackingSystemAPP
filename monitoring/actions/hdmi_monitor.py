"""显示器（HDMI/DP）插拔监控。"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Tuple

import win32api
import win32con

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction

logger = logging.getLogger(__name__)


def _snapshot_connected_monitors() -> Tuple[str, ...]:
    """返回当前连接并处于活动状态的显示器标识列表。"""

    devices: list[str] = []
    adapter_index = 0
    while True:
        try:
            adapter = win32api.EnumDisplayDevices(None, adapter_index)
        except win32api.error:
            break
        if not adapter:
            break
        adapter_index += 1
        if not (adapter.StateFlags & win32con.DISPLAY_DEVICE_ATTACHED_TO_DESKTOP):
            continue
        monitor_index = 0
        while True:
            try:
                monitor = win32api.EnumDisplayDevices(adapter.DeviceName, monitor_index)
            except win32api.error:
                break
            if not monitor:
                break
            monitor_index += 1
            if monitor.StateFlags & win32con.DISPLAY_DEVICE_ACTIVE:
                monitor_id = monitor.DeviceID or monitor.DeviceName or monitor.DeviceString
                if monitor_id and monitor_id not in devices:
                    devices.append(str(monitor_id))
    devices.sort()
    return tuple(devices)


def run(
    context: "Patvs_Fuction",
    target_cycles: float,
    *,
    remaining_cycles: float | None = None,
    poll_interval: float = 1.5,
) -> None:
    """监控显示器（HDMI/DP）插拔事件，支持断点续跑。"""

    try:
        total_target = float(target_cycles)
    except (TypeError, ValueError):
        total_target = 0.0
    if total_target <= 0:
        context.log("显示器插拔目标次数为 0，自动跳过。")
        context.record_count_progress_if_current(0, 0, expected_keys={"显示器插拔"})
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
    expected_keys = {"显示器插拔"}

    if completed > 0:
        context.log(
            f"显示器插拔已累计 {completed:g} 次，剩余 {max(0.0, total_target - completed):g} 次。"
        )

    try:
        last_snapshot = _snapshot_connected_monitors()
    except Exception as exc:  # pragma: no cover - 系统级调用难以稳定覆盖
        logger.exception("初始化显示器列表失败")
        context.log(f"初始化显示器连接状态失败: {exc}")
        context.action_complete.set()
        return

    readable_initial = "; ".join(last_snapshot) if last_snapshot else "未检测到显示器"
    context.log(f"当前检测到的显示器: {readable_initial}")

    while context.is_running and completed < total_target:
        time.sleep(max(0.1, float(poll_interval)))

        try:
            current_snapshot = _snapshot_connected_monitors()
        except Exception as exc:  # pragma: no cover - 防御系统错误
            logger.warning("读取显示器连接状态失败: %s", exc)
            continue

        if current_snapshot == last_snapshot:
            continue

        completed += 1.0
        context.log(
            f"检测到显示器插拔事件：之前 {len(last_snapshot)} 台，当前 {len(current_snapshot)} 台。"
        )
        if last_snapshot:
            context.log(f"之前: {', '.join(last_snapshot)}")
        if current_snapshot:
            context.log(f"当前: {', '.join(current_snapshot)}")
        last_snapshot = current_snapshot
        context.record_count_progress_if_current(
            total_target, completed, expected_keys=expected_keys
        )
        if completed >= total_target:
            break

    context.record_count_progress_if_current(total_target, completed, expected_keys=expected_keys)
    if completed >= total_target:
        context.log(f"显示器插拔次数已达到目标 ({total_target:g})，退出监控。")
    else:
        context.log("退出显示器插拔监控。")
    context.action_complete.set()
