"""Utilities for parsing monitoring keywords into actionable tasks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .exceptions import ValidationError


@dataclass(frozen=True)
class MonitoringAction:
    """Represents a single monitoring task such as ``S3+5``."""

    name: str
    amount: float

    @property
    def normalized_name(self) -> str:
        return self.name.strip().lower()


SUPPORTED_ACTIONS = {
    "时间",
    "s3",
    "s4",
    "s5",
    "restart",
    "电源插拔",
    "usb插拔",
    "键盘按键",
    "锁屏",
    "鼠标点击",
    "s3插拔",
    "s3电源插拔",
    "显示器",
    "音量",
    "摄像头",
    "camera",
    "s3+usb",  # alias for combined monitor
}


def parse_keywords(tokens: Sequence[str]) -> List[MonitoringAction]:
    """Parse keyword tokens into monitoring actions.

    The parser expects tokens with the format ``action+number``. If the
    ``number`` part cannot be coerced into a float the function raises a
    :class:`ValidationError`.
    """

    actions: List[MonitoringAction] = []
    errors: List[str] = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if "+" not in token:
            errors.append(token)
            continue
        name, amount_str = token.split("+", 1)
        name = name.strip()
        amount_str = amount_str.strip()
        try:
            amount = float(amount_str)
        except ValueError as exc:  # pragma: no cover - defensive branch
            errors.append(token)
            continue
        actions.append(MonitoringAction(name=name, amount=amount))
    if errors:
        raise ValidationError(
            "关键字解析错误: " + ", ".join(errors) + "。请使用 '动作+次数' 的格式"
        )
    return actions


def require_attachment(actions: Iterable[MonitoringAction]) -> bool:
    """Return ``True`` if any action requires screenshot evidence."""

    for action in actions:
        if "时间" in action.name:
            return True
    return False
