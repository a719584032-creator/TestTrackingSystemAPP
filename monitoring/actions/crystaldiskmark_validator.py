"""CrystalDiskMark 日志解析工具。"""
from __future__ import annotations

import re
from pathlib import Path


_READ_HEADER = "[read]"
_WRITE_HEADER = "[write]"
_SPEED_PATTERN = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*MB/s", re.IGNORECASE)


def read_peak_speeds(log_path: str | Path) -> tuple[float, float]:
    """提取 CrystalDiskMark 日志中的最大读写速率（MB/s）。

    :raises ValueError: 当文件不存在、无法读取或缺少有效速率时抛出。
    """

    path = Path(log_path)
    if not path.is_file():
        raise ValueError("日志文件不存在")

    def _load_text() -> str:
        data = path.read_bytes()
        # CrystalDiskMark 日志经常是 UTF-16LE（含 0 字节），做一个简单探测。
        if b"\x00" in data[:128]:
            return data.decode("utf-16", errors="ignore").replace("\x00", "")
        return data.decode("utf-8", errors="ignore")

    try:
        text = _load_text()
    except OSError as exc:  # pragma: no cover - 文件 IO 读取异常
        raise ValueError(f"无法读取日志文件: {exc}") from exc

    current_section: str | None = None
    max_read: float | None = None
    max_write: float | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if _READ_HEADER in lower:
            current_section = "read"
            continue
        if _WRITE_HEADER in lower:
            current_section = "write"
            continue
        if current_section is None:
            continue
        match = _SPEED_PATTERN.search(line)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if current_section == "read":
            max_read = value if max_read is None else max(max_read, value)
        else:
            max_write = value if max_write is None else max(max_write, value)

    if max_read is None:
        raise ValueError("日志中未找到 Read 段落或有效的 MB/s 数值")
    if max_write is None:
        raise ValueError("日志中未找到 Write 段落或有效的 MB/s 数值")

    return max_read, max_write
