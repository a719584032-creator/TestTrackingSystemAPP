"""显示器亮度监控（前三个显示器，任意一个完成关→开算一次）。"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import screen_brightness_control as sbc

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(
    context: "Patvs_Fuction",
    target_cycles: float,
    remaining_cycles: float | None = None,
) -> None:
    """检测前三个显示器的关→开周期次数；任意一个完成一次周期即全局计数+1，支持断点续跑。"""

    # 目标次数处理
    try:
        total_target = float(target_cycles)
    except (TypeError, ValueError):
        total_target = 0.0
    if total_target <= 0:
        context.log("显示器开关目标次数为 0，自动跳过。")
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
    off_on_count = max(0.0, total_target - remaining)

    if off_on_count > 0:
        context.log(
            f"显示器关→开已累计 {off_on_count:g} 次，"
            f"剩余 {max(0.0, total_target - off_on_count):g} 次。"
        )

    # 只监控前三个显示器
    monitor_indices = [0, 1, 2]
    expected_keys = {"显示器", "monitor", "brightness"}

    # 每个显示器的上次“是否点亮”状态；None 表示未知（首轮不判断跃迁）
    last_state: dict[int, bool | None] = {idx: None for idx in monitor_indices}
    # 全局：是否已经进入了一次“关→开”周期（某个显示器刚刚从 ON 变 OFF）
    cycle_started = False

    def probe(idx: int) -> bool:
        """
        返回该显示器当前是否“点亮”(ON)：
        - 能读到亮度且 > 0 视为 True；
        - 读不到/异常/0 视为 False。
        """
        try:
            val = sbc.get_brightness(display=idx)
            # library 在不同平台可能返回 int 或 [int]；做兼容处理
            if isinstance(val, (list, tuple)):
                val = val[0] if val else 0
            on = bool(val) and (int(val) > 0)
            return on
        except Exception:
            return False

    POLL_INTERVAL_SEC = 2  # 适当调大可减少对系统/驱动干扰

    while context.is_running and off_on_count < total_target:
        # 当前轮询结果
        current: dict[int, bool] = {idx: probe(idx) for idx in monitor_indices}

        for idx in monitor_indices:
            prev = last_state[idx]
            cur = current[idx]

            if prev is None:
                # 建立基线
                last_state[idx] = cur
                continue

            # 任一显示器 ON→OFF：标记一次关→开周期“开始”
            if (not cycle_started) and prev and (not cur):
                cycle_started = True
                context.log(f"[mon {idx}] 检测到关闭（ON→OFF），周期开始。")

            # 任一显示器 OFF→ON：若已开始，则完成一次周期并计数
            elif cycle_started and (not prev) and cur:
                off_on_count += 1.0
                cycle_started = False
                context.log(f"[mon {idx}] 重新点亮（OFF→ON），完成一个关→开周期！当前累计：{off_on_count:g}")
                context.record_count_progress_if_current(
                    total_target, off_on_count, expected_keys=expected_keys
                )
                if off_on_count >= total_target:
                    break

            # 更新该显示器的上次状态
            last_state[idx] = cur

        if off_on_count >= total_target:
            context.log(f"显示器关→开周期数已达到目标值 ({total_target:g})，退出监控。")
            break

        time.sleep(POLL_INTERVAL_SEC)

    if context.is_running:
        context.record_count_progress_if_current(
            total_target, off_on_count, expected_keys=expected_keys
        )
        context.log(
            f"显示器关→开次数已达到目标次数 ({total_target:g})，总计完成 {off_on_count:g} 次，退出监控。"
        )
    else:
        context.log("退出显示器开关监控。")
    context.action_complete.set()
