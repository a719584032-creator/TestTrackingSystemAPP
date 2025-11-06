"""摄像头开关监控（按“开关次数”统计）。"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

import cv2

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction

# 仅探测前三个索引
MAX_MONITORED_DEVICES = 3

# 后端偏好：优先 DSHOW，失败再 MSMF，最后用默认
_BACKENDS = [
    getattr(cv2, "CAP_DSHOW", None),
    getattr(cv2, "CAP_MSMF", None),
    None,
]

def _probe_device(index: int) -> bool:
    """尝试用多个后端打开并读一帧，成功则认为“可调用”，否则“不可调用”。
    无论成功失败都要及时 release()，避免遗留句柄。
    """
    for backend in _BACKENDS:
        cap = None
        try:
            cap = cv2.VideoCapture(index) if backend is None else cv2.VideoCapture(index, backend)
            if not cap.isOpened():
                continue
            # 读一帧来验证可用性；失败视为不可用
            ok, _ = cap.read()
            if ok:
                return True
        except Exception:
            # 各种后端/驱动异常一律吞掉，换下一个后端尝试
            pass
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
    return False


def run(
    context: "Patvs_Fuction",
    target_cycles: float,
    remaining_cycles: Optional[float] = None,
) -> None:
    """检测“摄像头开/关”的**次数**（任意设备的任意一次状态变化都+1），支持断点续跑。"""

    # --- 目标与恢复 ---
    try:
        total_target = float(target_cycles)
    except (TypeError, ValueError):
        total_target = 0.0
    if total_target <= 0:
        context.log("摄像头开关目标次数为 0，自动跳过。")
        context.record_count_progress_if_current(0, 0, expected_keys={"摄像头", "camera"})
        context.log("退出摄像头开关事件监控。")
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

    # 统一口径：completed = total - remaining
    switch_count = max(0.0, total_target - remaining)
    device_states: list[Optional[bool]] = [None] * MAX_MONITORED_DEVICES
    expected_keys = {"摄像头", "camera"}

    if switch_count > 0:
        context.log(f"摄像头开关已累计 {switch_count:g} 次，剩余 {max(0.0, total_target - switch_count):g} 次。")

    # 可选：降低 OpenCV 噪声日志
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        while context.is_running and switch_count < total_target:
            # 每轮只探测前三个索引
            for device_index in range(MAX_MONITORED_DEVICES):
                if not context.is_running:
                    break

                current_state = _probe_device(device_index)  # True=可调用，False=不可用/被占用
                previous_state = device_states[device_index]
                device_states[device_index] = current_state

                # 第一轮没有历史状态，不计数
                if previous_state is None:
                    continue

                # **任意状态变化**都算一次“开关”
                if previous_state != current_state:
                    switch_count += 1
                    context.log(
                        f"检测到摄像头 {device_index} 状态变化："
                        f"{'可调用' if current_state else '被占用/不可用'}，累计开关次数：{switch_count:g}"
                    )
                    context.record_count_progress_if_current(
                        total_target, switch_count, expected_keys=expected_keys
                    )
                    if switch_count >= total_target or not context.is_running:
                        break

            if switch_count >= total_target or not context.is_running:
                break

            # 适当缩短间隔，响应更及时；也可改回 1 秒
            time.sleep(0.5)

        # 结束条件说明
        if switch_count >= total_target:
            context.log(f"摄像头开关次数已达到目标值 ({total_target:g})，退出检测。")
        elif not context.is_running:
            context.log("收到停止请求，退出摄像头开关事件监控。")
    finally:
        # 落盘一次最终进度并唤醒主调度
        context.record_count_progress_if_current(total_target, switch_count, expected_keys=expected_keys)
        context.log("退出摄像头开关事件监控。")
        context.action_complete.set()
