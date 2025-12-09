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


def ensure_instance_paths(base_root: Path | None = None) -> InstanceAllocation:
    """
    确保当前进程使用已分配的实例目录。
    若环境变量已存在且可用，则直接返回；否则分配新的实例目录。
    """

    existing = _allocation_from_env()
    if existing:
        _register_cleanup(existing)
        return existing
    return allocate_instance_paths(base_root=base_root)


def allocate_instance_paths(base_root: Path | None = None) -> InstanceAllocation:
    """
    为当前进程分配实例目录，并设置环境变量。

    base_root 为空时，使用默认 PATVS 根目录 C:/PATVS。
    """

    resolved_base = base_root or _default_base_root()
    # 创建 instances 目录
    instances_root = resolved_base / "instances"
    instances_root.mkdir(parents=True, exist_ok=True)
    # 加锁读取 slots.lock
    with _locked_file(instances_root / "slots.lock"):
        # 获取没被占用的 slot 号
        slot = _next_available_slot(instances_root)
        slot_root = instances_root / f"slot-{slot}"
        patvs_root = slot_root / "patvs"
        config_root = slot_root / "config"
        # 创建目录
        slot_root.mkdir(parents=True, exist_ok=True)
        patvs_root.mkdir(parents=True, exist_ok=True)
        config_root.mkdir(parents=True, exist_ok=True)
        # 写入 meta.json
        meta_path = slot_root / "meta.json"
        _write_meta(meta_path, slot)
    # 构造对象
    allocation = InstanceAllocation(
        slot=slot,
        slot_root=slot_root,
        patvs_root=patvs_root,
        config_root=config_root,
        meta_path=meta_path,
    )
    os.environ["PATVS_ROOT"] = str(allocation.patvs_root)
    os.environ["TTS_CONFIG_DIR"] = str(allocation.config_root)
    os.environ["TTS_INSTANCE_SLOT"] = str(allocation.slot)
    # 注册清理函数
    _register_cleanup(allocation)
    return allocation


def _default_base_root() -> Path:
    return Path("C:/PATVS")


def _allocation_from_env() -> InstanceAllocation | None:
    """
    获取环境变量已存在的实例目录
    """
    patvs_env = os.environ.get("PATVS_ROOT")
    config_env = os.environ.get("TTS_CONFIG_DIR")
    slot_env = os.environ.get("TTS_INSTANCE_SLOT")

    if not patvs_env or not config_env:
        return None

    patvs_root = Path(patvs_env)
    config_root = Path(config_env)
    # 父目录以 slot- 开头
    # patvs_root.parent   -> C:/PATVS/instances/slot-3
    # patvs_root.parent.name  -> "slot-3"
    slot_root = patvs_root.parent if patvs_root.parent.name.startswith("slot-") else None
    if slot_root is None and config_root.parent.name.startswith("slot-"):
        slot_root = config_root.parent
    if slot_root is None:
        return None

    try:
        #  - 切割取索引1
        slot = int(slot_env) if slot_env is not None else int(slot_root.name.split("-", 1)[1])
    except ValueError:
        slot = 0

    meta_path = slot_root / "meta.json"
    for path in (slot_root, patvs_root, config_root):
        path.mkdir(parents=True, exist_ok=True)

    if slot_env is None:
        os.environ["TTS_INSTANCE_SLOT"] = str(slot)

    return InstanceAllocation(
        slot=slot,
        slot_root=slot_root,
        patvs_root=patvs_root,
        config_root=config_root,
        meta_path=meta_path,
    )


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
    # 加锁
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)


def _release_lock(lock_file: IO[str]) -> None:
    # 释放
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _next_available_slot(instances_root: Path) -> int:
    """
    返回第一个未被占用的 slot 号
    """
    slot = 1
    while True:
        slot_root = instances_root / f"slot-{slot}"
        if not _is_slot_active(slot_root):
            return slot
        slot += 1


def _is_slot_active(slot_root: Path) -> bool:
    """
    判断某个 slot 当前是否被占用。
    判定标准： meta.json 存在且记录的 PID 对应的进程仍然存在
    """
    meta_path = slot_root / "meta.json"
    # 如果没有说明没被占用
    if not meta_path.exists():
        return False


    try:
        with meta_path.open("r", encoding="utf-8") as handle:
            meta = json.load(handle)
    except (OSError, json.JSONDecodeError):
        # 出现异常则直接清空并复用
        _safe_remove(meta_path)
        return False

    pid = meta.get("pid")
    # 检查 pid 字段是否合法且进程仍存在
    if not isinstance(pid, int) or not psutil.pid_exists(pid):
        _safe_remove(meta_path)
        return False

    return True


def _write_meta(meta_path: Path, slot: int) -> None:
    # 记录 meta.json
    meta = {
        "slot": slot,
        "pid": os.getpid(),
        "allocated_at": datetime.now(timezone.utc).isoformat(),
    }
    with meta_path.open("w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)


def _register_cleanup(allocation: InstanceAllocation) -> None:
    # 程序退出时执行清理操作
    def _cleanup() -> None:
        try:
            with allocation.meta_path.open("r", encoding="utf-8") as handle:
                meta = json.load(handle)
            # 检查 pid 是否属于当前进程
            if meta.get("pid") != os.getpid():
                return
        except (OSError, json.JSONDecodeError):
            return
        # 清理 meta.json
        _safe_remove(allocation.meta_path)
    # 退出钩子
    atexit.register(_cleanup)


def _safe_remove(path: Path) -> None:
    """删除文件"""
    try:
        path.unlink(missing_ok=True)
    except FileNotFoundError:
        pass

