"""摄像头开关监控。"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import cv2

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


MAX_MONITORED_DEVICES = 3


def run(
    context: "Patvs_Fuction",
    target_cycles: float,
    remaining_cycles: float | None = None,
) -> None:
    """检测摄像头被占用与释放的周期次数，支持断点续跑。"""

    try:
        total_target = float(target_cycles)
    except (TypeError, ValueError):
        total_target = 0.0
    if total_target <= 0:
        context.log("摄像头开关目标次数为 0，自动跳过。")
        context.record_count_progress_if_current(
            0, 0, expected_keys={"摄像头", "camera"}
        )
        context.log("退出摄像头开关事件监控。")
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

    cycle_count = max(0.0, total_target - remaining)
    device_states: list[bool | None] = [None] * MAX_MONITORED_DEVICES
    cycles_started = [False] * MAX_MONITORED_DEVICES
    expected_keys = {"摄像头", "camera"}

    if cycle_count > 0:
        context.log(
            f"摄像头开关已累计 {cycle_count:g} 次，剩余 {max(0.0, total_target - cycle_count):g} 次。"
        )

    while context.is_running and cycle_count < total_target:
        for device_index in range(MAX_MONITORED_DEVICES):
            cap = cv2.VideoCapture(device_index)
            try:
                if cap.isOpened():
                    ret, _ = cap.read()
                else:
                    ret = False
            except Exception:
                ret = False
            finally:
                cap.release()

            current_state = bool(ret)
            previous_state = device_states[device_index]
            device_states[device_index] = current_state

            if previous_state is None:
                continue

            if not cycles_started[device_index] and previous_state and not current_state:
                cycles_started[device_index] = True
                context.log(f"检测到摄像头 {device_index} 被占用，开关周期开始。")
            elif (
                cycles_started[device_index]
                and not previous_state
                and current_state
            ):
                cycle_count += 1
                cycles_started[device_index] = False
                context.log(
                    f"检测到摄像头 {device_index} 可以调用，完成一个开关周期！当前周期数：{cycle_count}"
                )
                context.record_count_progress_if_current(
                    total_target, cycle_count, expected_keys=expected_keys
                )

            if cycle_count >= total_target:
                break

        if cycle_count >= total_target:
            context.log(f"摄像头开关周期数已达到目标值 ({total_target})，退出检测。")
            break
        time.sleep(1)

    context.record_count_progress_if_current(
        total_target, cycle_count, expected_keys=expected_keys
    )
    context.log("退出摄像头开关事件监控。")
    context.action_complete.set()
