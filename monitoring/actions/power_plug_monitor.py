"""电源插拔监控逻辑。"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

import psutil
import threading

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(
    context: "Patvs_Fuction",
    target_cycles: float,
    power_done_event: Optional[threading.Event] = None,
    *,
    remaining_cycles: float | None = None,
) -> None:
    """监控电源插拔次数，支持断点续跑。"""

    try:
        total_target = float(target_cycles)
    except (TypeError, ValueError):
        total_target = 0.0
    if total_target <= 0:
        context.log("电源插拔目标次数为 0，自动跳过。")
        if power_done_event:
            power_done_event.set()
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

    plugged_in_last_state = None
    plug_unplug_cycles = max(0.0, total_target - remaining)
    if plug_unplug_cycles > 0:
        context.log(
            f"电源插拔已累计 {plug_unplug_cycles:g} 次，剩余 {max(0.0, total_target - plug_unplug_cycles):g} 次。"
        )
    try:
        while context.is_running and plug_unplug_cycles < total_target:
            battery = psutil.sensors_battery()
            if not battery:
                context.logger.error("No battery information found")
                break

            plugged_in = battery.power_plugged
            if plugged_in_last_state is None:
                plugged_in_last_state = plugged_in

            if plugged_in != plugged_in_last_state:
                plugged_in_last_state = plugged_in
                if not plugged_in:
                    plug_unplug_cycles += 1
                    context.log(f"电源插拔完成次数: {plug_unplug_cycles}")
                    context._record_count_progress(total_target, plug_unplug_cycles)
                    if plug_unplug_cycles >= total_target:
                        context.log(
                            f"已完成目标插拔次数:{plug_unplug_cycles} ，Exiting...."
                        )
                        break
            time.sleep(1)
    finally:
        context.log("已停止电源插拔监控")
        if power_done_event:
            power_done_event.set()
        else:
            context.action_complete.set()
