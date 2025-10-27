"""系统音量监控。"""
from __future__ import annotations

import time
from ctypes import POINTER, cast
from typing import TYPE_CHECKING

from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def _get_volume() -> float:
    """读取当前系统主音量。"""

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    return volume.GetMasterVolumeLevelScalar()


def run(context: "Patvs_Fuction", target_change_count: float) -> None:
    """监控系统音量变化次数。"""

    previous_volume = _get_volume()
    change_count = 0
    context.log(f"初始系统音量: {previous_volume * 100:.2f}%")

    while context.is_running and change_count < target_change_count:
        time.sleep(1)
        current_volume = _get_volume()
        if current_volume != previous_volume:
            change_count += 1
            context.log(
                f"音量变化次数: {change_count}, 当前音量: {current_volume * 100:.2f}%"
            )
            previous_volume = current_volume

    if context.is_running:
        context.log("音量变化次数已达到目标次数，退出监控。")
    else:
        context.log("退出音量加减事件监控。")
    context.action_complete.set()
