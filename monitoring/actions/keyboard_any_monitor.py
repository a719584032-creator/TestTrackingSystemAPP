"""任意键盘按键监控。"""
from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from pynput import keyboard

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(
    context: "Patvs_Fuction",
    target_cycles: float,
    remaining_cycles: float | None = None,
) -> None:
    """监听任意按键，达到目标次数后退出，支持断点续跑。"""

    try:
        total_target = float(target_cycles)
    except (TypeError, ValueError):
        total_target = 0.0
    if total_target <= 0:
        context.log("键盘按键目标次数为 0，自动跳过。")
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

    key_count = max(0.0, total_target - remaining)
    listener_stopped = threading.Event()

    if key_count > 0:
        context.log(
            f"键盘按键已累计 {key_count:g} 次，剩余 {max(0.0, total_target - key_count):g} 次。"
        )

    def on_press(pressed_key):
        nonlocal key_count
        key_count += 1
        context.log(f"Key pressed: {pressed_key}. Total count: {key_count}")
        context.record_count_progress_if_current(
            total_target, key_count, expected_keys={"键盘按键"}
        )
        if key_count >= total_target:
            context.log("检测到已完成目标键盘按键次数. Exiting...")
            listener_stopped.set()
            return False

    def stop_listener(listener):
        while context.is_running and not listener_stopped.is_set():
            time.sleep(0.1)
        if not listener_stopped.is_set():
            context.log("程序终止，停止键盘按键监控...")
            listener.stop()
            listener_stopped.set()

    try:
        with keyboard.Listener(on_press=on_press) as listener:
            stop_thread = threading.Thread(target=stop_listener, args=(listener,))
            stop_thread.start()
            listener.join()
            stop_thread.join()
    finally:
        context.log("停止键盘按键监控")
        context.record_count_progress_if_current(
            total_target, key_count, expected_keys={"键盘按键"}
        )
        context.action_complete.set()
