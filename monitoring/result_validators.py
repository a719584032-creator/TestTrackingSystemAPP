"""结果提交时的附件校验。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Sequence

from monitoring.actions.crystaldiskmark_validator import read_peak_speeds
from monitoring.actions.luyin import get_audio_duration_seconds
from monitoring.actions.mikelog_validator import read_resume_counter_after_end_test
from monitoring.actions.transitioncaplog_validator import read_loop_count_after_end


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    title: str = ""
    message: str = ""


def _paths_from_attachments(attachments: Iterable[dict[str, str]]) -> list[str]:
    paths: list[str] = []
    for payload in attachments:
        path = payload.get("local_path")
        if path:
            paths.append(path)
    return paths


def validate_recording_attachments(
    attachments: Sequence[dict[str, str]],
    required_minutes: float | None,
) -> ValidationResult:
    if required_minutes is None or required_minutes <= 0:
        return ValidationResult(ok=True)
    if not attachments:
        return ValidationResult(
            ok=False,
            title="缺少录音",
            message=f"提交通过需要上传时长不少于 {required_minutes:g} 分钟的录音文件。",
        )

    required_seconds = required_minutes * 60
    errors: list[str] = []
    for payload in attachments:
        path = payload.get("local_path")
        if not path:
            continue
        try:
            duration = get_audio_duration_seconds(path)
        except ValueError as exc:
            errors.append(f"{os.path.basename(path)}: {exc}")
            continue
        if duration >= required_seconds:
            return ValidationResult(ok=True)
        errors.append(
            f"{os.path.basename(path)} 时长 {duration / 60:.1f} 分钟，不足 {required_minutes:g} 分钟"
        )

    message = "\n".join(errors) if errors else "请上传可识别的录音文件。"
    return ValidationResult(ok=False, title="录音不符合要求", message=message)


def validate_mikelog_attachments(
    attachments: Sequence[dict[str, str]],
    required_count: float,
) -> ValidationResult:
    if required_count <= 0:
        return ValidationResult(ok=True)
    log_paths = _paths_from_attachments(attachments)
    if not log_paths:
        return ValidationResult(
            ok=False,
            title="缺少 Mike 日志",
            message=(
                "提交通过需要上传 Mike 日志，"
                f"Resume counter (Total) 需达到 {required_count:g}。"
            ),
        )

    errors: list[str] = []
    for path in log_paths:
        try:
            resume_count = read_resume_counter_after_end_test(path)
        except ValueError as exc:
            errors.append(f"{os.path.basename(path)}: {exc}")
            continue
        if resume_count < required_count:
            errors.append(
                f"{os.path.basename(path)} Resume counter (Total) = {resume_count}, 低于要求的 {required_count:g}"
            )

    if errors:
        message = "\n".join(errors)
        return ValidationResult(ok=False, title="Mike 日志不符合要求", message=message)
    return ValidationResult(ok=True)


def validate_crystaldiskmark_attachments(
    attachments: Sequence[dict[str, str]],
    required_speed: float,
) -> ValidationResult:
    if required_speed <= 0:
        return ValidationResult(ok=True)
    log_paths = _paths_from_attachments(attachments)
    if not log_paths:
        return ValidationResult(
            ok=False,
            title="缺少 CrystalDiskMark 日志",
            message=(
                "提交通过需要上传 CrystalDiskMark 日志，"
                f"读写速率需达到 {required_speed:g} MB/s。"
            ),
        )

    errors: list[str] = []
    for path in log_paths:
        try:
            read_speed, write_speed = read_peak_speeds(path)
        except ValueError as exc:
            errors.append(f"{os.path.basename(path)}: {exc}")
            continue
        if read_speed <= required_speed or write_speed <= required_speed:
            errors.append(
                f"{os.path.basename(path)} 读 {read_speed:.3f} MB/s，写 {write_speed:.3f} MB/s，"
                f"未超过要求的 {required_speed:g} MB/s"
            )

    if errors:
        message = "\n".join(errors)
        return ValidationResult(ok=False, title="CrystalDiskMark 日志不符合要求", message=message)
    return ValidationResult(ok=True)


def validate_transitioncaplog_attachments(
    attachments: Sequence[dict[str, str]],
    required_count: float,
) -> ValidationResult:
    if required_count <= 0:
        return ValidationResult(ok=True)
    log_paths = _paths_from_attachments(attachments)
    if not log_paths:
        return ValidationResult(
            ok=False,
            title="缺少 TransitionCap 日志",
            message=(
                "提交通过需要上传 TransitionCap 日志，"
                f"loop count 需达到 {required_count:g}。"
            ),
        )

    errors: list[str] = []
    for path in log_paths:
        try:
            loop_count = read_loop_count_after_end(path)
        except ValueError as exc:
            errors.append(f"{os.path.basename(path)}: {exc}")
            continue
        if loop_count < required_count:
            errors.append(
                f"{os.path.basename(path)} loop count = {loop_count}, 低于要求的 {required_count:g}"
            )

    if errors:
        message = "\n".join(errors)
        return ValidationResult(ok=False, title="TransitionCap 日志不符合要求", message=message)
    return ValidationResult(ok=True)
