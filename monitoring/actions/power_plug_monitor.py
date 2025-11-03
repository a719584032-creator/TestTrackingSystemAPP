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
) -> None:
    """监控电源插拔次数。"""

    plugged_in_last_state = None
    plug_unplug_cycles = 0
    try:
        while context.is_running and plug_unplug_cycles < target_cycles:
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
                    context._record_count_progress(target_cycles, plug_unplug_cycles)
                    if plug_unplug_cycles >= target_cycles:
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
