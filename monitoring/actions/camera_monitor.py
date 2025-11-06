"""摄像头开关监控（前3个摄像头，任意一个算一次）。"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import cv2

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(
    context: "Patvs_Fuction",
    target_cycles: float,
    remaining_cycles: float | None = None,
) -> None:
    """检测前3个摄像头的开关周期次数；任意一个摄像头完成一次开关都计数。"""

    # 目标次数处理
    try:
        total_target = float(target_cycles)
    except (TypeError, ValueError):
        total_target = 0.0
    if total_target <= 0:
        context.log("摄像头开关目标次数为 0，自动跳过。")
        context.record_count_progress_if_current(0, 0, expected_keys={"摄像头", "camera"})
        context.log("退出摄像头开关事件监控。")
        context.action_complete.set()
        return

    # 断点续跑：已完成/剩余次数
    if remaining_cycles is None:
        remaining = total_target
    else:
        try:
            remaining = float(remaining_cycles)
        except (TypeError, ValueError):
            remaining = total_target
    remaining = max(0.0, min(total_target, remaining))
    cycle_count = max(0.0, total_target - remaining)

    if cycle_count > 0:
        context.log(
            f"摄像头开关已累计 {cycle_count:g} 次，"
            f"剩余 {max(0.0, total_target - cycle_count):g} 次。"
        )

    # 只监控前三个摄像头
    camera_indices = [0, 1, 2]
    expected_keys = {"摄像头", "camera"}

    # 为每个摄像头记录上次可读状态；None 表示未知（首轮不判断跃迁）
    last_state = {idx: None for idx in camera_indices}
    # 全局“已开始一次开关”的标记：出现任一设备 True->False 就置 True，
    # 出现任一设备 False->True 就完成一次周期并清零
    cycle_started = False

    def probe(idx: int) -> bool:
        # 读一帧判断是否可用；有的平台 isOpened 为真但读帧失败，使用 read 更稳妥
        cap = cv2.VideoCapture(idx)
        ret, _ = cap.read()
        cap.release()
        return bool(ret)

    while context.is_running and cycle_count < total_target:
        # 扫描 0/1/2 三个摄像头
        current = {idx: probe(idx) for idx in camera_indices}

        # 遍历每个摄像头的状态变化
        for idx in camera_indices:
            prev = last_state[idx]
            cur = current[idx]

            if prev is None:
                # 首次有了基线
                last_state[idx] = cur
                continue

            # 任一设备的 True->False：标记“开始”
            if (not cycle_started) and prev and (not cur):
                cycle_started = True
                context.log(f"[cam {idx}] 检测到被占用，开关周期开始。")

            # 任一设备的 False->True：若已开始，则完成一个周期
            elif cycle_started and (not prev) and cur:
                cycle_count += 1.0
                cycle_started = False
                context.log(f"[cam {idx}] 释放，完成一个开关周期！当前周期数：{cycle_count:g}")
                context.record_count_progress_if_current(
                    total_target, cycle_count, expected_keys=expected_keys
                )
                # 达到目标就尽快退出
                if cycle_count >= total_target:
                    break

            last_state[idx] = cur

        if cycle_count >= total_target:
            context.log(f"摄像头开关周期数已达到目标值 ({total_target:g})，退出检测。")
            break

        time.sleep(1)

    context.record_count_progress_if_current(
        total_target, cycle_count, expected_keys=expected_keys
    )
    context.log("退出摄像头开关事件监控。")
    context.action_complete.set()
