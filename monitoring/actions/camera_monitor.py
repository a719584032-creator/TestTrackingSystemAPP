"""摄像头开关监控。"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import cv2

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(context: "Patvs_Fuction", target_cycles: float) -> None:
    """检测摄像头被占用与释放的周期次数。"""

    cycle_count = 0
    last_camera_state = None
    cycle_started = False

    while context.is_running and cycle_count < target_cycles:
        cap = cv2.VideoCapture(0)
        ret, _ = cap.read()
        cap.release()
        current_camera_state = ret

        if last_camera_state is not None:
            if not cycle_started and last_camera_state and not current_camera_state:
                cycle_started = True
                context.log("检测到摄像头被占用，开关周期开始。")
            elif cycle_started and not last_camera_state and current_camera_state:
                cycle_count += 1
                cycle_started = False
                context.log(f"检测到摄像头可以调用，完成一个开关周期！当前周期数：{cycle_count}")

        last_camera_state = current_camera_state
        if cycle_count >= target_cycles:
            context.log(f"摄像头开关周期数已达到目标值 ({target_cycles})，退出检测。")
            break
        time.sleep(1)

    context.log("退出摄像头开关事件监控。")
    context.action_complete.set()
