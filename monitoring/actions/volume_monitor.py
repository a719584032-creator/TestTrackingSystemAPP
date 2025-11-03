"""系统音量监控。"""
from __future__ import annotations

import time
from ctypes import POINTER, cast
from contextlib import suppress
from typing import TYPE_CHECKING

from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

try:  # pragma: no cover - only available on Windows
    import pythoncom
except ImportError:  # pragma: no cover - pywin32 not installed/non-Windows
    pythoncom = None

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def _get_volume() -> float:
    """读取当前系统主音量，确保及时释放 COM 资源。"""

    devices = AudioUtilities.GetSpeakers()
    interface = None
    volume = None
    try:
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        return volume.GetMasterVolumeLevelScalar()
    finally:
        # 在 COM 环境回收前主动释放引用，避免析构延后到 CoUninitialize 之后。
        if volume is not None:
            with suppress(Exception):
                volume.Release()
            volume = None
        if interface is not None:
            with suppress(Exception):
                interface.Release()
            interface = None
        if devices is not None:
            with suppress(Exception):
                devices.Release()
            devices = None


def run(
    context: "Patvs_Fuction",
    target_change_count: float,
    remaining_change_count: float | None = None,
) -> None:
    """监控系统音量变化次数，支持断点续跑。"""

    try:
        total_target = float(target_change_count)
    except (TypeError, ValueError):
        total_target = 0.0
    if total_target <= 0:
        context.log("音量目标次数为 0，自动跳过。")
        context.action_complete.set()
        return

    if remaining_change_count is None:
        remaining = total_target
    else:
        try:
            remaining = float(remaining_change_count)
        except (TypeError, ValueError):
            remaining = total_target
    remaining = max(0.0, min(total_target, remaining))
    change_count = max(0.0, total_target - remaining)

    coinited = False
    if pythoncom is not None:
        try:
            pythoncom.CoInitialize()
            coinited = True
        except Exception as exc:  # pragma: no cover - defensive logging
            context.log(f"初始化音量监控 COM 环境失败: {exc}")

    try:
        previous_volume = _get_volume()
        context.log(f"初始系统音量: {previous_volume * 100:.2f}%")
        if change_count > 0:
            remaining_to_go = max(0.0, total_target - change_count)
            context.log(
                f"音量变化已累计 {change_count:g} 次，剩余 {remaining_to_go:g} 次。"
            )
        expected_keys = {"音量"}

        while context.is_running and change_count < total_target:
            time.sleep(1)
            current_volume = _get_volume()
            if current_volume != previous_volume:
                change_count += 1
                context.log(
                    f"音量变化次数: {change_count}, 当前音量: {current_volume * 100:.2f}%"
                )
                previous_volume = current_volume
                context.record_count_progress_if_current(
                    total_target, change_count, expected_keys=expected_keys
                )

        if context.is_running:
            context.record_count_progress_if_current(
                total_target, change_count, expected_keys=expected_keys
            )
            context.log(
                f"音量变化次数已达到目标次数 ({total_target:g})，总计完成 {change_count} 次，退出监控。"
            )
        else:
            context.log("退出音量加减事件监控。")
    finally:
        context.action_complete.set()
        if pythoncom is not None and coinited:
            pythoncom.CoUninitialize()
