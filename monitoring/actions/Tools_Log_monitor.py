"""Log解析事件监控。"""
from __future__ import annotations

from typing import TYPE_CHECKING
from pathlib import Path
if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction

from .Log_jugement_monitor import LogParser,HtmlParser

def run(context: "Patvs_Fuction",
        target_count: float,
        display_action: str | None = None) -> None:

    open_files: list[tuple[str, object]] = []
    count_time=0
    pass_result=[]
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
        log_files=[path for path in log_files if display_action.lower().replace('log','') in path.lower()]
        context.log(
            f"{display_action} 执行文件数量为 {len(log_files)}"
        )
        for index,path in enumerate(log_files):
            context.log(
                f"已选择第{index+1}个文件为：{Path(path).name}"
            )
            try:
                if path.endswith('.html'):
                    test_result=HtmlParser(context).finder_html_data(path)
                else:
                    test_result=LogParser(context,display_action).parse_log_file(path)
                open_files.append(path)
                count_time=index+1

                context._record_count_progress(
                    target_count, count_time, action_key=display_action.lower()
                )
                pass_result.append(test_result[-1])
                if count_time==target_count_int:
                    context.log(
                        f"{display_action}事件已提前满足目标次数 {target_count_int}，当前计数 {count_time}/{target_count_int}。"
                    )
                    break

            except Exception as file_error:
                context.logger.error(f"无法打开{display_action}日志文件 {path}: {file_error}")
                context.log(f"无法打开{display_action}日志文件 {path} , 请选择正确的{display_action}日志文件")
                return

        if count_time<target_count_int:
            context.log(
                f"{display_action}事件不满足目标次数 {target_count_int}，当前计数 {count_time}/{target_count_int}。"
            )
            return

        if "FAIL" in pass_result or pass_result==[]:
            context.log(
                f"{display_action}事件没有满足测试通过要求，当前状态为 FAIL。"
            )
            return
        else:
            context.log(
                f"{display_action}事件已满测试通过要求，当前状态为 PASS。"
            )
            context.action_complete.set()
            return

    except Exception as error:  # pragma: no cover - 兼容异常场景
        context.logger.error(
            f"监控{display_action}事件出现异常: {error}"
        )
        context.log(f"监控{display_action} 事件出现异常: {error}")
        return



