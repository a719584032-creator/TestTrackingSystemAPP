"""S4 睡眠事件监控。"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import win32evtlog
from .time_count_monitore import S4_times
if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(context: "Patvs_Fuction", start_time, target_cycles) -> None:
    """统计并监控 S4 睡眠事件。"""
    s4_times_ = S4_times(context)
    try:
        target_cycles = float(target_cycles)
    except (TypeError, ValueError):
        target_cycles = 0.0
    if target_cycles <= 0:
        context.log("S4 目标次数为 0，自动跳过。")
        context.action_complete.set()
        return

    (
        start_time,
        total,
        last_record_number,
        last_event_time,
    ) = context._bootstrap_event_progress(
        start_time, lambda event: event.EventID == 42
    )
    last_seen_time = last_event_time
    log_num = total
    context._record_count_progress(target_cycles, total, action_key="s4")
    if total==0:
        s4_times_.remove_json()
    else:
        s4_times_.view_times()
    count_flags = False

    if total:
        context.log(f"S4 已累计完成 {total} 次，剩余 {int(max(0, target_cycles - total))} 次。")
    if total >= target_cycles:
        context.log(f"已完成目标S4次数: {int(total)}")
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
        context._record_count_progress(target_cycles, total, action_key="s4")
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
                if event.EventID == 42:
                    occurred_time = event.TimeGenerated
                    record_number = getattr(event, "RecordNumber", 0) or 0
                    if occurred_time <= start_time:
                        continue
                    if record_number > last_record_number:
                        last_record_number = record_number
                        last_seen_time = occurred_time
                        total += 1
                        context._record_count_progress(
                            target_cycles, total, action_key="s4"
                        )
                        count_flags = True
                    elif record_number <= 0 or occurred_time > last_seen_time:
                        last_record_number = record_number
                        last_seen_time = occurred_time
                        total += 1
                        context._record_count_progress(
                            target_cycles, total, action_key="s4"
                        )
                        count_flags = True
            if count_flags:
                time.sleep(4)
                s4_times_.filter_deepsleep_events(last_event_time,total)
                count_flags = False

            if total > log_num:
                context.log(
                    f"当前已测试 {total} 次，目标次数为 {target_cycles:g} 次。"
                )
                log_num = total
            if total >= target_cycles:
                context._record_count_progress(target_cycles, total, action_key="s4")
                context.log(f"已完成目标S4次数: {target_cycles:g}")
                return
    finally:
        context._record_count_progress(target_cycles, total, action_key="s4")
        context.log("停止S4事件监控.")
        if hand:
            try:
                win32evtlog.CloseEventLog(hand)
            except Exception as exc:
                context.logger.warning(f"S4 Final close error: {exc}")
        context.action_complete.set()
