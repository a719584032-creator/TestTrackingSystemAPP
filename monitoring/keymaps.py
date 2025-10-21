"""Keyword parsing helpers for monitoring actions."""
from __future__ import annotations

from typing import Dict, Tuple

# Normalized keyword -> canonical monitor action name used in Patvs_Fuction
KEYWORD_MAPPING: Dict[str, str] = {
    "时间": "时间",
    "time": "时间",
    "电源插拔": "电源插拔",
    "power": "电源插拔",
    "usb插拔": "usb插拔",
    "usb": "usb插拔",
    "键盘按键": "键盘按键",
    "lock": "锁屏",
    "锁屏": "锁屏",
    "鼠标点击": "鼠标点击",
    "mouse": "鼠标点击",
    "s3": "s3",
    "s4": "s4",
    "s5": "s5",
    "restart": "restart",
    "s3插拔": "s3插拔",
    "s3电源插拔": "s3电源插拔",
    "显示器": "显示器",
    "monitor": "显示器",
    "音量": "音量",
    "volume": "音量",
    "摄像头": "摄像头",
    "camera": "camera",
    "音频": "audio",
}


def normalize_keyword(raw: str) -> Tuple[str, str]:
    key = raw.strip().lower()
    return KEYWORD_MAPPING.get(key, raw), key
