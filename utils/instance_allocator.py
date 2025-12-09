"""为每个进程分配独立的实例目录"""
from __future__ import annotations

import atexit
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import IO

import psutil


@dataclass(frozen=True, slots=True)
class InstanceAllocation:
    """实例目录分配结果"""

    slot: int
    slot_root: Path
    patvs_root: Path
    config_root: Path
    meta_path: Path


def allocate_instance_paths(base_root: Path | None = None) -> InstanceAllocation:
    """
    为当前进程分配实例目录，并设置环境变量。

    base_root 为空时，使用默认 PATVS 根目录（Windows 为 C:/PATVS，其他平台为 ~/PATVS）。
    """

    resolved_base = base_root or _default_base_root()
    instances_root = resolved_base / "instances"
    instances_root.mkdir(parents=True, exist_ok=True)

    with _locked_file(instances_root / "slots.lock"):
        slot = _next_available_slot(instances_root)
        slot_root = instances_root / f"slot-{slot}"
        patvs_root = slot_root / "patvs"
        config_root = slot_root / "config"
        slot_root.mkdir(parents=True, exist_ok=True)
        patvs_root.mkdir(parents=True, exist_ok=True)
        config_root.mkdir(parents=True, exist_ok=True)
        meta_path = slot_root / "meta.json"
        _write_meta(meta_path, slot)

    allocation = InstanceAllocation(
        slot=slot,
        slot_root=slot_root,
        patvs_root=patvs_root,
        config_root=config_root,
        meta_path=meta_path,
    )
    os.environ["PATVS_ROOT"] = str(allocation.patvs_root)
    os.environ["TTS_CONFIG_DIR"] = str(allocation.config_root)
    _register_cleanup(allocation)
    return allocation


def _default_base_root() -> Path:
    return Path("C:/PATVS") if os.name == "nt" else Path.home() / "PATVS"


@contextmanager
def _locked_file(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock_file:
        _acquire_lock(lock_file)
        try:
            yield lock_file
        finally:
            _release_lock(lock_file)


def _acquire_lock(lock_file: IO[str]) -> None:
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)


def _release_lock(lock_file: IO[str]) -> None:
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _next_available_slot(instances_root: Path) -> int:
    slot = 1
    while True:
        slot_root = instances_root / f"slot-{slot}"
        if not _is_slot_active(slot_root):
            return slot
        slot += 1


def _is_slot_active(slot_root: Path) -> bool:
    meta_path = slot_root / "meta.json"
    if not meta_path.exists():
        return False

    try:
        with meta_path.open("r", encoding="utf-8") as handle:
            meta = json.load(handle)
    except (OSError, json.JSONDecodeError):
        _safe_remove(meta_path)
        return False

    pid = meta.get("pid")
    if not isinstance(pid, int) or not psutil.pid_exists(pid):
        _safe_remove(meta_path)
        return False

    return True


def _write_meta(meta_path: Path, slot: int) -> None:
    meta = {
        "slot": slot,
        "pid": os.getpid(),
        "allocated_at": datetime.now(timezone.utc).isoformat(),
    }
    with meta_path.open("w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)


def _register_cleanup(allocation: InstanceAllocation) -> None:
    def _cleanup() -> None:
        try:
            with allocation.meta_path.open("r", encoding="utf-8") as handle:
                meta = json.load(handle)
            if meta.get("pid") != os.getpid():
                return
        except (OSError, json.JSONDecodeError):
            return

        _safe_remove(allocation.meta_path)

    atexit.register(_cleanup)


def _safe_remove(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except TypeError:  # Python < 3.8 兼容
        try:
            path.unlink()
        except FileNotFoundError:
            pass

