"""将监控关键字解析成可执行的监控动作。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from utils.exceptions import ValidationError
from .audio_event_constants import EVENT_SPECS


logger = logging.getLogger(__name__)


def _normalize(value: str) -> str:
    """规范化动作 token，便于查找。"""

    return value.strip().lower().replace(" ", "")

# 实例创建后不可变
@dataclass(frozen=True)
class MonitoringAction:
    """ 用例关键字，例如 ``S3+5`` 或 ``S3+USB+5``。"""

    name: str
    amount: float
    components: Tuple[str, ...] = ()
    raw: str | None = None
    # 强制 components 元组类型
    def __post_init__(self) -> None:
        object.__setattr__(self, "components", tuple(self.components or ()))

    @property
    def normalized_name(self) -> str:
        """ 规范格式化后的关键字 """
        return _normalize(self.name)

    def display_label(self) -> str:
        """返回包含组件拆解的可读标签。"""

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
    """支持的监控动作的规范描述。"""

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
    _ActionDefinition("录音"),
    _ActionDefinition("Restart"),
    _ActionDefinition("电源插拔"),
    _ActionDefinition("USB 插拔"),
    _ActionDefinition("Hotplug"),
    _ActionDefinition("键盘按键"),
    _ActionDefinition("锁屏"),
    _ActionDefinition("鼠标点击"),
    _ActionDefinition("S3 插拔", components=("S3 睡眠", "USB 插拔")),
    _ActionDefinition("S3 电源插拔", components=("S3 睡眠", "电源插拔")),
    _ActionDefinition("显示器开关"),
    _ActionDefinition("显示器插拔"),
    _ActionDefinition("音量"),
    _ActionDefinition("摄像头"),
    _ActionDefinition("Camera"),
    _ActionDefinition("MikeLog"),
    _ActionDefinition("TransitionCapLog"),
    _ActionDefinition("CrystalDiskMark"),
    # 表单记录显示器组合测试类型并检测分辨率
    # usb-a 口
    # 九宫格
)

# 常规动作映射：规范化名称 -> 动作定义
_ACTION_LOOKUP = {_normalize(defn.name): defn for defn in _ACTION_DEFINITIONS}
_AUDIO_ACTION_LOOKUP = {}
for _name, _spec in EVENT_SPECS.items():
    # 音频事件动作：用事件描述填充组件，供 UI 展示
    normalized = _normalize(_name)
    description = (_spec.get("description") or "").strip()
    components: Tuple[str, ...] = (description,) if description else ()
    _AUDIO_ACTION_LOOKUP[normalized] = _ActionDefinition(_name, components=components)

ACTION_ALIASES = {
    _normalize("s3+usb"): _normalize("S3 插拔"),
    _normalize("s3usb"): _normalize("S3 插拔"),
    _normalize("s3+电源插拔"): _normalize("S3 电源插拔"),
    _normalize("time"): _normalize("时间"),
    _normalize("hotplug"): _normalize("Hotplug"),
    _normalize("hdmi"): _normalize("显示器插拔"),
    _normalize("hdmi插拔"): _normalize("显示器插拔"),
    _normalize("displayhotplug"): _normalize("显示器插拔"),
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
    """将关键字 token 转换为监控动作。

    期望格式为 ``动作+次数``，也支持多步骤组合如 ``S3+USB+5``。
    解析格式错误会抛出 :class:`ValidationError`。不支持的监控动作将被忽略。
    """

    actions: List[MonitoringAction] = []
    format_errors: List[str] = []
    unsupported: List[str] = []

    for token in tokens:
        token = token.strip()
        if not token:
            continue
        # 按 “+” 切分：前半部是动作组合，末尾是次数
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

        # 保留原始 token 方便错误提示或展示
        actions.append(
            MonitoringAction(
                name=definition.name,
                amount=amount,
                components=components,
                raw=token,
            )
        )
    if format_errors:
        message = "关键字解析错误: " + ", ".join(format_errors) + "。请使用 '动作+次数' 的格式"
        raise ValidationError(message)

    if unsupported:
        logger.info(
            "Ignoring unsupported monitoring actions: %s; supported actions: %s",
            ", ".join(unsupported),
            ", ".join(sorted(SUPPORTED_ACTIONS)),
        )

    return actions


def require_attachment(actions: Iterable[MonitoringAction]) -> bool:
    """是否需要附件：时间类动作需强制上传截图。"""

    for action in actions:
        if "时间" in action.name or action.normalized_name == _normalize("时间"):
            return True
    return False


def recording_requirement_minutes(actions: Iterable["MonitoringAction"]) -> float | None:
    """如果存在“录音”类型的监控动作，则返回所需录音时长（分钟）；否则返回 None。"""

    for action in actions:
        if action.normalized_name == _normalize("录音"):
            return max(0.0, float(action.amount))

    return None


def mikelog_requirement(actions: Iterable["MonitoringAction"]) -> float | None:
    """若存在 MikeLog 关键字，返回所需的 Resume counter (Total) 阈值。"""

    for action in actions:
        if action.normalized_name == _normalize("MikeLog"):
            return max(0.0, float(action.amount))
    return None


def crystaldiskmark_requirement(actions: Iterable["MonitoringAction"]) -> float | None:
    """若存在 CrystalDiskMark 关键字，返回所需的读写速率阈值（MB/s）。"""

    for action in actions:
        if action.normalized_name == _normalize("CrystalDiskMark"):
            return max(0.0, float(action.amount))
    return None


def transitioncaplog_requirement(actions: Iterable["MonitoringAction"]) -> float | None:
    """若存在 TransitionCapLog 关键字，返回所需的 loop count 阈值。"""

    for action in actions:
        if action.normalized_name == _normalize("TransitionCapLog"):
            return max(0.0, float(action.amount))
    return None
