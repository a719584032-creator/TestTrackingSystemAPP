"""Mike 日志 Resume counter 校验工具。"""
from __future__ import annotations

import re
from pathlib import Path


_END_TEST_TOKEN = "event  : end test"
_RESUME_COUNTER_PATTERN = re.compile(r"resume\s+counter\s*\(total\)\s*=\s*(\d+)", re.IGNORECASE)


def read_resume_counter_after_end_test(log_path: str | Path) -> int:
    """读取最后一个“End test”之后的 Resume counter (Total) 数值。

    :raises ValueError: 当文件不存在、无法读取或未找到标记/计数行时抛出。
    """

    path = Path(log_path)
    if not path.is_file():
        raise ValueError("日志文件不存在")

    lines_after_last_end: list[str] = []
    found_end_marker = False
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as file_obj:
            for raw_line in file_obj:
                line = raw_line.strip()
                normalized = line.lower()
                if _END_TEST_TOKEN in normalized:
                    lines_after_last_end = []
                    found_end_marker = True
                    continue
                if found_end_marker:
                    lines_after_last_end.append(line)
    except OSError as exc:
        raise ValueError(f"无法读取日志文件: {exc}") from exc

    if not found_end_marker:
        raise ValueError("日志中未找到 'EVENT  : End test' 标记")

    for line in lines_after_last_end:
        match = _RESUME_COUNTER_PATTERN.search(line)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                continue

    raise ValueError("未在 'End test' 之后找到 Resume counter (Total) 计数")
