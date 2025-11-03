"""特定键盘按键监控。"""
from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Optional

from pynput import keyboard

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(context: "Patvs_Fuction", target_cycles: float, key_name: Optional[str] = None) -> None:
    """监听特定按键，达到目标次数后退出。"""

    key_count = 0
    key = context.KEY_MAPPING.get(key_name.lower()) if key_name else None
    listener_stopped = threading.Event()
    expected_keys = {key_name} if key_name else {"键盘按键"}

    def on_press(pressed_key):
        nonlocal key_count
        if key is None or pressed_key == key:
            key_count += 1
            context.log(f"Key pressed: {pressed_key}. Total count: {key_count}")
            context.record_count_progress_if_current(
                target_cycles, key_count, expected_keys=expected_keys
            )
        if key_count >= target_cycles:
            context.log("Reached target keystroke count. Exiting...")
            listener_stopped.set()
            return False

    def stop_listener(listener):
        while context.is_running and not listener_stopped.is_set():
            time.sleep(0.1)
        if not listener_stopped.is_set():
            context.log("Stop event triggered. Exiting listener...")
            listener.stop()
            listener_stopped.set()

    try:
        with keyboard.Listener(on_press=on_press) as listener:
            stop_thread = threading.Thread(target=stop_listener, args=(listener,))
            stop_thread.start()
            listener.join()
            stop_thread.join()
    finally:
        context.log("Stopped monitoring keystrokes.")
        context.record_count_progress_if_current(
            target_cycles, key_count, expected_keys=expected_keys
        )
        context.action_complete.set()
