"""Nine-grid action configuration and label mapping."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


def _normalize(value: str) -> str:
    return value.strip().lower().replace(" ", "")


@dataclass(frozen=True)
class NineGridAction:
    key: str
    label: str
    base_action: str
    count: float


NINE_GRID_ACTION_ORDER: tuple[str, ...] = (
    "hotplug",
    "s3_plug_in_resume",
    "s3_unplug_plug_in_resume",
    "s3_unplug_resume_plug_in",
    "s4_plug_in_resume",
    "s4_unplug_plug_in_resume",
    "s4_unplug_resume_plug_in",
    "s5_plug_in_power_on",
    "s5_unplug_power_on_plug_in",
)

NINE_GRID_ACTION_SPECS: dict[str, tuple[str, str]] = {
    "hotplug": ("Hotplug", "Hotplug"),
    "s3_plug_in_resume": ("S3-Plug in-Resume", "S3"),
    "s3_unplug_plug_in_resume": ("S3-Unplug-Plug in-Resume", "S3"),
    "s3_unplug_resume_plug_in": ("S3-Unplug-Resume-Plug in", "S3"),
    "s4_plug_in_resume": ("S4-Plug in-Resume", "S4"),
    "s4_unplug_plug_in_resume": ("S4-Unplug-Plug in-Resume", "S4"),
    "s4_unplug_resume_plug_in": ("S4-Unplug-Resume-Plug in", "S4"),
    "s5_plug_in_power_on": ("S5-Plug in-Power on", "S5"),
    "s5_unplug_power_on_plug_in": ("S5-Unplug-Power on-Plug in", "S5"),
}

NINE_GRID_LABEL_ALIASES: dict[str, str] = {
    _normalize(spec[0]): _normalize(spec[1])
    for spec in NINE_GRID_ACTION_SPECS.values()
}
NINE_GRID_LABEL_INDEX: dict[str, tuple[str, str, str]] = {
    _normalize(spec[0]): (key, spec[0], spec[1])
    for key, spec in NINE_GRID_ACTION_SPECS.items()
}
NINE_GRID_KEY_INDEX: dict[str, tuple[str, str, str]] = {
    _normalize(key): (key, spec[0], spec[1])
    for key, spec in NINE_GRID_ACTION_SPECS.items()
}

def _normalize_key(value: object) -> str:
    if value is None:
        return ""
    return _normalize(str(value))


def build_nine_grid_actions(raw_map: Mapping[str, object]) -> list[NineGridAction]:
    if not isinstance(raw_map, Mapping):
        return []
    payload = raw_map
    if "data" in raw_map and isinstance(raw_map.get("data"), Mapping):
        payload = raw_map.get("data")  # type: ignore[assignment]
    normalized_map = {_normalize_key(key): value for key, value in payload.items()}
    actions: list[NineGridAction] = []
    for key in NINE_GRID_ACTION_ORDER:
        normalized_key = _normalize_key(key)
        if normalized_key not in normalized_map:
            continue
        try:
            count = float(normalized_map.get(normalized_key) or 0)
        except (TypeError, ValueError):
            count = 0.0
        if count <= 0:
            continue
        spec = NINE_GRID_ACTION_SPECS.get(key)
        if not spec:
            continue
        label, base_action = spec
        actions.append(
            NineGridAction(
                key=key,
                label=label,
                base_action=base_action,
                count=count,
            )
        )
    return actions


def build_nine_grid_actions_from_session(
    actions_snapshot: Iterable[Mapping[str, object]] | None,
) -> list[NineGridAction]:
    if not actions_snapshot:
        return []
    actions: list[NineGridAction] = []
    for entry in actions_snapshot:
        if not isinstance(entry, Mapping):
            continue
        name = entry.get("name") or entry.get("action")
        if not name:
            continue
        normalized = _normalize(str(name))
        spec = NINE_GRID_LABEL_INDEX.get(normalized) or NINE_GRID_KEY_INDEX.get(normalized)
        if not spec:
            continue
        try:
            count = float(entry.get("target", entry.get("amount", 0)) or 0)
        except (TypeError, ValueError):
            count = 0.0
        if count <= 0:
            continue
        key, label, base_action = spec
        actions.append(
            NineGridAction(
                key=key,
                label=label,
                base_action=base_action,
                count=count,
            )
        )
    return actions
