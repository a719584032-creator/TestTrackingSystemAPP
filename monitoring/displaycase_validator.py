"""DisplayCase 环境校验与解析。"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DisplayCaseValidationResult:
    ok: bool
    title: str = ""
    message: str = ""


def _extract_payload_from_text(text: str) -> Optional[Dict[str, str]]:
    if not text:
        return None
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except (TypeError, ValueError) as exc:
        logger.warning("DisplayCase action parse failed: %s", exc)
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def parse_display_case_payload(steps: list[object] | str | None) -> Optional[Dict[str, str]]:
    if not steps:
        return None
    if isinstance(steps, str):
        return _extract_payload_from_text(steps)

    target_text: Optional[str] = None
    fallback_texts: List[str] = []
    for step in steps:
        action = getattr(step, "action", None)
        if action:
            fallback_texts.append(str(action))
        if getattr(step, "no", None) is not None and str(step.no).strip() == "2":
            target_text = str(action) if action else None
            break

    if target_text:
        payload = _extract_payload_from_text(target_text)
        if payload:
            return payload
    for text in fallback_texts:
        payload = _extract_payload_from_text(text)
        if payload:
            return payload
    return None


def display_case_include_primary(payload: Dict[str, str]) -> bool:
    lcd_state = payload.get("lcd_off_on")
    if lcd_state is None:
        return True
    normalized = str(lcd_state).strip().lower().replace(" ", "")
    if normalized == "off":
        return False
    if normalized == "on":
        return True
    return True


def get_connected_display_resolutions(include_primary: bool) -> List[str]:
    """获取当前 Windows 系统中已连接显示器的分辨率信息。"""
    try:
        import win32api
        import win32con
    except Exception as exc:
        logger.warning("无法加载显示器检测依赖: %s", exc)
        return []

    monitors: List[Dict[str, object]] = []

    for monitor_handle, _, _ in win32api.EnumDisplayMonitors():
        info = win32api.GetMonitorInfo(monitor_handle)
        device = info.get("Device")
        if not device:
            continue

        try:
            settings = win32api.EnumDisplaySettings(
                device, win32con.ENUM_CURRENT_SETTINGS
            )
        except Exception as exc:
            logger.warning("读取显示器配置失败(%s): %s", device, exc)
            continue

        width = getattr(settings, "PelsWidth", None)
        height = getattr(settings, "PelsHeight", None)
        freq = getattr(settings, "DisplayFrequency", None)
        if not width or not height:
            continue

        resolution = f"{int(width)}*{int(height)}*{int(freq or 0)}"
        is_primary = bool(info.get("Flags", 0) & win32con.MONITORINFOF_PRIMARY)
        monitors.append({"resolution": resolution, "is_primary": is_primary})

    if not monitors:
        return []

    if include_primary:
        selected = monitors
    else:
        selected = [item for item in monitors if not item.get("is_primary")]

    return [str(item.get("resolution")) for item in selected if item.get("resolution")]


def validate_display_case_resolution(steps: list[object] | str | None) -> DisplayCaseValidationResult:
    payload = parse_display_case_payload(steps)
    if not payload:
        return DisplayCaseValidationResult(
            ok=False,
            title="用例解析失败",
            message="当前用例解析出错，请使用 DisplayCase 自动生成的用例。",
        )

    monitor_qty_raw = payload.get("monitor_qty")
    try:
        expected_qty = int(str(monitor_qty_raw).strip())
    except (TypeError, ValueError):
        expected_qty = -1

    if expected_qty <= 0:
        return DisplayCaseValidationResult(
            ok=False,
            title="用例解析失败",
            message="当前用例解析出错，请使用 DisplayCase 自动生成的用例。",
        )

    resolution_fields = (
        "tbt_monitor",
        "type_c_monitor",
        "dp1_monitor",
        "dp2_monitor",
        "hdmi1_monitor",
        "hdmi2_monitor",
    )
    expected_resolutions: list[str] = []
    for field in resolution_fields:
        value = payload.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            expected_resolutions.append(text)

    if not expected_resolutions:
        return DisplayCaseValidationResult(
            ok=False,
            title="用例解析失败",
            message="当前用例解析出错，请使用 DisplayCase 自动生成的用例。",
        )

    include_primary = display_case_include_primary(payload)
    actual_resolutions = get_connected_display_resolutions(include_primary)
    qty_label = "期望显示器数量" if include_primary else "期望外接显示器数量"

    if len(actual_resolutions) != expected_qty:
        message = (
            "请连接正确的显示器和分辨率。\n"
            f"{qty_label}: {expected_qty}\n"
            f"当前检测数量: {len(actual_resolutions)}\n"
            f"期望分辨率: {', '.join(expected_resolutions)}\n"
            f"当前分辨率: {', '.join(actual_resolutions) or '未检测到'}"
        )
        return DisplayCaseValidationResult(False, "显示器数量不匹配", message)

    missing = [item for item in actual_resolutions if item not in expected_resolutions]
    if missing:
        message = (
            "请连接正确的显示器和分辨率。\n"
            f"期望分辨率: {', '.join(expected_resolutions)}\n"
            f"当前分辨率: {', '.join(actual_resolutions)}\n"
            f"未匹配分辨率: {', '.join(missing)}"
        )
        return DisplayCaseValidationResult(False, "显示器分辨率不匹配", message)

    return DisplayCaseValidationResult(ok=True)
