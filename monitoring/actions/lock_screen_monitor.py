"""锁屏事件监控。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..lock_screen import monitor_locks

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


def run(
    context: "Patvs_Fuction",
    target_cycles: float,
    remaining_cycles: float | None = None,
) -> None:
    """启动锁屏监控，支持断点续跑。"""

    monitor_locks(context, target_cycles, remaining_cycles=remaining_cycles)
    context.action_complete.set()
