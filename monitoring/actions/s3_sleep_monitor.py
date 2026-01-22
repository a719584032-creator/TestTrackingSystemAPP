"""S3 睡眠事件监控。"""
from __future__ import annotations

import datetime
import time
from typing import TYPE_CHECKING, Optional

import win32evtlog
import threading
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


def run(
    context: "Patvs_Fuction",
    start_time,
    target_cycles,
    s3_done_event: Optional[threading.Event] = None,
    action_label: str | None = None,
) -> None:
    """统计并监控 S3 睡眠事件。"""
    label = str(action_label).strip() if action_label else "S3"
    if not label:
        label = "S3"
    try:
        target_cycles = float(target_cycles)
    except (TypeError, ValueError):
        target_cycles = 0.0
    if target_cycles <= 0:
        context.log(f"{label} 目标次数为 0，自动跳过。")
        if s3_done_event:
            s3_done_event.set()
        else:
            context.action_complete.set()
        return

    next_start_time, total = context._bootstrap_event_progress(
        start_time,
        lambda event: event.EventID in (507, 107),
        batch_window=DEFAULT_BATCH_WINDOW,
        event_time_getter=_get_event_time,
    )
    if total:
        context.record_next_action_start_time(next_start_time)
    log_num = total

    def log_progress_if_changed():
        nonlocal log_num
        if total != log_num:
            context.log(
                f"当前已测试 {label} {total} 次，目标次数为 {target_cycles:g} 次。"
            )
            log_num = total

    # 记录初始进度
    context._record_count_progress(target_cycles, total, action_key="s3")
    if total:
        context.log(
            f"{label} 已累计完成 {total} 次，剩余 {int(max(0, target_cycles - total))} 次。"
        )
    if total >= target_cycles:
        context.log(f"已完成目标{label}次数: {int(total)}")
        if s3_done_event:
            s3_done_event.set()
        else:
            context.action_complete.set()
        return

    def reopen_event_log():
        # 打开系统日志
        try:
            return win32evtlog.OpenEventLog(None, "System")
        except Exception as exc:  # pragma: no cover - 仅用于错误追踪
            context.log(f"Failed to open event log: {exc}")
            return None

    hand = reopen_event_log()
    if hand is None:
        context._record_count_progress(target_cycles, total, action_key="s3")
        return

    flags = win32evtlog.EVENTLOG_FORWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
    try:
        # 循环读取日志
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
                if event.EventID in (507, 107):
                    # 日志开始时间
                    occurred_time = _get_event_time(event)
                    if occurred_time is None:
                        continue
                    if occurred_time <= next_start_time:
                        continue
                    total += 1
                    next_start_time = _advance_start_time(occurred_time)
                    context.record_next_action_start_time(next_start_time)
                    context._record_count_progress(
                        target_cycles, total, action_key="s3"
                    )
                    log_progress_if_changed()


            if total >= target_cycles:
                context._record_count_progress(target_cycles, total, action_key="s3")
                context.log(f"已完成目标{label}次数: {total}")
                return
    finally:
        context._record_count_progress(target_cycles, total, action_key="s3")
        if hand:
            try:
                win32evtlog.CloseEventLog(hand)
            except Exception as exc:
                context.logger.warning(f"S3 Final close error: {exc}")
        context.log(f"停止{label}事件监控.")
        if s3_done_event:
            s3_done_event.set()
        else:
            context.action_complete.set()
