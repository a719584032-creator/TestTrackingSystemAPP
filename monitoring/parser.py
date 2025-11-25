"""Utilities for parsing monitoring keywords into actionable tasks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from utils.exceptions import ValidationError
from .audio_event_constants import EVENT_SPECS


def _normalize(value: str) -> str:
    """Return an action token normalized for lookups."""

    return value.strip().lower().replace(" ", "")


@dataclass(frozen=True)
class MonitoringAction:
    """Represents a monitoring task such as ``S3+5`` or ``S3+USB+5``."""

    name: str
    amount: float
    components: Tuple[str, ...] = ()
    raw: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "components", tuple(self.components or ()))

    @property
    def normalized_name(self) -> str:
        return _normalize(self.name)

    def display_label(self) -> str:
        """Return a human friendly label including component breakdown."""

        if self.components:
            components = tuple(part for part in self.components if part)
            if not components:
                return self.name
            if len(components) == 1:
                single = components[0]
                if single and single.lower() != self.name.lower():
                    return f"{self.name} ({single})"
            else:
                return f"{self.name} ({' + '.join(components)})"
        return self.name


@dataclass(frozen=True)
class _ActionDefinition:
    """Canonical description for a supported monitoring action."""

    name: str
    components: Tuple[str, ...] = ()

    def describe(self, fallback: Sequence[str]) -> Tuple[str, ...]:
        if self.components:
            return self.components
        if fallback:
            return tuple(fallback)
        return (self.name,)


_ACTION_DEFINITIONS: Tuple[_ActionDefinition, ...] = (
    _ActionDefinition("时间"),
    _ActionDefinition("S3"),
    _ActionDefinition("S4"),
    _ActionDefinition("S5"),
    _ActionDefinition("Restart"),
    _ActionDefinition("电源插拔"),
    _ActionDefinition("USB 插拔"),
    _ActionDefinition("键盘按键"),
    _ActionDefinition("锁屏"),
    _ActionDefinition("鼠标点击"),
    _ActionDefinition("S3 插拔", components=("S3 睡眠", "USB 插拔")),
    _ActionDefinition("S3 电源插拔", components=("S3 睡眠", "电源插拔")),
    _ActionDefinition("显示器"),
    _ActionDefinition("音量"),
    _ActionDefinition("摄像头"),
    _ActionDefinition("Camera"),

    _ActionDefinition("S4记时"),
    _ActionDefinition("S3记时"),
)

_ACTION_LOOKUP = {_normalize(defn.name): defn for defn in _ACTION_DEFINITIONS}
_AUDIO_ACTION_LOOKUP = {}
for _name, _spec in EVENT_SPECS.items():
    normalized = _normalize(_name)
    description = (_spec.get("description") or "").strip()
    components: Tuple[str, ...] = (description,) if description else ()
    _AUDIO_ACTION_LOOKUP[normalized] = _ActionDefinition(_name, components=components)

ACTION_ALIASES = {
    _normalize("s3+usb"): _normalize("S3 插拔"),
    _normalize("s3usb"): _normalize("S3 插拔"),
    _normalize("s3+电源插拔"): _normalize("S3 电源插拔"),
    _normalize("time"): _normalize("时间"),
}

SUPPORTED_ACTIONS = {definition.name for definition in _ACTION_DEFINITIONS}


def _resolve_action_name(parts: Sequence[str]) -> Tuple[_ActionDefinition | None, Tuple[str, ...]]:
    if not parts:
        return None, ()
    candidate_key = _normalize("+".join(parts))
    candidate_key = ACTION_ALIASES.get(candidate_key, candidate_key)
    definition = _ACTION_LOOKUP.get(candidate_key)
    if definition is None and len(parts) == 1:
        # 若用户只填写了单一动作，尝试直接匹配该组件，兼容旧格式
        fallback_key = _normalize(parts[0])
        fallback_key = ACTION_ALIASES.get(fallback_key, fallback_key)
        definition = _ACTION_LOOKUP.get(fallback_key)
    if definition is None:
        return None, tuple(parts)
    return definition, definition.describe(parts)


def _resolve_audio_action(parts: Sequence[str]) -> Tuple[_ActionDefinition | None, Tuple[str, ...]]:
    if len(parts) != 1:
        return None, ()
    key = _normalize(parts[0])
    definition = _AUDIO_ACTION_LOOKUP.get(key)
    if definition is None:
        return None, ()
    return definition, definition.describe(parts)


def parse_keywords(tokens: Sequence[str]) -> List[MonitoringAction]:
    """Parse keyword tokens into monitoring actions.

    The parser expects tokens with the format ``action+number`` and can also resolve
    multi-step combinations such as ``S3+USB+5``. If parsing or validation fails,
    a :class:`ValidationError` is raised listing the problematic tokens.
    """

    actions: List[MonitoringAction] = []
    format_errors: List[str] = []
    unsupported: List[str] = []

    for token in tokens:
        token = token.strip()
        if not token:
            continue
        parts = [part.strip() for part in token.split("+") if part.strip()]
        if len(parts) < 2:
            format_errors.append(token)
            continue
        amount_str = parts[-1]
        action_parts = parts[:-1]
        try:
            amount = float(amount_str)
        except ValueError:  # pragma: no cover - 防御性分支
            format_errors.append(token)
            continue
        # 将动作部分解析成规范化定义 + 组件描述，便于界面自动勾选监控项
        definition, components = _resolve_action_name(action_parts)

        if definition is None:
            definition, components = _resolve_audio_action(action_parts)
        if definition is None:
            unsupported.append("+".join(action_parts))
            continue

        actions.append(
            MonitoringAction(
                name=definition.name,
                amount=amount,
                components=components,
                raw=token,
            )
        )
    if format_errors or unsupported:
        messages: List[str] = []
        if format_errors:
            messages.append(
                "关键字解析错误: " + ", ".join(format_errors) + "。请使用 '动作+次数' 的格式"
            )
        if unsupported:
            messages.append(
                "存在不支持的监控动作: "
                + ", ".join(unsupported)
                + "。支持的动作: "
                + ", ".join(sorted(SUPPORTED_ACTIONS))
            )
        raise ValidationError("；".join(messages))

    return actions


def require_attachment(actions: Iterable[MonitoringAction]) -> bool:
    """Return ``True`` if any action requires screenshot evidence."""

    for action in actions:
        if "时间" in action.name or action.normalized_name == _normalize("时间"):
            return True
    return False
