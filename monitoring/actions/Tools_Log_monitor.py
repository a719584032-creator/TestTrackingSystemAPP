"""Log解析事件监控。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction

import re
from pathlib import Path

from .Log_jugement_monitor import Log_parse



def run(context: "Patvs_Fuction",
        target_count: float,
        display_action: str | None = None) -> None:

    log_parse_=Log_parse(context,display_action)
    open_files: list[tuple[str, object]] = []
    try:

        target_count_int = int(float(target_count)) if target_count is not None else 0
        target_count_int = max(0, target_count_int)

        if target_count_int == 0:
            context.log(
                f"{display_action}事件目标次数为 0，自动跳过。"
            )
            return

        log_files = context.get_audio_log_files()
        if not log_files:
            context.log(
                f"未选择任何日志文件，无法监控 {display_action}。"
            )
            return

        for index,path in enumerate(log_files):
            try:
                test_result=log_parse_.folder_files(path)
                open_files.append(path)
                context._record_count_progress(
                    target_count, index+1, action_key=display_action.lower()
                )


            except Exception as file_error:
                context.logger.error(f"无法打开{display_action}日志文件 {path}: {file_error}")
                context.log(f"无法打开{display_action}日志文件 {path}: {file_error}")
            if "PASS" in test_result[-1]:
                context.action_complete.set()
            else:
                context.log(
                    f"{display_action}事件已提前满足目标次数 {target_count_int}，当前计数 {index+1}/{target_count_int}。"
                )
        if not open_files:
            context.log(
                f"无法监控 {display_action}，{display_action}日志文件打开失败。"
            )
            return

    except Exception as error:  # pragma: no cover - 兼容异常场景
        context.logger.error(
            f"监控{display_action}事件出现异常: {error}"
        )
        context.log(f"监控{display_action} 事件出现异常: {error}")

    # finally:
    #     context.action_complete.set()

