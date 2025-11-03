"""显示器亮度监控。"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import screen_brightness_control as sbc

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(context: "Patvs_Fuction", target_cycles: float) -> None:
    """检测显示器亮度变化，统计关闭周期。"""

    previous_brightness = None
    off_cycle_count = 0
    was_display_on = True
    expected_keys = {"显示器"}

    while context.is_running and off_cycle_count < target_cycles:
        try:
            current_brightness = sbc.get_brightness(display=0)
            context.log(f"当前显示器亮度: {current_brightness}")
            if current_brightness == 0:
                raise RuntimeError("Brightness is 0, assuming display is off.")

            if previous_brightness is None:
                previous_brightness = current_brightness

            was_display_on = True
        except Exception as exc:
            context.log(f"检测到屏幕已关闭: {exc}")
            if was_display_on and previous_brightness:
                off_cycle_count += 1
                context.log(f"显示器关闭周期完成: {off_cycle_count} 次")
                context.record_count_progress_if_current(
                    target_cycles, off_cycle_count, expected_keys=expected_keys
                )
            was_display_on = False
            previous_brightness = None

        time.sleep(5)

    if context.is_running:
        context.record_count_progress_if_current(
            target_cycles, off_cycle_count, expected_keys=expected_keys
        )
        context.log(
            f"显示器开关次数已达到目标次数 ({target_cycles:g})，总计完成 {off_cycle_count} 次，退出监控。"
        )
    else:
        context.log("退出显示器开关监控。")
    context.action_complete.set()
