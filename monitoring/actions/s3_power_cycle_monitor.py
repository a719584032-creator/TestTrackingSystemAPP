"""S3 + 电源插拔组合监控。"""
from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from . import power_plug_monitor, s3_sleep_monitor

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def _sanitize_progress(value, fallback=0.0):
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return fallback


def run(
    context: "Patvs_Fuction",
    start_time,
    target_cycles,
    remaining_cycles: float | None = None,
    *,
    s3_progress: float | None = None,
    power_progress: float | None = None,
) -> None:
    """并行监控 S3 睡眠与电源插拔动作，支持断点续跑。"""

    try:
        total_target = float(target_cycles)
    except (TypeError, ValueError):
        total_target = 0.0

    if total_target <= 0:
        context.log("S3 电源插拔目标次数为 0，自动跳过。")
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

    combined_completed = max(0.0, total_target - remaining)
    s3_completed = _sanitize_progress(s3_progress, combined_completed)
    power_completed = _sanitize_progress(power_progress, combined_completed)
    combined_completed = min(total_target, s3_completed, power_completed)

    context._record_s3_power_progress(
        total_target, s3_completed=s3_completed, power_completed=power_completed
    )

    context.log(f"开始执行监控: S3电源插拔，目标测试次数: {int(total_target)}")
    if combined_completed >= total_target:
        context.log("所有插拔+S3循环已完成！")
        context.action_complete.set()
        return
    if combined_completed > 0:
        context.log(
            "S3 电源插拔已累计完成 "
            f"{combined_completed:g} 次，剩余 {max(0.0, total_target - combined_completed):g} 次。"
        )

    power_remaining = max(0.0, total_target - power_completed)
    power_event = threading.Event()
    power_thread = threading.Thread(
        target=power_plug_monitor.run,
        args=(context, total_target, power_event),
        kwargs={"remaining_cycles": power_remaining},
    )

    s3_event = threading.Event()
    s3_thread = threading.Thread(
        target=s3_sleep_monitor.run,
        args=(context, start_time, total_target, s3_event),
    )

    s3_thread.start()
    power_thread.start()

    last_logged = combined_completed

    while context.is_running:
        with context.state_lock:
            if not context.remaining_actions:
                break
            current = context.remaining_actions[0]
            if context.normalize_action(current.get("name", "")) != "s3电源插拔":
                break
            s3_completed = _sanitize_progress(current.get("s3_progress", s3_completed), s3_completed)
            power_completed = _sanitize_progress(
                current.get("power_progress", power_completed), power_completed
            )
        combined = min(total_target, s3_completed, power_completed)
        if combined > last_logged:
            context.log(f"已完成第{int(combined)}轮插拔+S3")
            last_logged = combined
        if combined >= total_target:
            break
        if s3_event.is_set() and power_event.is_set():
            break
        time.sleep(0.5)

    s3_thread.join()
    power_thread.join()

    with context.state_lock:
        if context.remaining_actions and context.normalize_action(
            context.remaining_actions[0].get("name", "")
        ) == "s3电源插拔":
            s3_completed = _sanitize_progress(
                context.remaining_actions[0].get("s3_progress", s3_completed), s3_completed
            )
            power_completed = _sanitize_progress(
                context.remaining_actions[0].get("power_progress", power_completed),
                power_completed,
            )
            combined_final = min(total_target, s3_completed, power_completed)
        else:
            combined_final = min(total_target, last_logged)

    if combined_final >= total_target:
        context.log("所有插拔+S3循环已完成！")
    else:
        context.log("S3 电源插拔监控已终止。")

    context.action_complete.set()
