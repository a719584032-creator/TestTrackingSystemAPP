"""S3 + 电源插拔组合监控。"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from . import power_plug_monitor, s3_sleep_monitor

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(context: "Patvs_Fuction", start_time, target_cycles) -> None:
    """顺序执行 S3 睡眠与电源插拔动作。"""

    context.log(f"开始执行监控: S3电源插拔，目标测试次数: {target_cycles}")
    for index in range(int(target_cycles)):
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
            target=power_plug_monitor.run, args=(context, 1, power_done_event)
        )
        power_thread.start()
        power_done_event.wait()
        power_thread.join()

        context.log(f"已完成第{index + 1}轮插拔+S3")

    context.log("所有插拔+S3循环已完成！")
    context.action_complete.set()
