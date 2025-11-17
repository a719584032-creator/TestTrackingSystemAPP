"""系统音量监控。"""
from __future__ import annotations

import time
from ctypes import POINTER, cast
from typing import TYPE_CHECKING
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def _read_volume_level() -> float:
    """按照旧实现的方式读取一次音量，不做额外的 COM 生命周期管理。"""
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    return float(volume.GetMasterVolumeLevelScalar())


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

    previous_volume = _read_volume_level()
    context.log(f"初始系统音量: {previous_volume * 100:.2f}%")
    if change_count > 0:
        remaining_to_go = max(0.0, total_target - change_count)
        context.log(f"音量变化已累计 {change_count:g} 次，剩余 {remaining_to_go:g} 次。")

    expected_keys = {"音量"}

    while context.is_running and change_count < total_target:
        time.sleep(1)
        current_volume = _read_volume_level()
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

    context.action_complete.set()
