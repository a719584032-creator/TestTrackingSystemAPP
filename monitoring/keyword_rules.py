"""监控关键字的辅助规则。"""
from __future__ import annotations

from typing import Sequence, Tuple

from monitoring.audio_event_constants import AUDIO_EVENT_KEYWORDS
from monitoring.parser import MonitoringAction


def is_recording_action(action: MonitoringAction) -> bool:
    return action.normalized_name == "录音"


def is_mikelog_action(action: MonitoringAction) -> bool:
    return action.normalized_name == "mikelog"


def is_crystaldiskmark_action(action: MonitoringAction) -> bool:
    return action.normalized_name == "crystaldiskmark"


def is_transitioncap_action(action: MonitoringAction) -> bool:
    return action.normalized_name == "transitioncaplog"


def filter_monitoring_actions(
    actions: Sequence[MonitoringAction],
) -> list[MonitoringAction]:
    return [
        action
        for action in actions
        if not is_recording_action(action)
        and not is_mikelog_action(action)
        and not is_crystaldiskmark_action(action)
        and not is_transitioncap_action(action)
    ]


def requires_audio_logs(actions: Sequence[MonitoringAction]) -> bool:
    return any(action.normalized_name in AUDIO_EVENT_KEYWORDS for action in actions)


def requires_text_logs(actions: Sequence[MonitoringAction]) -> Tuple[bool, str]:
    for action in actions:
        normalized = action.normalized_name
        if is_mikelog_action(action) or is_transitioncap_action(action):
            continue
        if "log" in normalized:
            return True, normalized
    return False, "None"
