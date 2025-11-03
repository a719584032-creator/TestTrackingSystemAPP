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
) -> None:
    """监控 USB 插拔事件。"""

    notification = Notification(context, 0, target_cycles)
    try:
        notification.messageLoop()
    finally:
        context.log("停止 USB 插拔事件监控.")
        if usb_done_event:
            usb_done_event.set()
        else:
            context.action_complete.set()
