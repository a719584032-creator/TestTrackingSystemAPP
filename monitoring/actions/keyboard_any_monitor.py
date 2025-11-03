"""任意键盘按键监控。"""
from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from pynput import keyboard

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(context: "Patvs_Fuction", target_cycles: float) -> None:
    """监听任意按键，达到目标次数后退出。"""

    key_count = 0
    listener_stopped = threading.Event()

    def on_press(pressed_key):
        nonlocal key_count
        key_count += 1
        context.log(f"Key pressed: {pressed_key}. Total count: {key_count}")
        context.record_count_progress_if_current(
            target_cycles, key_count, expected_keys={"键盘按键"}
        )
        if key_count >= target_cycles:
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
            target_cycles, key_count, expected_keys={"键盘按键"}
        )
        context.action_complete.set()
