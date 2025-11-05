"""USB 插拔监控。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ..devicerm import Notification
import threading

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(
    context: "Patvs_Fuction",
    target_cycles: float,
    usb_done_event: Optional[threading.Event] = None,
    *,
    remaining_cycles: float | None = None,
) -> None:
    """监控 USB 插拔事件，支持断点续跑。"""

    try:
        total_target = float(target_cycles)
    except (TypeError, ValueError):
        total_target = 0.0
    if total_target <= 0:
        context.log("USB 插拔目标次数为 0，自动跳过。")
        if usb_done_event:
            usb_done_event.set()
        else:
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
    completed = max(0.0, total_target - remaining)

    if completed > 0:
        context.log(
            f"USB 插拔已累计 {completed:g} 次，剩余 {max(0.0, total_target - completed):g} 次。"
        )

    notification = Notification(context, completed, total_target)
    context.register_message_loop_shutdown(notification.stop)
    try:
        notification.messageLoop()
    finally:
        context.register_message_loop_shutdown(None)
        if context.msg_loop_thread_id == threading.get_ident():
            context.msg_loop_thread_id = None
        context.log("停止 USB 插拔事件监控.")
        if usb_done_event:
            usb_done_event.set()
        else:
            context.action_complete.set()
