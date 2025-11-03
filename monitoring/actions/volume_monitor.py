"""系统音量监控。"""
from __future__ import annotations

import time
from ctypes import POINTER, cast
from typing import TYPE_CHECKING
from contextlib import suppress
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

try:  # pragma: no cover - only available on Windows
    import pythoncom
except ImportError:  # pragma: no cover - pywin32 not installed/non-Windows
    pythoncom = None

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def _open_endpoint():
    """打开并返回 (devices, volume) 两个 COM 对象，调用方负责 _close_endpoint 释放。"""
    devices = AudioUtilities.GetSpeakers()  # IMMDevice
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))  # IAudioEndpointVolume*
    return devices, volume

def _close_endpoint(devices, volume):
    """显式释放 COM 对象，避免依赖 __del__ 在 CoUninitialize 之后再释放。"""
    with suppress(Exception):
        if volume is not None:
            volume.Release()
    with suppress(Exception):
        if devices is not None:
            devices.Release()


def run(
    context: "Patvs_Fuction",
    target_change_count: float,
    remaining_change_count: float | None = None,
) -> None:
    # === 参数与剩余次数计算，保持不变 ===
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

    # === COM 初始化 ===
    coinited = False
    if pythoncom is not None:
        try:
            pythoncom.CoInitialize()
            coinited = True
        except Exception as exc:
            context.log(f"初始化音量监控 COM 环境失败: {exc}")

    devices = None
    volume = None
    try:
        # === 只打开一次端点，循环内复用 ===
        devices, volume = _open_endpoint()

        previous_volume = float(volume.GetMasterVolumeLevelScalar())
        context.log(f"初始系统音量: {previous_volume * 100:.2f}%")
        if change_count > 0:
            remaining_to_go = max(0.0, total_target - change_count)
            context.log(f"音量变化已累计 {change_count:g} 次，剩余 {remaining_to_go:g} 次。")

        expected_keys = {"音量"}

        while context.is_running and change_count < total_target:
            time.sleep(1)
            current_volume = float(volume.GetMasterVolumeLevelScalar())
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
        # 先释放所有 COM 指针，再反初始化 COM
        _close_endpoint(devices, volume)
        context.action_complete.set()
        if pythoncom is not None and coinited:
            with suppress(Exception):
                pythoncom.CoUninitialize()
