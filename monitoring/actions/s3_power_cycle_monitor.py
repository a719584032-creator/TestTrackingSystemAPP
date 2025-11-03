"""S3 + 电源插拔组合监控。"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from . import power_plug_monitor, s3_sleep_monitor

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(
    context: "Patvs_Fuction",
    start_time,
    target_cycles,
    remaining_cycles: float | None = None,
) -> None:
    """顺序执行 S3 睡眠与电源插拔动作，支持断点续跑。"""

    try:
        total_target = int(float(target_cycles))
    except (TypeError, ValueError):
        total_target = 0

    if total_target <= 0:
        context.log("S3 电源插拔目标次数为 0，自动跳过。")
        context.action_complete.set()
        return

    if remaining_cycles is None:
        remaining = float(total_target)
    else:
        try:
            remaining = float(remaining_cycles)
        except (TypeError, ValueError):
            remaining = float(total_target)
    remaining = max(0.0, min(float(total_target), remaining))
    completed = int(max(0.0, float(total_target) - remaining))

    context.log(f"开始执行监控: S3电源插拔，目标测试次数: {total_target}")
    if completed > 0:
        context.log(
            f"S3 电源插拔已累计完成 {completed} 次，剩余 {max(0, total_target - completed)} 次。"
        )

    for index in range(completed, total_target):
        s3_done_event = threading.Event()
        s3_thread = threading.Thread(
            target=s3_sleep_monitor.run,
            args=(context, start_time, index + 1, s3_done_event),
        )
        s3_thread.start()
        s3_done_event.wait()
        s3_thread.join()

        power_done_event = threading.Event()
        power_thread = threading.Thread(
            target=power_plug_monitor.run,
            args=(context, 1, power_done_event),
        )
        power_thread.start()
        power_done_event.wait()
        power_thread.join()

        context.log(f"已完成第{index + 1}轮插拔+S3")

    context.log("所有插拔+S3循环已完成！")
    context.action_complete.set()
