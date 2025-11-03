"""音频事件日志监控。"""
from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

from ..audio_event_constants import AUDIO_EVENT_KEYWORDS

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(context: "Patvs_Fuction", action_key: str, target_count: float, display_action: str | None = None) -> None:
    """监控音频日志中的关键字出现次数。"""

    open_files: list[tuple[str, object]] = []
    try:
        if action_key not in AUDIO_EVENT_KEYWORDS:
            context.log(
                f"未在音频事件常量中找到 {display_action or action_key} 对应的关键字。"
            )
            return

        keyword = AUDIO_EVENT_KEYWORDS[action_key]
        target_count_int = int(float(target_count)) if target_count is not None else 0
        target_count_int = max(0, target_count_int)
        expected_keys = {display_action or action_key, action_key}
        if target_count_int == 0:
            context.log(
                f"音频事件 {display_action or action_key} 目标次数为 0，自动跳过。"
            )
            return

        if not context.audio_log_files:
            context.log(
                f"未选择任何 Lab Audio 日志文件，无法监控 {display_action or action_key}。"
            )
            return

        current_count = context.audio_event_cache.get(action_key, 0)
        if current_count >= target_count_int:
            context.log(
                f"音频事件 {display_action or action_key} 已提前满足目标次数 {target_count_int}，当前计数 {current_count}。"
            )
            context.record_count_progress_if_current(
                target_count_int, current_count, expected_keys=expected_keys
            )
            return

        for path in context.audio_log_files:
            try:
                file_obj = open(path, "r", encoding="utf-8", errors="ignore")
                start_pos = context.audio_log_offsets.get(path)
                if start_pos is None:
                    file_obj.seek(0, os.SEEK_END)
                else:
                    file_obj.seek(start_pos)
                open_files.append((path, file_obj))
            except Exception as file_error:
                context.logger.error(f"无法打开音频日志文件 {path}: {file_error}")
                context.log(f"无法打开音频日志文件 {path}: {file_error}")

        if not open_files:
            context.log(
                f"无法监控 {display_action or action_key}，音频日志文件打开失败。"
            )
            return

        context.log(
            f"开始监控音频事件 {display_action or action_key}，目标 {target_count_int} 次，关键字: {keyword}"
        )
        if current_count > 0:
            context.log(
                f"音频事件 {display_action or action_key} 当前已有计数 {current_count}/{target_count_int}。"
            )

        while context.is_running and current_count < target_count_int:
            progress_made = False
            for path, file_obj in open_files:
                line = file_obj.readline()
                while line:
                    progress_made = True
                    for normalized_key, event_keyword in AUDIO_EVENT_KEYWORDS.items():
                        if event_keyword in line:
                            cached = context.audio_event_cache.get(normalized_key, 0) + 1
                            context.audio_event_cache[normalized_key] = cached
                            if normalized_key == action_key:
                                current_count = cached
                                context.log(
                                    f"[{os.path.basename(path)}] 检测到 {keyword} ({current_count}/{target_count_int})"
                                )
                                context.record_count_progress_if_current(
                                    target_count_int,
                                    current_count,
                                    expected_keys=expected_keys,
                                )
                    line = file_obj.readline()
                context.audio_log_offsets[path] = file_obj.tell()
                if current_count >= target_count_int or not context.is_running:
                    break
            if current_count >= target_count_int or not context.is_running:
                break
            if not progress_made:
                time.sleep(0.5)

        if current_count >= target_count_int:
            context.log(
                f"音频事件 {display_action or action_key} 已达到目标次数 {target_count_int}。"
            )
            context.record_count_progress_if_current(
                target_count_int, current_count, expected_keys=expected_keys
            )
        else:
            context.log(
                f"音频事件 {display_action or action_key} 监控结束，当前计数 {current_count}/{target_count_int}。"
            )
            context.record_count_progress_if_current(
                target_count_int, current_count, expected_keys=expected_keys
            )
    except Exception as error:  # pragma: no cover - 兼容异常场景
        context.logger.error(
            f"监控音频事件 {display_action or action_key} 出现异常: {error}"
        )
        context.log(f"监控音频事件 {display_action or action_key} 出现异常: {error}")
    finally:
        for _, file_obj in open_files:
            try:
                file_obj.close()
            except Exception:
                pass
        context.action_complete.set()
