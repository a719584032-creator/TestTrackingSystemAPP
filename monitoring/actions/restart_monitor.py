"""系统重启事件监控。"""
from __future__ import annotations

import datetime
import time
from typing import TYPE_CHECKING

import win32evtlog

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction

DEFAULT_BATCH_WINDOW = 10.0


def _advance_start_time(current_time):
    if DEFAULT_BATCH_WINDOW <= 0:
        return current_time
    try:
        return current_time + datetime.timedelta(seconds=DEFAULT_BATCH_WINDOW)
    except Exception:
        return current_time


def _get_event_time(event):
    return getattr(event, "TimeWritten", None) or getattr(event, "TimeGenerated", None)


def run(context: "Patvs_Fuction", start_time, target_cycles) -> None:
    """统计并监控 1074 重启事件。"""

    try:
        target_cycles = float(target_cycles)
    except (TypeError, ValueError):
        target_cycles = 0.0
    if target_cycles <= 0:
        context.log("restart 目标次数为 0，自动跳过。")
        context.action_complete.set()
        return

    next_start_time, total = context._bootstrap_event_progress(
        start_time,
        lambda event: (event.EventID & 0xFFFF) == 1074,
        batch_window=DEFAULT_BATCH_WINDOW,
        event_time_getter=_get_event_time,
    )
    if total:
        context.record_next_action_start_time(next_start_time)
    log_num = total
    context._record_count_progress(target_cycles, total, action_key="restart")
    if total:
        context.log(
            f"restart 已累计完成 {total} 次，剩余 {int(max(0, target_cycles - total))} 次。"
        )
    if total >= target_cycles:
        context.log(f"已完成目标 restart 次数: {int(total)}")
        context.action_complete.set()
        return

    def reopen_event_log():
        try:
            return win32evtlog.OpenEventLog(None, "System")
        except Exception as exc:
            context.log(f"Failed to open event log: {exc}")
            return None

    hand = reopen_event_log()
    if hand is None:
        context._record_count_progress(target_cycles, total, action_key="restart")
        return

    flags = win32evtlog.EVENTLOG_FORWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
    try:
        while context.is_running:
            if not hand:
                hand = reopen_event_log()
                if hand is None:
                    time.sleep(1)
                    continue
            try:
                events = win32evtlog.ReadEventLog(hand, flags, 0)
                if not events:
                    win32evtlog.CloseEventLog(hand)
                    hand = reopen_event_log()
                    time.sleep(1)
                    continue
            except Exception as exc:
                context.logger.debug(f"Error reading event log: {exc}")
                if hand:
                    try:
                        win32evtlog.CloseEventLog(hand)
                    except Exception as close_exc:
                        context.logger.debug(f"Error closing event log: {close_exc}")
                hand = reopen_event_log()
                time.sleep(1)
                continue

            for event in events:
                event_id = event.EventID & 0xFFFF
                if event_id == 1074:
                    occurred_time = _get_event_time(event)
                    if occurred_time is None:
                        continue
                    if occurred_time <= next_start_time:
                        continue
                    total += 1
                    next_start_time = _advance_start_time(occurred_time)
                    context.record_next_action_start_time(next_start_time)
                    context._record_count_progress(
                        target_cycles, total, action_key="restart"
                    )
            if total > log_num:
                context.log(
                    f"当前已测试 {total} 次，目标次数为 {target_cycles:g} 次。"
                )
                log_num = total
            if total >= target_cycles:
                context._record_count_progress(target_cycles, total, action_key="restart")
                context.log(f"已完成目标 restart 次数: {target_cycles:g}")
                return
    finally:
        context._record_count_progress(target_cycles, total, action_key="restart")
        context.log("停止 restart 事件监控.")
        if hand:
            try:
                win32evtlog.CloseEventLog(hand)
            except Exception as exc:
                context.logger.warning(f"restart Final close error: {exc}")
        context.action_complete.set()
