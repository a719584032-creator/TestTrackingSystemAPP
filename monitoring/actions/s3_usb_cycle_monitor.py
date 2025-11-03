"""S3 + USB 插拔组合监控。"""
from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from . import s3_sleep_monitor, usb_monitor

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(
    context: "Patvs_Fuction",
    start_time,
    s3_target_cycles,
    usb_target_cycles,
    remaining_cycles: float | None = None,
) -> None:
    """并行监控 S3 事件与 USB 插拔，支持断点续跑。"""

    try:
        total_target = float(usb_target_cycles)
    except (TypeError, ValueError):
        total_target = 0.0
    if remaining_cycles is None:
        remaining_usb = total_target
    else:
        try:
            remaining_usb = float(remaining_cycles)
        except (TypeError, ValueError):
            remaining_usb = total_target
    remaining_usb = max(0.0, min(total_target, remaining_usb))
    completed = max(0.0, total_target - remaining_usb)
    if completed > 0:
        context.log(
            f"S3 + USB 插拔已累计完成 {completed:g} 次，剩余 {max(0.0, total_target - completed):g} 次。"
        )

    s3_done_event = threading.Event()
    usb_done_event = threading.Event()

    s3_thread = threading.Thread(
        target=s3_sleep_monitor.run,
        args=(context, start_time, s3_target_cycles, s3_done_event),
    )
    usb_thread = threading.Thread(
        target=usb_monitor.run,
        args=(context, usb_target_cycles, usb_done_event),
        kwargs={"remaining_cycles": remaining_usb},
    )

    s3_thread.start()
    usb_thread.start()
    context.msg_loop_thread_id = usb_thread.ident

    while not (s3_done_event.is_set() and usb_done_event.is_set()):
        time.sleep(0.5)

    context.action_complete.set()
    s3_thread.join()
    usb_thread.join()
    context.log("S3 和 USB 插拔监控已完成。")
