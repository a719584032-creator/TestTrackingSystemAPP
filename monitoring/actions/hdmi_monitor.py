"""显示器（HDMI/DP）插拔监控。"""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Tuple

try:
    import wmi
except ImportError:  # pragma: no cover - 仅在缺少依赖时触发
    wmi = None
import pythoncom
import pywintypes

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction

logger = logging.getLogger(__name__)

# 线程局部变量
_com_state = threading.local()  # 用于存储线程的 COM 初始化状态。
_thread_state = threading.local()  # 用于存储线程的 WMI 客户端实例。


def _ensure_com_initialized() -> None:
    """在当前线程初始化 COM，兼容已初始化的线程。"""

    if getattr(_com_state, "initialized", False):
        return
    try:
        pythoncom.CoInitialize()
    except pywintypes.com_error as exc:  # pragma: no cover - 系统级初始化异常
        # 已在不同模式下初始化过也算可用
        if getattr(exc, "hresult", None) != pythoncom.RPC_E_CHANGED_MODE:
            raise
    _com_state.initialized = True


def _get_wmi_client():
    """按需初始化 WMI 客户端，指向 root\\wmi。"""

    client = getattr(_thread_state, "wmi_client", None)
    if client is None:
        _ensure_com_initialized()
        if wmi is None:
            raise RuntimeError("未安装 wmi 依赖，无法监控显示器插拔")
        client = wmi.WMI(namespace="root\\wmi")
        _thread_state.wmi_client = client
    return client


def _snapshot_connected_monitors() -> Tuple[str, ...]:
    """通过 WmiMonitorId 读取当前显示器列表。"""

    client = _get_wmi_client()
    try:
        # 获取显示器列表
        monitors = client.WmiMonitorId()
    except Exception:
        # 当前线程的 WMI client 可能无效，尝试重建一次
        _thread_state.wmi_client = None
        client = _get_wmi_client()
        monitors = client.WmiMonitorId()
    devices: list[str] = []
    for monitor in monitors:
        ident = getattr(monitor, "InstanceName", None) or getattr(monitor, "DeviceID", None)
        if ident is None:
            # UserFriendlyName 可能是数组，兼容取出字符串
            friendly = getattr(monitor, "UserFriendlyName", None)
            if isinstance(friendly, (list, tuple)):
                friendly_str = "".join(chr(c) for c in friendly if c)
                ident = friendly_str or None
        if ident:
            text = str(ident)
            if text not in devices:
                devices.append(text)
    devices.sort()
    return tuple(devices)


def run(
    context: "Patvs_Fuction",
    target_cycles: float,
    *,
    remaining_cycles: float | None = None,
    poll_interval: float = 1,
) -> None:
    """监控显示器（HDMI/DP）插拔事件，支持断点续跑。"""

    try:
        total_target = float(target_cycles)
    except (TypeError, ValueError):
        total_target = 0.0
    if total_target <= 0:
        context.log("显示器插拔目标次数为 0，自动跳过。")
        context.record_count_progress_if_current(0, 0, expected_keys={"显示器插拔"})
        context.action_complete.set()
        return

    if remaining_cycles is None:
        remaining = total_target
    else:
        try:
            remaining = float(remaining_cycles)
        except (TypeError, ValueError):
            remaining = total_target
    remaining = max(0.0, min(total_target, remaining))
    completed = max(0.0, total_target - remaining)
    expected_keys = {"显示器插拔"}

    if completed > 0:
        context.log(
            f"显示器插拔已累计 {completed:g} 次，剩余 {max(0.0, total_target - completed):g} 次。"
        )

    try:
        last_snapshot = _snapshot_connected_monitors()
    except Exception as exc:  # pragma: no cover - 系统级调用难以稳定覆盖
        logger.exception("初始化显示器列表失败")
        context.log(f"初始化显示器连接状态失败: {exc}")
        context.action_complete.set()
        return

    readable_initial = "; ".join(last_snapshot) if last_snapshot else "未检测到显示器"
    context.log(f"当前检测到的显示器: {readable_initial}")

    # 插拔状态跟踪变量
    cycle_in_progress = False  # 初始插拔状态标记
    change_start_snapshot: Tuple[str, ...] | None = None  # 记录插拔操作开始时的显示器状态

    while context.is_running and completed < total_target:
        time.sleep(poll_interval)

        # 获取当前显示器连接状态快照
        try:
            current_snapshot = _snapshot_connected_monitors()
        except Exception as exc:  # pragma: no cover - 防御系统错误
            logger.warning("读取显示器连接状态失败: %s", exc)
            continue

        # 如果显示器状态没有变化，继续等待
        if current_snapshot == last_snapshot:
            continue

        # ===== 插拔判断核心逻辑 =====
        # 判断原理：
        # 1. 一次完整的插拔操作被定义为：显示器状态发生变化 -> 状态再次变化
        # 2. 使用状态机模式：cycle_in_progress 标记当前是否处于插拔过程中
        # 3. 第一次检测到状态变化：标记插拔开始（cycle_in_progress = True）
        # 4. 第二次检测到状态变化：标记插拔完成（cycle_in_progress = False，计数+1）

        if cycle_in_progress:
            # 情况1：已经在进行插拔操作中，现在检测到第二次状态变化
            # 这标志着一次完整插拔操作的结束（无论是插入->拔出，还是拔出->插入）
            completed += 1.0
            start_snapshot = change_start_snapshot or ()
            context.log("完成一次显示器插拔")

            # 重置插拔状态，准备检测下一次插拔
            cycle_in_progress = False
            change_start_snapshot = None

            # 记录进度
            context.record_count_progress_if_current(
                total_target, completed, expected_keys=expected_keys
            )

            # 检查是否已达到目标次数
            if completed >= total_target:
                last_snapshot = current_snapshot
                break
        else:
            # 情况2：当前没有进行插拔操作，检测到第一次状态变化
            # 这标志着一次插拔操作的开始（可能是插入显示器，也可能是拔出显示器）
            cycle_in_progress = True
            change_start_snapshot = last_snapshot  # 保存变化开始时的状态，用于调试

            context.log(
                f"检测到显示器状态变化（开始）：之前 {len(last_snapshot)} 台，当前 {len(current_snapshot)} 台。"
            )
            # 详细日志
            # if last_snapshot:
            #     context.log(f"之前: {', '.join(last_snapshot)}")
            # if current_snapshot:
            #     context. log(f"当前: {', '. join(current_snapshot)}")

        # 更新上一次状态快照，用于下次比较
        last_snapshot = current_snapshot

    # 记录最终进度并完成
    context.record_count_progress_if_current(total_target, completed, expected_keys=expected_keys)
    if completed >= total_target:
        context.log(f"显示器插拔次数已达到目标 ({total_target:g})，退出监控。")
    else:
        context.log("退出显示器插拔监控。")
    context.action_complete.set()
