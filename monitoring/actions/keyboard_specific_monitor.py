"""特定键盘按键监控。"""
from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Optional

from pynput import keyboard

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(
    context: "Patvs_Fuction",
    target_cycles: float,
    key_name: Optional[str] = None,
    remaining_cycles: float | None = None,
) -> None:
    """单键监控入口（已退化为任意键统计，兼容历史调用），支持断点续跑。"""

    try:
        total_target = float(target_cycles)
    except (TypeError, ValueError):
        total_target = 0.0
    if total_target <= 0:
        context.log("特定键监控目标次数为 0，自动跳过。")
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
    expected_keys = {"键盘按键"}

    if key_name:
        context.log(f"单键监控已关闭，改为统计任意键。原始目标键: {key_name}")

    if key_count > 0:
        context.log(
            f"{key_name or '键盘按键'} 已累计 {key_count:g} 次，剩余 {max(0.0, total_target - key_count):g} 次。"
        )

    def on_press(pressed_key):
        nonlocal key_count
        key_count += 1
        context.log(f"Key pressed: {pressed_key}. Total count: {key_count}")
        context.record_count_progress_if_current(
            total_target, key_count, expected_keys=expected_keys
        )
        if key_count >= total_target:
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
            total_target, key_count, expected_keys=expected_keys
        )
        context.action_complete.set()
