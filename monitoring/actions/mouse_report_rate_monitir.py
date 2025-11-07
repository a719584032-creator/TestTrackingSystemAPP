"""时间关键字监控逻辑。"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import time
import threading
import win32api
import win32con
if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction


class MousePollingMonitor:
    def __init__(self,update_interval=0.001, sample_window=1.0):  # 这里将刷新间隔改为0.001秒
        """
        :param update_interval: 回报率刷新间隔（秒），越小刷新越频繁
        :param sample_window: 计算回报率的采样窗口（秒），建议 1 秒
        """
        self.timestamps = []  # 存储鼠标运动事件的时间戳
        self.update_interval = update_interval  # 刷新间隔（秒）
        self.sample_window = sample_window      # 采样窗口（秒）
        self.update_interval = update_interval
        self.running = False                    # 控制程序运行的标志
        self.last_pos = win32api.GetCursorPos() # 记录上一时刻鼠标位置
        self.locations=[]
        self.locations.append(win32api.GetCursorPos())
        self.dpi_store=[]
        self.dpi_=0

        # 新增：记录按键点击次数
        self.left_clicks = 0  # 左键点击次数
        self.right_clicks = 0  # 右键点击次数
        self.last_left_state = 0  # 上一时刻左键状态（0=未按下，1=按下）
        self.last_right_state = 0  # 上一时刻右键状态


    def _detect_movement(self):
        """持续检测鼠标运动，有位移时记录时间戳（同步检测核心）"""
        while self.running:
            # 获取当前鼠标位置
            current_pos = win32api.GetCursorPos()
            # self.locations.append(current_pos)
            # print(self.locations)
            # 若位置变化（鼠标运动），记录当前时间戳
            if current_pos != self.last_pos:
                self.timestamps.append(time.perf_counter())  # 高精度时间戳
                self.dpi_=self.calculate_dpi(current_pos)
                self.last_pos = current_pos  # 更新位置
                self._clean_old_timestamps()  # 清理过期数据
                # print("DPI:",dpi)
                # print(self._calculate_rate(), "Hz")
                self.context.log(self._calculate_rate()," Hz")
            else:
                self.context.log("0 Hz")
            time.sleep(0.0001)
    def click_ponits(self):
        current_left = win32api.GetKeyState(win32con.VK_LBUTTON) & 0x8000
        current_right = win32api.GetKeyState(win32con.VK_RBUTTON) & 0x8000
        # print(current_left,current_right)
        # 左键从"未按下"到"按下"时计数+1（避免长按重复计数）
        if current_left and not self.last_left_state:
            self.left_clicks += 1
        # 右键同理
        if current_right and not self.last_right_state:
            self.right_clicks += 1

        # 更新按键状态记录
        self.last_left_state = current_left
        self.last_right_state = current_right

    def calculate_dpi(self,current_pos):
        dpi_x = abs(current_pos[0] - self.last_pos[0])
        dpi_y = abs(current_pos[1] - self.last_pos[1])
        dpi = (dpi_x ** 2 + dpi_y ** 2) ** 0.5
        return dpi

    def _clean_old_timestamps(self):
        """清理采样窗口外的旧时间戳，避免数据堆积"""
        if not self.timestamps:
            return
        # 计算采样窗口的起始时间（当前时间 - 窗口时长）
        cutoff_time = time.perf_counter() - self.sample_window
        # 移除所有早于起始时间的旧数据
        while self.timestamps and self.timestamps[0] < cutoff_time:
            self.timestamps.pop(0)

    def _calculate_rate(self):
        """根据采样窗口内的事件计算回报率（Hz）"""
        if len(self.timestamps) < 2:
            return 0  # 事件太少，无法计算
        # 采样窗口的实际时长（最后一个事件 - 第一个事件）
        duration = self.timestamps[-1] - self.timestamps[0]
        if duration <= 0:
            return 0
        # 回报率 = 事件数量 / 窗口时长（每秒事件数）
        return int(len(self.timestamps) / duration)

    # def start(self):
    #     """启动监控（同步检测+实时打印）"""
    #     self.running = True
    #     detect_thread = threading.Thread(target=self._detect_movement)
    #     detect_thread.start()
        # try:
        #     while self.running:
        #         time.sleep(0.01)
        #
        # except KeyboardInterrupt:
        #     self.running = False
        #     print("\n监控已停止")


def run(context: "Patvs_Fuction",
        remaining_seconds: float,
        total_seconds: float) -> None:
    """执行时间监控，支持断点续跑。"""
    try:
        total_seconds = max(0, int(math.ceil(float(total_seconds))))
    except (TypeError, ValueError):
        total_seconds = 0
    try:
        remaining = max(0, int(math.ceil(float(remaining_seconds))))
    except (TypeError, ValueError):
        remaining = total_seconds

    if total_seconds == 0:
        context.log("时间关键字为 0，视为立即完成。")
        context.log("时间监控已完成，可以提交通过结果")
        context._record_time_progress(0)
        context.action_complete.set()
        return

    spent = total_seconds - remaining
    minutes = total_seconds / 60
    if remaining <= 0:
        context.log("时间监控剩余时间为 0，视为已完成。")
        context.log("时间监控已完成，可以提交通过结果")
        context._record_time_progress(0)
        context.action_complete.set()
        return

    if spent > 0:
        context.log(f"时间监控已累计执行 {spent} 秒，剩余 {remaining} 秒。")
    else:
        context.log(f"该用例需要执行 {minutes:g} 分钟，共 {total_seconds} 秒。")

    try:
        report_rate_ = MousePollingMonitor()
        detect_thread = threading.Thread(target=report_rate_._detect_movement)
        detect_thread.start()
        while context.is_running and remaining > 0:
            context.log(f"倒计时：剩余 {remaining} 秒")
            time.sleep(1)
            remaining -= 1
            context._record_time_progress(remaining)

        if context.is_running and remaining == 0:
            report_rate_.running = False
            detect_thread.join()
            context.log("时间监控已完成，可以提交通过结果")
        else:
            report_rate_.running = False
            detect_thread.join()
            context.log("时间监控已停止")
    finally:
        report_rate_.running = False
        detect_thread.join()
        context.log("已停止测试时间监控")
        context._record_time_progress(remaining)
        context.action_complete.set()
