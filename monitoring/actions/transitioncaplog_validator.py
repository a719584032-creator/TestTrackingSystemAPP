"""TransitionCap 日志 loop count 校验工具。"""
from __future__ import annotations

import re
from pathlib import Path


_END_TOKEN = "# end"
_RESULT_PATTERN = re.compile(r"#\s*result\s*=\s*([a-z0-9_]+)", re.IGNORECASE)
_LOOP_PATTERN = re.compile(r"#\s*loop\s*count\s*=\s*(\d+)", re.IGNORECASE)


def read_loop_count_after_end(log_path: str | Path) -> int:
    """读取最后一个 '# end' 后的 loop count。

    检测顺序：先找 '# end'，再验证 result = OK，最后读取 loop count 数值。

    :raises ValueError: 当文件不存在、无法读取或缺少关键标记时抛出。
    """

    path = Path(log_path)
    if not path.is_file():
        raise ValueError("日志文件不存在")

    last_prefix: str | None = None
    trailing_lines: list[str] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                lower = line.lower()
                if _END_TOKEN in lower:
                    last_prefix = line.split("#", 1)[0].strip()
                    trailing_lines = []
                    continue
                if last_prefix:
                    trailing_lines.append(line)
    except OSError as exc:  # pragma: no cover - 文件 IO 在测试环境难以稳定复现
        raise ValueError(f"无法读取日志文件: {exc}") from exc

    if not last_prefix:
        raise ValueError("日志中未找到 '# end' 标记")

    result_value: str | None = None
    loop_count: int | None = None
    for line in trailing_lines:
        if not line or not line.startswith(last_prefix):
            continue
        if result_value is None:
            result_match = _RESULT_PATTERN.search(line)
            if result_match:
                result_value = result_match.group(1).strip()
        loop_match = _LOOP_PATTERN.search(line)
        if loop_match:
            try:
                loop_count = int(loop_match.group(1))
            except ValueError:
                continue

    if result_value is None:
        raise ValueError("未在 '# end' 之后找到 result 标记")
    if result_value.lower() != "ok":
        raise ValueError(f"result = {result_value}，未通过")
    if loop_count is None:
        raise ValueError("未在 '# end' 之后找到 loop count 标记")

    return loop_count
