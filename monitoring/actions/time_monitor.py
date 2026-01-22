"""时间关键字监控逻辑。"""
from __future__ import annotations

import datetime
import math
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - 仅用于类型检查
    from ..patvs_monitor import Patvs_Fuction


def run(context: "Patvs_Fuction", start_time: object, total_seconds: float) -> None:
    """执行时间监控：基于开始时间计算时间差，不再倒计时。"""

    try:
        total_seconds = max(0, int(math.ceil(float(total_seconds))))
    except (TypeError, ValueError):
        total_seconds = 0

    if total_seconds == 0:
        context.log("时间关键字为 0，视为立即完成。")
        context.log("时间监控已完成，可以提交通过结果")
        context._record_time_progress(0)
        context.action_complete.set()
        return

    normalized_start = context._normalize_start_time(start_time)
    total_minutes = total_seconds / 60

    def remaining_seconds() -> int:
        elapsed = (datetime.datetime.now() - normalized_start).total_seconds()
        return max(0, int(math.ceil(total_seconds - elapsed)))

    remaining = remaining_seconds()
    if remaining <= 0:
        start_label = normalized_start.strftime("%Y年%m月%d日 %H时%M分%S秒")
        end_label = (normalized_start + datetime.timedelta(seconds=total_seconds)).strftime(
            "%Y年%m月%d日 %H时%M分%S秒"
        )
        context.log(
            f"用例开始时间是 {start_label}，需要到 {end_label} 才能点击pass"
        )
        context.log("时间监控剩余时间为 0，视为已完成。")
        context.log("时间监控已完成，可以提交通过结果")
        context._record_time_progress(0)
        context.action_complete.set()
        return

    start_label = normalized_start.strftime("%Y年%m月%d日 %H时%M分%S秒")
    end_label = (normalized_start + datetime.timedelta(seconds=total_seconds)).strftime(
        "%Y年%m月%d日 %H时%M分%S秒"
    )
    context.log(
        f"用例开始时间是 {start_label}，需要到 {end_label} 才能点击pass"
    )
    try:
        while context.is_running:
            remaining = remaining_seconds()
            if remaining <= 0:
                break
            time.sleep(min(1.0, float(remaining)))
        if context.is_running and remaining <= 0:
            context.log("时间监控已完成，可以提交通过结果")
        else:
            context.log("时间监控已停止")
    finally:
        context.log("已停止测试时间监控")
        context._record_time_progress(max(0, remaining))
        context.action_complete.set()
