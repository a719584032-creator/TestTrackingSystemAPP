"""结果提交流程的规则计算。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from monitoring.parser import (
    MonitoringAction,
    crystaldiskmark_requirement,
    mikelog_requirement,
    recording_requirement_minutes,
    require_attachment,
    transitioncaplog_requirement,
)


@dataclass(frozen=True)
class ResultRequirements:
    need_attachment: bool
    recording_minutes: Optional[float]
    mikelog_count: Optional[float]
    crystaldiskmark_speed: Optional[float]
    transitioncap_count: Optional[float]


def build_result_requirements(
    actions: Iterable[MonitoringAction],
    result: str,
) -> ResultRequirements:
    recording_minutes = recording_requirement_minutes(actions)
    mikelog_count = mikelog_requirement(actions)
    crystaldiskmark_speed = crystaldiskmark_requirement(actions)
    transitioncap_count = transitioncaplog_requirement(actions)

    recording_required = result == "pass" and (recording_minutes or 0) > 0
    mikelog_required = result == "pass" and (mikelog_count or 0) > 0
    crystaldiskmark_required = result == "pass" and (crystaldiskmark_speed or 0) > 0
    transitioncap_required = result == "pass" and (transitioncap_count or 0) > 0

    need_attachment = (
        (result in {"pass", "fail"} and require_attachment(actions))
        or recording_required
        or mikelog_required
        or crystaldiskmark_required
        or transitioncap_required
    )

    return ResultRequirements(
        need_attachment=need_attachment,
        recording_minutes=recording_minutes if recording_required else None,
        mikelog_count=float(mikelog_count) if mikelog_required else None,
        crystaldiskmark_speed=float(crystaldiskmark_speed) if crystaldiskmark_required else None,
        transitioncap_count=float(transitioncap_count) if transitioncap_required else None,
    )
