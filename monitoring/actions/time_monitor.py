"""时间关键字监控逻辑。"""
from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - 仅用于类型检查
    from ..patvs_monitor import Patvs_Fuction


def run(context: "Patvs_Fuction", remaining_seconds: float, total_seconds: float) -> None:
    """执行时间监控，支持断点续跑。"""

    try:
        total_seconds = max(0, int(math.ceil(float(total_seconds))))
    except (TypeError, ValueError):
        total_seconds = 0
    try:
        remaining = max(0, int(math.ceil(float(remaining_seconds))))
    except (TypeError, ValueError):
        remaining = total_seconds

    if total_seconds == 0:
        context.log("时间关键字为 0，视为立即完成。")
        context.log("时间监控已完成，可以提交通过结果")
        context._record_time_progress(0)
        context.action_complete.set()
        return

    spent = total_seconds - remaining
    minutes = total_seconds / 60
    if remaining <= 0:
        context.log("时间监控剩余时间为 0，视为已完成。")
        context.log("时间监控已完成，可以提交通过结果")
        context._record_time_progress(0)
        context.action_complete.set()
        return

    if spent > 0:
        context.log(f"时间监控已累计执行 {spent} 秒，剩余 {remaining} 秒。")
    else:
        context.log(f"该用例需要执行 {minutes:g} 分钟，共 {total_seconds} 秒。")

    try:
        while context.is_running and remaining > 0:
            context.log(f"倒计时：剩余 {remaining} 秒")
            time.sleep(1)
            remaining -= 1
            context._record_time_progress(remaining)
        if context.is_running and remaining == 0:
            context.log("时间监控已完成，可以提交通过结果")
        else:
            context.log("时间监控已停止")
    finally:
        context.log("已停止测试时间监控")
        context._record_time_progress(remaining)
        context.action_complete.set()
