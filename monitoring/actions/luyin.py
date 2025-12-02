"""使用 mutagen 获取音频工具。"""
from __future__ import annotations

from typing import Optional

from mutagen import File
from mutagen import MutagenError


def get_audio_duration_seconds(path: str) -> float:
    """返回指定音频文件的时长（单位：秒）。"""

    try:
        audio = File(path)
    except (MutagenError, OSError) as exc:
        raise ValueError(f"无法读取录音文件: {exc}") from exc

    # 如果 mutagen 无法识别该文件类型，或无法获取 info 信息，则视为无法识别格式
    if audio is None or not getattr(audio, "info", None):
        raise ValueError("无法识别录音文件格式")

    # 从 audio.info 中尝试获取音频时长（单位：秒）
    duration: Optional[float] = getattr(audio.info, "length", None)
    if not duration:
        raise ValueError("无法获取录音时长")

    return float(duration)
