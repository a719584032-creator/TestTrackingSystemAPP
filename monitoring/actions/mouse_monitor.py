"""鼠标点击监控。"""
from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from pynput import mouse

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(
    context: "Patvs_Fuction",
    target_cycles: float,
    remaining_cycles: float | None = None,
) -> None:
    """监听鼠标点击事件，完成既定次数后退出，支持断点续跑。"""

    try:
        total_target = float(target_cycles)
    except (TypeError, ValueError):
        total_target = 0.0
    if total_target <= 0:
        context.log("鼠标点击目标次数为 0，自动跳过。")
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

    click_count = max(0.0, total_target - remaining)
    listener_stopped = threading.Event()
    expected_keys = {"鼠标点击"}

    if click_count > 0:
        context.log(
            f"鼠标点击已累计 {click_count:g} 次，剩余 {max(0.0, total_target - click_count):g} 次。"
        )

    def on_click(x, y, button, pressed):
        nonlocal click_count
        if pressed:
            click_count += 1
            context.log(
                f"Mouse clicked at ({x}, {y}) with {button}. Total count: {click_count}"
            )
            context.record_count_progress_if_current(
                total_target, click_count, expected_keys=expected_keys
            )
            if click_count >= total_target:
                context.log("已完成目标点击次数. Exiting...")
                listener_stopped.set()
                return False

    def stop_listener(listener):
        while context.is_running and not listener_stopped.is_set():
            time.sleep(0.1)
        if not listener_stopped.is_set():
            context.log("程序终止，停止鼠标点击事件监控...")
            listener.stop()
            listener_stopped.set()

    try:
        with mouse.Listener(on_click=on_click) as listener:
            stop_thread = threading.Thread(target=stop_listener, args=(listener,))
            stop_thread.start()
            listener.join()
            stop_thread.join()
    finally:
        context.log("停止鼠标点击事件监控")
        context.record_count_progress_if_current(
            total_target, click_count, expected_keys=expected_keys
        )
        context.action_complete.set()
