# -*- coding: utf-8 -*-
# 负责监控逻辑
from PyQt5 import QtCore
import logging

from .devicerm import Notification
from .lock_screen import monitor_locks
from .audio_event_constants import AUDIO_EVENT_KEYWORDS
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import time
import psutil
import win32evtlog
import win32evtlogutil
import pytz
import datetime
from pynput import keyboard
from cryptography.fernet import Fernet
import os
import json
import threading
import screen_brightness_control as sbc
import cv2


logger = logging.getLogger(__name__)


class _WxCompat:
    """Compatibility shim so legacy monitoring logic can run under PyQt."""

    @staticmethod
    def CallAfter(func, *args, **kwargs):
        QtCore.QTimer.singleShot(0, lambda: func(*args, **kwargs))

    class _App:
        @staticmethod
        def ExitMainLoop():  # pragma: no cover - compatibility helper
            pass

    @staticmethod
    def GetApp():  # pragma: no cover - compatibility helper
        return _WxCompat._App()


wx = _WxCompat()

# Windows API 常量
MONITOR_OFF = 2  # 显示器关闭状态
MONITOR_ON = -1  # 显示器打开状态


class Patvs_Fuction():
    TEMP_FILE = r"C:\PATVS\temp_action_and_num.json"
    ENCRYPTION_KEY = b'JZfpG9N5K4PQoQMtImxPv80DS-D-WPXr9DN0eF7zhR4='  # 32 bytes URL-safe base64-encoded key
    # 定义按键映射字典，将用户友好的名称映射到 pynput 的按键
    KEY_MAPPING = {
        'alt': keyboard.Key.alt,
        'alt_l': keyboard.Key.alt_l,
        'alt_r': keyboard.Key.alt_r,
        'alt_gr': keyboard.Key.alt_gr,
        'backspace': keyboard.Key.backspace,
        'caps_lock': keyboard.Key.caps_lock,
        'cmd': keyboard.Key.cmd,
        'cmd_l': keyboard.Key.cmd_l,
        'cmd_r': keyboard.Key.cmd_r,
        'ctrl': keyboard.Key.ctrl,
        'ctrl_l': keyboard.Key.ctrl_l,
        'ctrl_r': keyboard.Key.ctrl_r,
        'delete': keyboard.Key.delete,
        'down': keyboard.Key.down,
        'end': keyboard.Key.end,
        'enter': keyboard.Key.enter,
        'esc': keyboard.Key.esc,
        'f1': keyboard.Key.f1,
        'f2': keyboard.Key.f2,
        'f3': keyboard.Key.f3,
        'f4': keyboard.Key.f4,
        'f5': keyboard.Key.f5,
        'f6': keyboard.Key.f6,
        'f7': keyboard.Key.f7,
        'f8': keyboard.Key.f8,
        'f9': keyboard.Key.f9,
        'f10': keyboard.Key.f10,
        'f11': keyboard.Key.f11,
        'f12': keyboard.Key.f12,
        'f13': keyboard.Key.f13,
        'f14': keyboard.Key.f14,
        'f15': keyboard.Key.f15,
        'home': keyboard.Key.home,
        'left': keyboard.Key.left,
        'page_down': keyboard.Key.page_down,
        'page_up': keyboard.Key.page_up,
        'right': keyboard.Key.right,
        'shift': keyboard.Key.shift,
        'shift_l': keyboard.Key.shift_l,
        'shift_r': keyboard.Key.shift_r,
        'space': keyboard.Key.space,
        'tab': keyboard.Key.tab,
        'up': keyboard.Key.up,
        'media_play_pause': keyboard.Key.media_play_pause,
        'media_volume_mute': keyboard.Key.media_volume_mute,
        'media_volume_down': keyboard.Key.media_volume_down,
        'media_volume_up': keyboard.Key.media_volume_up,
        'media_previous': keyboard.Key.media_previous,
        'media_next': keyboard.Key.media_next,
        'insert': keyboard.Key.insert,
        'menu': keyboard.Key.menu,
        'num_lock': keyboard.Key.num_lock,
        'pause': keyboard.Key.pause,
        'prtsc': keyboard.Key.print_screen,
        'scrlk': keyboard.Key.scroll_lock,
        'a': keyboard.KeyCode.from_char('a'),
        'b': keyboard.KeyCode.from_char('b'),
        'c': keyboard.KeyCode.from_char('c'),
        'd': keyboard.KeyCode.from_char('d'),
        'e': keyboard.KeyCode.from_char('e'),
        'f': keyboard.KeyCode.from_char('f'),
        'g': keyboard.KeyCode.from_char('g'),
        'h': keyboard.KeyCode.from_char('h'),
        'i': keyboard.KeyCode.from_char('i'),
        'j': keyboard.KeyCode.from_char('j'),
        'k': keyboard.KeyCode.from_char('k'),
        'l': keyboard.KeyCode.from_char('l'),
        'm': keyboard.KeyCode.from_char('m'),
        'n': keyboard.KeyCode.from_char('n'),
        'o': keyboard.KeyCode.from_char('o'),
        'p': keyboard.KeyCode.from_char('p'),
        'q': keyboard.KeyCode.from_char('q'),
        'r': keyboard.KeyCode.from_char('r'),
        's': keyboard.KeyCode.from_char('s'),
        't': keyboard.KeyCode.from_char('t'),
        'u': keyboard.KeyCode.from_char('u'),
        'v': keyboard.KeyCode.from_char('v'),
        'w': keyboard.KeyCode.from_char('w'),
        'x': keyboard.KeyCode.from_char('x'),
        'y': keyboard.KeyCode.from_char('y'),
        'z': keyboard.KeyCode.from_char('z'),
        '`': keyboard.KeyCode.from_char('`'),
        '1': keyboard.KeyCode.from_char('1'),
        '2': keyboard.KeyCode.from_char('2'),
        '3': keyboard.KeyCode.from_char('3'),
        '4': keyboard.KeyCode.from_char('4'),
        '5': keyboard.KeyCode.from_char('5'),
        '6': keyboard.KeyCode.from_char('6'),
        '7': keyboard.KeyCode.from_char('7'),
        '8': keyboard.KeyCode.from_char('8'),
        '9': keyboard.KeyCode.from_char('9'),
        '0': keyboard.KeyCode.from_char('0'),
        '-': keyboard.KeyCode.from_char('-'),
        '=': keyboard.KeyCode.from_char('='),
        '[': keyboard.KeyCode.from_char('['),
        ']': keyboard.KeyCode.from_char(']'),
        '\\': keyboard.KeyCode.from_char('\\'),  # 单反斜杠
        ';': keyboard.KeyCode.from_char(';'),
        ',': keyboard.KeyCode.from_char(','),
        '.': keyboard.KeyCode.from_char('.'),
        '/': keyboard.KeyCode.from_char('/')
    }

    def __init__(self, window, stop_event):
        self.window = window
        self.stop_event = stop_event
        # 读取临时文件
        self.remaining_actions = []
        self.case_id = None
        self.action_complete = threading.Event()
        self.msg_loop_thread_id = None
        self.audio_log_files = []
        self.audio_log_offsets = {}
        self.audio_event_cache = {}

    def update_audio_log_files(self, files):
        """更新需要监控的音频日志文件列表。"""
        # 使用 ``dict.fromkeys`` 去重同时保持原有顺序
        self.audio_log_files = list(dict.fromkeys(files))

    def initialize_audio_monitor_state(self, offsets=None):
        """重置音频日志监控的偏移量和缓存计数。"""
        self.audio_log_offsets = {}
        if offsets:
            for path, position in offsets.items():
                self.audio_log_offsets[path] = position
        self.audio_event_cache = {}

    def monitor_time(self, num_time):
        """
        监控时间
        """
        count = 0
        num_time = num_time * 60
        wx.CallAfter(self.window.add_log_message, f"执行时间: {num_time} 秒")
        try:
            while self.stop_event and count < num_time:
                count += 1
                time.sleep(1)
                wx.CallAfter(self.window.add_log_message, f"Running time {count} of ")
        finally:
            wx.CallAfter(self.window.add_log_message, "已停止测试时间监控")
            self.action_complete.set()  # 设置动作完成状态

    def monitor_power_plug_changes(self, target_cycles, power_done_event=None):
        """
        监控电源插拔次数
        """
        # battery.percent  # 电量百分比
        # battery.power_plugged  # 是否连接电源
        # battery.secsleft  # 剩余时间（秒），未充电时可用
        plugged_in_last_state = None
        plug_unplug_cycles = 0
        try:
            while self.stop_event and plug_unplug_cycles < target_cycles:
                battery = psutil.sensors_battery()
                if battery:
                    plugged_in = battery.power_plugged
                    # 初次运行时设定初始电源状态
                    if plugged_in_last_state is None:
                        plugged_in_last_state = plugged_in

                    # 当电源状态改变时
                    if plugged_in != plugged_in_last_state:
                        plugged_in_last_state = plugged_in

                        # 当检测到拔出动作后计算一次周期
                        if not plugged_in:
                            plug_unplug_cycles += 1
                            message = f"电源插拔完成次数: {plug_unplug_cycles}"
                            wx.CallAfter(self.window.add_log_message, message)
                        if plug_unplug_cycles >= target_cycles:
                            wx.CallAfter(self.window.add_log_message,
                                         f"已完成目标插拔次数:{plug_unplug_cycles} ，Exiting....")
                            break
                else:
                    logger.error("No battery information found")
                    break
                time.sleep(1)
        finally:
            wx.CallAfter(self.window.add_log_message, "已停止电源插拔监控")
            if power_done_event:
                power_done_event.set()
            else:
                self.action_complete.set()  # 设置动作完成状态

    def monitor_s3_and_power(self, start_time, target_cycles):
        wx.CallAfter(self.window.add_log_message, f"开始执行监控: S3电源插拔，目标测试次数: {target_cycles}")
        for i in range(int(target_cycles)):
            # S3一次
            s3_done_event = threading.Event()
            s3_thread = threading.Thread(
                target=self.test_count_s3_sleep_events,
                args=(start_time, i+1, s3_done_event)
            )
            s3_thread.start()
            s3_done_event.wait()
            s3_thread.join()

            # 插拔一次
            power_done_event = threading.Event()
            power_thread = threading.Thread(
                target=self.monitor_power_plug_changes,
                args=(1, power_done_event)
            )
            power_thread.start()
            power_done_event.wait()
            power_thread.join()

            wx.CallAfter(self.window.add_log_message, f"已完成第{i + 1}轮插拔+S3")

        wx.CallAfter(self.window.add_log_message, "所有插拔+S3循环已完成！")
        self.action_complete.set()

    # def monitor_s3_and_power(self, start_time, s3_target_cycles, power_target_cycles):
    #     # 创建事件对象，用于标记 S3 和 电源插拔 是否完成
    #     s3_done_event = threading.Event()
    #     power_done_event = threading.Event()
    #
    #     # 启动 S3 和 USB 的监控线程
    #     s3_thread = threading.Thread(
    #         target=self.test_count_s3_sleep_events,
    #         args=(start_time, s3_target_cycles, s3_done_event)
    #     )
    #     power_thread = threading.Thread(
    #         target=self.monitor_power_plug_changes,
    #         args=(power_target_cycles, power_done_event)
    #     )
    #
    #     s3_thread.start()
    #     power_thread.start()
    #     # 等待两个事件都完成
    #     while not (s3_done_event.is_set() and power_done_event.is_set()):
    #         time.sleep(0.5)
    #
    #     # 确保所有线程退出
    #     self.action_complete.set()
    #     s3_thread.join()
    #     power_thread.join()
    #     wx.CallAfter(self.window.add_log_message, "S3 和 电源 插拔监控已完成。")

    def test_count_s3_sleep_events(self, start_time, target_cycles, s3_done_event=None):
        def reopen_event_log():
            """尝试打开事件日志句柄，返回句柄或 None"""
            try:
                return win32evtlog.OpenEventLog(None, "System")
            except Exception as e:
                wx.CallAfter(self.window.add_log_message, f"Failed to open event log: {e}")
                return None

        hand = reopen_event_log()
        if hand is None:
            return  # 如果无法打开句柄，退出

        flags = win32evtlog.EVENTLOG_FORWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        total = 0
        log_num = 0
        start_time = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")

        try:
            while self.stop_event:
                if not hand:  # 检查句柄是否有效
                    hand = reopen_event_log()
                    if hand is None:
                        time.sleep(1)
                        continue
                try:
                    events = win32evtlog.ReadEventLog(hand, flags, 0)
                    if not events:
                        # 关闭当前句柄并重新打开
                        win32evtlog.CloseEventLog(hand)
                        hand = reopen_event_log()
                        total = 0
                        time.sleep(1)
                        continue
                except Exception as e:
                    logger.warning(f"Error reading event log: {e}")
                    if hand:
                        try:
                            win32evtlog.CloseEventLog(hand)
                        except Exception as close_e:
                            logger.warning(f"Error closing event log: {close_e}")
                    hand = reopen_event_log()
                    total = 0
                    time.sleep(1)
                    continue

                for event in events:
                    if event.EventID in (507, 107):
                        occurred_time = event.TimeGenerated
                        if occurred_time > start_time:
                            total += 1

                # 输出增量日志，如果total比上一次记录的last_total大，则说明有新日志
                if total > log_num:
                    wx.CallAfter(self.window.add_log_message,
                                 f"当前已测试S3 {total} 次，目标次数为 {target_cycles} 次。")
                    log_num = total

                if total >= target_cycles:
                    wx.CallAfter(self.window.add_log_message,
                                 f"已完成目标S3次数: {total}")
                    return
        finally:
            if hand:
                try:
                    win32evtlog.CloseEventLog(hand)
                except Exception as e:
                    logger.warning(f"S3 Final close error: {e}")
            wx.CallAfter(self.window.add_log_message, "停止S3事件监控.")
            # 兼容单个调用和S3插拔时调用
            if s3_done_event:  # 如果事件对象存在，则设置它
                s3_done_event.set()
            else:
                self.action_complete.set()  # 设置动作完成状态

    def get_event_data(self, event):
        # 获取详细信息中的 EventData
        strings = win32evtlogutil.SafeFormatMessage(event, 'System')
        return strings

    def parse_time(self, time_str):
        time_str = time_str.strip()  # 移除空格
        try:
            # 去除小数秒部分，只保留到秒级别
            if '.' in time_str:
                time_str = time_str.split('.')[0]
            utc_time = datetime.datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S")
            # 设置为UTC时区
            utc_time = utc_time.replace(tzinfo=pytz.utc)
            # 转换为东8区时间
            beijing_time = utc_time.astimezone(pytz.timezone('Asia/Shanghai'))
            # 格式化为所需字符串格式，不包含时区信息
            formatted_time = datetime.datetime.strptime(beijing_time.strftime("%Y-%m-%d %H:%M:%S"), "%Y-%m-%d %H:%M:%S")
            return formatted_time
        except ValueError as e:
            # 解析失败，返回None
            logger.error(f'{e}')
            return None

    def monitor_s3_and_usb(self, start_time, s3_target_cycles, usb_target_cycles):
        # 创建事件对象，用于标记 S3 和 USB 是否完成
        s3_done_event = threading.Event()
        usb_done_event = threading.Event()

        # 启动 S3 和 USB 的监控线程
        s3_thread = threading.Thread(
            target=self.test_count_s3_sleep_events,
            args=(start_time, s3_target_cycles, s3_done_event)
        )
        usb_thread = threading.Thread(
            target=self.monitor_device_plug_changes,
            args=(usb_target_cycles, usb_done_event)
        )

        s3_thread.start()
        usb_thread.start()
        self.msg_loop_thread_id = usb_thread.ident
        # 等待两个事件都完成
        while not (s3_done_event.is_set() and usb_done_event.is_set()):
            time.sleep(0.5)

        # 确保所有线程退出
        self.action_complete.set()
        s3_thread.join()
        usb_thread.join()

        wx.CallAfter(self.window.add_log_message, "S3 和 USB 插拔监控已完成。")

    # def monitor_s3_and_usb(self, start_time, target_cycles):
    #     for i in range(int(target_cycles)):
    #         # 1. 等待一次S3
    #         s3_done_event = threading.Event()
    #         s3_thread = threading.Thread(
    #             target=self.test_count_s3_sleep_events,
    #             args=(start_time, i+1, s3_done_event)
    #         )
    #         s3_thread.start()
    #         s3_done_event.wait()
    #         s3_thread.join()
    #         wx.CallAfter(self.window.add_log_message, f"第{i + 1}轮：S3完成")
    #
    #         # 2. 等待一次USB插拔
    #         usb_done_event = threading.Event()
    #         usb_thread = threading.Thread(
    #             target=self.monitor_device_plug_changes,
    #             args=(2, usb_done_event)
    #         )
    #         usb_thread.start()
    #         usb_done_event.wait()
    #         usb_thread.join()
    #         wx.CallAfter(self.window.add_log_message, f"第{i + 1}轮：USB插拔完成")
    #
    #     wx.CallAfter(self.window.add_log_message, "所有USB插拔+S3循环已完成！")
    #     self.action_complete.set()

    # def test_count_s4_sleep_events(self, start_time, target_cycles):
    #     def reopen_event_log():
    #         """尝试打开事件日志句柄，返回句柄或 None"""
    #         try:
    #             return win32evtlog.OpenEventLog(None, "System")
    #         except Exception as e:
    #             wx.CallAfter(self.window.add_log_message, f"Failed to open event log: {e}")
    #             return None
    #
    #     hand = reopen_event_log()
    #     if hand is None:
    #         return  # 如果无法打开句柄，退出
    #
    #     flags = win32evtlog.EVENTLOG_FORWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
    #     total = 0
    #     log_num = 0
    #     start_time = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    #     try:
    #         while self.stop_event:
    #             if not hand:  # 检查句柄是否有效
    #                 hand = reopen_event_log()
    #                 if hand is None:
    #                     time.sleep(1)
    #                     continue
    #             try:
    #                 events = win32evtlog.ReadEventLog(hand, flags, 0)
    #                 if not events:
    #                     # 关闭当前句柄并重新打开
    #                     win32evtlog.CloseEventLog(hand)
    #                     hand = reopen_event_log()
    #                     total = 0
    #                     time.sleep(1)
    #                     continue
    #             except Exception as e:
    #                 logger.warning(f"Error reading event log: {e}")
    #                 if hand:
    #                     try:
    #                         win32evtlog.CloseEventLog(hand)
    #                     except Exception as close_e:
    #                         logger.warning(f"Error closing event log: {close_e}")
    #                 hand = reopen_event_log()
    #                 total = 0
    #                 time.sleep(1)
    #                 continue
    #
    #             for event in events:
    #                 if event.EventID == 1:
    #                     # 解析 EventData 获取 SleepTime 和 WakeTime
    #                     event_data = self.get_event_data(event)
    #                     sleep_time = None
    #                     wake_time = None
    #                     for line in event_data.split('\n'):
    #                         if "睡眠时间" in line or "Sleep Time" in line:
    #                             sleep_time = self.parse_time(line.split(": ")[1])
    #                         elif "唤醒时间" in line or "Wake Time" in line:
    #                             wake_time = self.parse_time(line.split(": ")[1])
    #                     # 统计S4事件次数
    #                     if sleep_time and wake_time:
    #                         if sleep_time > start_time and wake_time > sleep_time:
    #                             total += 1
    #                             if total > log_num:  # 仅输出增量日志
    #                                 wx.CallAfter(self.window.add_log_message,
    #                                              f"当前已测试 {total} 次，目标次数为 {target_cycles} 次。")
    #                                 wx.CallAfter(self.window.add_log_message,
    #                                              f'SleepTime: {sleep_time}, WakeTime: {wake_time}')
    #                             if total >= target_cycles:
    #                                 wx.CallAfter(self.window.add_log_message,
    #                                              f"已完成目标S4次数: {total}")
    #                                 return
    #     finally:
    #         wx.CallAfter(self.window.add_log_message, "停止S4事件监控.")
    #         if hand:
    #             try:
    #                 win32evtlog.CloseEventLog(hand)
    #             except Exception as e:
    #                 logger.warning(f"S4 Final close error: {e}")
    #         self.action_complete.set()  # 设置动作完成状态
    def test_count_s4_sleep_events(self, start_time, target_cycles):
        def reopen_event_log():
            """尝试打开事件日志句柄，返回句柄或 None"""
            try:
                return win32evtlog.OpenEventLog(None, "System")
            except Exception as e:
                wx.CallAfter(self.window.add_log_message, f"Failed to open event log: {e}")
                return None

        hand = reopen_event_log()
        if hand is None:
            return  # 如果无法打开句柄，退出
        flags = win32evtlog.EVENTLOG_FORWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        total = 0
        log_num = 0
        start_time = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        try:
            while self.stop_event:
                if not hand:  # 检查句柄是否有效
                    hand = reopen_event_log()
                    if hand is None:
                        time.sleep(1)
                        continue
                try:
                    events = win32evtlog.ReadEventLog(hand, flags, 0)
                    if not events:
                        # 关闭当前句柄并重新打开
                        win32evtlog.CloseEventLog(hand)
                        hand = reopen_event_log()
                        total = 0
                        time.sleep(1)
                        continue
                except Exception as e:
                    logger.warning(f"Error reading event log: {e}")
                    if hand:
                        try:
                            win32evtlog.CloseEventLog(hand)
                        except Exception as close_e:
                            logger.warning(f"Error closing event log: {close_e}")
                    hand = reopen_event_log()
                    total = 0
                    time.sleep(1)
                    continue

                for event in events:
                    if event.EventID == 42:
                        occurred_time = event.TimeGenerated
                        if occurred_time > start_time:
                            total += 1
                # 仅输出增量日志
                if total > log_num:
                    wx.CallAfter(self.window.add_log_message,
                                 f"当前已测试 {total} 次，目标次数为 {target_cycles} 次。")
                    log_num = total
                if total >= target_cycles:
                    wx.CallAfter(self.window.add_log_message,
                                 f"已完成目标S4次数: {target_cycles}")
                    return
        finally:
            wx.CallAfter(self.window.add_log_message, "停止S4事件监控.")
            if hand:
                try:
                    win32evtlog.CloseEventLog(hand)
                except Exception as e:
                    logger.warning(f"S4 Final close error: {e}")
            self.action_complete.set()  # 设置动作完成状态

    def test_count_s5_sleep_events(self, start_time, target_cycles):
        def reopen_event_log():
            """尝试打开事件日志句柄，返回句柄或 None"""
            try:
                return win32evtlog.OpenEventLog(None, "System")
            except Exception as e:
                wx.CallAfter(self.window.add_log_message, f"Failed to open event log: {e}")
                return None

        hand = reopen_event_log()
        if hand is None:
            return  # 如果无法打开句柄，退出
        flags = win32evtlog.EVENTLOG_FORWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        total = 0
        log_num = 0
        start_time = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        try:
            while self.stop_event:
                if not hand:  # 检查句柄是否有效
                    hand = reopen_event_log()
                    if hand is None:
                        time.sleep(1)
                        continue
                try:
                    events = win32evtlog.ReadEventLog(hand, flags, 0)
                    if not events:
                        # 关闭当前句柄并重新打开
                        win32evtlog.CloseEventLog(hand)
                        hand = reopen_event_log()
                        total = 0
                        time.sleep(1)
                        continue
                except Exception as e:
                    logger.warning(f"Error reading event log: {e}")
                    if hand:
                        try:
                            win32evtlog.CloseEventLog(hand)
                        except Exception as close_e:
                            logger.warning(f"Error closing event log: {close_e}")
                    hand = reopen_event_log()
                    total = 0
                    time.sleep(1)
                    continue

                for event in events:
                    if event.EventID == 7001:
                        occurred_time = event.TimeGenerated
                        if occurred_time > start_time:
                            total += 1
                # 仅输出增量日志
                if total > log_num:
                    wx.CallAfter(self.window.add_log_message,
                                 f"当前已测试 {total} 次，目标次数为 {target_cycles} 次。")
                    log_num = total
                if total >= target_cycles:
                    wx.CallAfter(self.window.add_log_message,
                                 f"已完成目标S5次数: {target_cycles}")
                    return
        finally:
            wx.CallAfter(self.window.add_log_message, "停止S5事件监控.")
            if hand:
                try:
                    win32evtlog.CloseEventLog(hand)
                except Exception as e:
                    logger.warning(f"S5 Final close error: {e}")
            self.action_complete.set()  # 设置动作完成状态

    def test_count_restart_events(self, start_time, target_cycles):
        def reopen_event_log():
            """尝试打开事件日志句柄，返回句柄或 None"""
            try:
                return win32evtlog.OpenEventLog(None, "System")
            except Exception as e:
                wx.CallAfter(self.window.add_log_message, f"Failed to open event log: {e}")
                return None

        hand = reopen_event_log()
        if hand is None:
            return  # 如果无法打开句柄，退出
        flags = win32evtlog.EVENTLOG_FORWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        total = 0
        log_num = 0
        start_time = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        try:
            while self.stop_event:
                if not hand:  # 检查句柄是否有效
                    hand = reopen_event_log()
                    if hand is None:
                        time.sleep(1)
                        continue
                try:
                    events = win32evtlog.ReadEventLog(hand, flags, 0)
                    if not events:
                        # 关闭当前句柄并重新打开
                        win32evtlog.CloseEventLog(hand)
                        hand = reopen_event_log()
                        total = 0
                        time.sleep(1)
                        continue
                except Exception as e:
                    logger.warning(f"Error reading event log: {e}")
                    if hand:
                        try:
                            win32evtlog.CloseEventLog(hand)
                        except Exception as close_e:
                            logger.warning(f"Error closing event log: {close_e}")
                    hand = reopen_event_log()
                    total = 0
                    time.sleep(1)
                    continue
                for event in events:
                    event_id = event.EventID & 0xFFFF  # 掩码EventID以获取实际值
                    if event_id == 1074:
                        occurred_time = event.TimeGenerated
                        if occurred_time > start_time:
                            total += 1
                # 仅输出增量日志
                if total > log_num:
                    wx.CallAfter(self.window.add_log_message,
                                 f"当前已测试 {total} 次，目标次数为 {target_cycles} 次。")
                    log_num = total
                if total >= target_cycles:
                    wx.CallAfter(self.window.add_log_message,
                                 f"已完成目标 restart 次数: {target_cycles}")
                    return
        finally:
            wx.CallAfter(self.window.add_log_message, "停止 restart 事件监控.")
            if hand:
                try:
                    win32evtlog.CloseEventLog(hand)
                except Exception as e:
                    logger.warning(f"restart Final close error: {e}")
            self.action_complete.set()  # 设置动作完成状态

    def monitor_device_plug_changes(self, target_cycles, usb_done_event=None):
        notification = Notification(0, target_cycles, self.window)
        try:
            notification.messageLoop()
        finally:
            wx.CallAfter(self.window.add_log_message, "停止 USB 插拔事件监控.")
            # 兼容单个调用和S3时调用
            if usb_done_event:  # 如果事件对象存在，则设置它
                usb_done_event.set()
            else:
                self.action_complete.set()  # 设置动作完成状态

    def monitor_lock_screen_changes(self, target_cycles):
        monitor_locks(target_cycles, self.window)
        self.action_complete.set()  # 设置动作完成状态

    def monitor_keystrokes(self, target_cycles, key_name=None):
        """
        监控任意按键
        """
        try:
            key_count = 0
            listener_stopped = threading.Event()  # 用于指示监听器是否已经停止

            def on_press(pressed_key):
                nonlocal key_count
                key_count += 1
                wx.CallAfter(self.window.add_log_message, f"Key pressed: {pressed_key}. Total count: {key_count}")

                if key_count >= target_cycles:
                    wx.CallAfter(self.window.add_log_message, "检测到已完成目标键盘按键次数. Exiting...")
                    listener_stopped.set()  # 设置监听器已停止的事件
                    return False  # Stop the listener

            def stop_listener(listener):
                # 定期检查 stop_event 和 listener_stopped
                while self.stop_event and not listener_stopped.is_set():
                    time.sleep(0.1)  # 检查间隔

                if not listener_stopped.is_set():  # 如果监听器还没停，则停止它
                    wx.CallAfter(self.window.add_log_message, "程序终止，停止键盘按键监控...")
                    listener.stop()  # 立即停止监听器
                    listener_stopped.set()  # 确保事件被设置

            with keyboard.Listener(on_press=on_press) as listener:
                # 启动后台线程以检查 stop_event
                stop_thread = threading.Thread(target=stop_listener, args=(listener,))
                stop_thread.start()
                listener.join()  # 等待监听器停止
                stop_thread.join()  # 等待后台线程停止
        finally:
            wx.CallAfter(self.window.add_log_message, "停止键盘按键监控")
            self.action_complete.set()  # 设置动作完成状态

    def monitor_keystrokes2(self, target_cycles, key_name=None):
        """
        监控具体按键
        """
        try:
            key_count = 0
            key = self.KEY_MAPPING.get(key_name.lower()) if key_name else None
            listener_stopped = threading.Event()  # 用于指示监听器是否已经停止

            def on_press(pressed_key):
                nonlocal key_count
                if key is None or pressed_key == key:
                    key_count += 1
                    wx.CallAfter(self.window.add_log_message, f"Key pressed: {pressed_key}. Total count: {key_count}")

                if key_count >= target_cycles:
                    wx.CallAfter(self.window.add_log_message, "Reached target keystroke count. Exiting...")
                    listener_stopped.set()  # 设置监听器已停止的事件
                    return False  # Stop the listener

            def stop_listener(listener):
                # 定期检查 stop_event 和 listener_stopped
                while self.stop_event and not listener_stopped.is_set():
                    time.sleep(0.1)  # 检查间隔

                if not listener_stopped.is_set():  # 如果监听器还没停，则停止它
                    wx.CallAfter(self.window.add_log_message, "Stop event triggered. Exiting listener...")
                    listener.stop()  # 立即停止监听器
                    listener_stopped.set()  # 确保事件被设置

            with keyboard.Listener(on_press=on_press) as listener:
                # 启动后台线程以检查 stop_event
                stop_thread = threading.Thread(target=stop_listener, args=(listener,))
                stop_thread.start()
                listener.join()  # 等待监听器停止
                stop_thread.join()  # 等待后台线程停止
        finally:
            wx.CallAfter(self.window.add_log_message, "Stopped monitoring keystrokes.")
            self.action_complete.set()  # 设置动作完成状态

    def monitor_mouse_clicks(self, target_cycles):
        try:
            click_count = 0
            listener_stopped = threading.Event()  # 用于指示监听器是否已经停止

            def on_click(x, y, button, pressed):
                nonlocal click_count
                if pressed:
                    click_count += 1
                    message = f"Mouse clicked at ({x}, {y}) with {button}. Total count: {click_count}"
                    wx.CallAfter(self.window.add_log_message, message)
                    if click_count >= target_cycles:
                        message = "已完成目标点击次数. Exiting..."
                        wx.CallAfter(self.window.add_log_message, message)
                        listener_stopped.set()  # 设置监听器已停止的事件
                        return False  # Stop the listener

            def stop_listener(listener):
                # 定期检查 stop_event 和 listener_stopped
                while self.stop_event and not listener_stopped.is_set():
                    time.sleep(0.1)  # 检查间隔

                if not listener_stopped.is_set():  # 如果监听器还没停，则停止它
                    wx.CallAfter(self.window.add_log_message, "程序终止，停止鼠标点击事件监控...")
                    listener.stop()  # 立即停止监听器
                    listener_stopped.set()  # 确保事件被设置

            with keyboard.Listener(on_click=on_click) as listener:
                # 启动后台线程以检查 stop_event
                stop_thread = threading.Thread(target=stop_listener, args=(listener,))
                stop_thread.start()
                listener.join()  # 等待监听器停止
                stop_thread.join()  # 等待后台线程停止

        finally:
            wx.CallAfter(self.window.add_log_message, "停止鼠标点击事件监控")
            self.action_complete.set()  # 设置动作完成状态

    def monitor_display_status(self, target_cycles):
        """
        监控显示器状态，当连续关闭次数达到目标次数时退出。

        :param target_off_cycles: 显示器连续关闭的目标次数
        """
        previous_brightness = None
        off_cycle_count = 0
        was_display_on = True

        while self.stop_event and off_cycle_count < target_cycles:
            try:
                # 获取当前屏幕亮度
                current_brightness = sbc.get_brightness(display=0)  # 假设只有一个显示器
                wx.CallAfter(self.window.add_log_message, f"当前显示器亮度: {current_brightness}")
                if current_brightness == 0:
                    raise Exception("Brightness is 0, assuming display is off.")

                # 如果亮度正常，更新状态
                if previous_brightness is None:
                    previous_brightness = current_brightness

                was_display_on = True  # 屏幕处于打开状态

            except Exception as e:
                # 当无法获取亮度时，假定屏幕已关闭
                wx.CallAfter(self.window.add_log_message, f"检测到屏幕已关闭: {e}")
                # 仅在屏幕刚从打开变为关闭时计数
                if was_display_on and previous_brightness:
                    off_cycle_count += 1
                    wx.CallAfter(self.window.add_log_message, f"显示器关闭周期完成: {off_cycle_count} 次")
                # 更新状态：屏幕处于关闭状态
                was_display_on = False
                previous_brightness = None

            time.sleep(5)  # 每5秒检测一次
        if self.stop_event:
            wx.CallAfter(self.window.add_log_message, "显示器开关次数已达到目标次数，退出监控。")
        else:
            wx.CallAfter(self.window.add_log_message, "退出显示器开关监控。")
        self.action_complete.set()  # 设置动作完成状态

    def get_volume(self):
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        # 获取当前音量（范围从 0.0 到 1.0）
        current_volume = volume.GetMasterVolumeLevelScalar()
        return current_volume

    def monitor_volume_changes(self, target_change_count):
        """
        监控系统音量变化，当变化次数达到目标次数时退出。

        :param target_change_count: 音量变化的目标次数
        """
        previous_volume = self.get_volume()
        change_count = 0

        wx.CallAfter(self.window.add_log_message, f"初始系统音量: {previous_volume * 100:.2f}%")

        while self.stop_event and change_count < target_change_count:
            time.sleep(1)  # 每秒检测一次
            current_volume = self.get_volume()

            if current_volume != previous_volume:
                change_count += 1
                wx.CallAfter(self.window.add_log_message,
                             f"音量变化次数: {change_count}, 当前音量: {current_volume * 100:.2f}%")
                previous_volume = current_volume
        if self.stop_event:
            wx.CallAfter(self.window.add_log_message, "音量变化次数已达到目标次数，退出监控。")
        else:
            wx.CallAfter(self.window.add_log_message, "退出音量加减事件监控。")
        self.action_complete.set()  # 设置动作完成状态

    def monitor_video_changes(self, target_cycles):
        """
        检测摄像头开关周期，并在达到目标周期次数后退出。

        :param target_cycles: 目标开关周期次数
        :return: None
        """
        cycle_count = 0  # 记录完整的开关周期数
        last_camera_state = None  # 上一次的摄像头状态（True: 被调用, False: 未被调用）
        cycle_started = False  # 标记是否进入了一个开关周期

        while self.stop_event and cycle_count < target_cycles:
            # 尝试打开摄像头
            cap = cv2.VideoCapture(0)
            ret, frame = cap.read()  # 尝试读取帧
            cap.release()  # 释放摄像头资源

            # 当前摄像头状态
            current_camera_state = ret  # True: 摄像头没有被占用 False: 摄像头被占用

            # 检测开关周期
            if last_camera_state is not None:
                if not cycle_started and last_camera_state == True and current_camera_state == False:
                    # 从“没有被占用”切换到“被占用”，标记周期开始
                    cycle_started = True
                    wx.CallAfter(self.window.add_log_message, "检测到摄像头被占用，开关周期开始。")
                elif cycle_started and last_camera_state == False and current_camera_state == True:
                    # 从“被占用”切换回“没有被占用”，标记周期结束
                    cycle_count += 1
                    cycle_started = False
                    wx.CallAfter(self.window.add_log_message,
                                 f"检测到摄像头可以调用，完成一个开关周期！当前周期数：{cycle_count}")
            # 更新上一次的摄像头状态
            last_camera_state = current_camera_state

            # 如果达到目标周期数，退出检测
            if cycle_count >= target_cycles:
                wx.CallAfter(self.window.add_log_message, f"摄像头开关周期数已达到目标值 ({target_cycles})，退出检测。")
                break
            # 等待一段时间后再次检测
            time.sleep(1)

        wx.CallAfter(self.window.add_log_message, "退出摄像头开关事件监控。")
        self.action_complete.set()  # 设置动作完成状态

    def encrypt_data(self, data):
        fernet = Fernet(self.ENCRYPTION_KEY)
        encrypted_data = fernet.encrypt(data.encode())
        return encrypted_data

    def decrypt_data(self, encrypted_data):
        fernet = Fernet(self.ENCRYPTION_KEY)
        decrypted_data = fernet.decrypt(encrypted_data).decode()
        return decrypted_data

    def load_remaining_actions(self):
        if os.path.exists(self.TEMP_FILE):
            with open(self.TEMP_FILE, 'rb') as file:
                encrypted_data = file.read()
                decrypted_data = self.decrypt_data(encrypted_data)
                data = json.loads(decrypted_data)
                if data['case_id'] == self.case_id:
                    return data['actions']
        return []

    def save_remaining_actions(self):
        logger.warning("开始保存临时文件")
        logger.warning(self.remaining_actions)
        data = json.dumps({"case_id": self.case_id, "actions": self.remaining_actions})
        encrypted_data = self.encrypt_data(data)
        with open(self.TEMP_FILE, 'wb') as file:
            file.write(encrypted_data)

    def remove_temp_file(self):
        if os.path.exists(self.TEMP_FILE):
            os.remove(self.TEMP_FILE)

    def normalize_action(self, action):
        """忽略大小写以及空格匹配"""
        return action.lower().replace(" ", "")

    def run_main(self, case_id, action_and_num, start_time):
        try:
            self.case_id = case_id
            self.remaining_actions = self.load_remaining_actions()
            if not self.remaining_actions:
                self.remaining_actions = action_and_num

            # 显示日志信息
            wx.CallAfter(self.window.add_log_message, f"请按照提示依次执行以下动作:")
            for action, test_num in self.remaining_actions:
                if action == '时间':
                    wx.CallAfter(self.window.add_log_message, f"您选择的动作是: {action}，目标测试时间: {test_num} min")
                else:
                    wx.CallAfter(self.window.add_log_message, f"您选择的动作是: {action}，目标测试次数: {test_num}")
            for action, test_num in self.remaining_actions:
                if self.stop_event:
                    display_action = action
                    action = self.normalize_action(action)
                    test_num = float(test_num)
                    # 在每个动作开始前更新临时文件
                    self.save_remaining_actions()
                    # 清除上一个动作的完成状态
                    self.action_complete.clear()
                    if '时间' in action:
                        wx.CallAfter(self.window.add_log_message, f"开始执行监控时间，目标测试时间: {test_num} min")
                        threading.Thread(target=self.monitor_time, args=(test_num,)).start()
                    elif action == '电源插拔':
                        wx.CallAfter(self.window.add_log_message, f"开始执行监控: {action}，目标测试次数: {test_num}")
                        threading.Thread(target=self.monitor_power_plug_changes, args=(test_num,)).start()
                    elif action.lower() == 'usb插拔':
                        wx.CallAfter(self.window.add_log_message, f"开始执行监控: {action}，目标测试次数: {test_num}")
                        thread = threading.Thread(target=self.monitor_device_plug_changes, args=(test_num,))
                        thread.start()
                        # 获取线程ID
                        self.msg_loop_thread_id = thread.ident
                    elif action == '键盘按键':
                        wx.CallAfter(self.window.add_log_message, f"开始执行监控: {action}，目标测试次数: {test_num}")
                        threading.Thread(target=self.monitor_keystrokes, args=(test_num,)).start()
                    elif action == '锁屏':
                        wx.CallAfter(self.window.add_log_message, f"开始执行监控: {action}，目标测试次数: {test_num}")
                        thread = threading.Thread(target=self.monitor_lock_screen_changes, args=(test_num,))
                        thread.start()
                        # 获取线程ID
                        self.msg_loop_thread_id = thread.ident
                    elif action == '鼠标点击':
                        wx.CallAfter(self.window.add_log_message, f"开始执行监控: {action}，目标测试次数: {test_num}")
                        threading.Thread(target=self.monitor_mouse_clicks, args=(test_num,)).start()
                    elif action == 's3':
                        wx.CallAfter(self.window.add_log_message, f"开始执行监控: {action}，目标测试次数: {test_num}")
                        threading.Thread(target=self.test_count_s3_sleep_events, args=(start_time, test_num,)).start()
                    elif action == 's4':
                        wx.CallAfter(self.window.add_log_message, f"开始执行监控: {action}，目标测试次数: {test_num}")
                        threading.Thread(target=self.test_count_s4_sleep_events, args=(start_time, test_num,)).start()
                    elif action == 's5':
                        wx.CallAfter(self.window.add_log_message, f"开始执行监控: {action}，目标测试次数: {test_num}")
                        threading.Thread(target=self.test_count_s5_sleep_events, args=(start_time, test_num,)).start()
                    elif action == 'restart':
                        wx.CallAfter(self.window.add_log_message, f"开始执行监控: {action}，目标测试次数: {test_num}")
                        threading.Thread(target=self.test_count_restart_events, args=(start_time, test_num,)).start()
                    elif action.lower() in self.KEY_MAPPING:
                        wx.CallAfter(self.window.add_log_message,
                                     f"开始执行监控按键: {action}，目标测试次数: {test_num}")
                        threading.Thread(target=self.monitor_keystrokes2, args=(test_num, action,)).start()
                    elif action == 's3插拔':
                        wx.CallAfter(self.window.add_log_message, f"开始执行监控: {action}，目标测试次数: {test_num}")
                        threading.Thread(target=self.monitor_s3_and_usb, args=(start_time, test_num, test_num)).start()
                    elif action == 's3电源插拔':
                        threading.Thread(target=self.monitor_s3_and_power,
                                         args=(start_time, test_num)).start()
                    elif action == '显示器':
                        wx.CallAfter(self.window.add_log_message,
                                     f"开始执行监控: {action} 开关事件，目标测试次数: {test_num}")
                        threading.Thread(target=self.monitor_display_status, args=(test_num,)).start()
                    elif action == '音量':
                        wx.CallAfter(self.window.add_log_message,
                                     f"开始执行监控: {action} 加减事件，目标测试次数: {test_num}")
                        threading.Thread(target=self.monitor_volume_changes, args=(test_num,)).start()
                    elif action == '摄像头':
                        wx.CallAfter(self.window.add_log_message,
                                     f"开始执行监控: {action} 开关事件，目标测试次数: {test_num}")
                        threading.Thread(target=self.monitor_video_changes, args=(test_num,)).start()
                    elif action.lower() == 'camera':
                        wx.CallAfter(self.window.add_log_message,
                                     f"开始执行监控: {action} 开关事件，目标测试次数: {test_num}")
                        threading.Thread(target=self.monitor_video_changes, args=(test_num,)).start()
                    elif action in AUDIO_EVENT_KEYWORDS:
                        wx.CallAfter(self.window.add_log_message,
                                     f"开始执行监控音频事件: {display_action}，目标测试次数: {int(test_num)}")
                        threading.Thread(target=self.monitor_audio_event,
                                         args=(action, test_num, display_action)).start()
                    else:
                        wx.CallAfter(self.window.add_log_message,
                                     f"未匹配到任何监控事项，请检查 {action} 填写是否正确")
                        self.action_complete.set()  # 设置动作完成状态
                    # 等待当前监控动作完成
                    self.action_complete.wait()
                    wx.CallAfter(self.window.add_log_message, f"动作 {action} 完成")
                    # 动作完成后，移除已执行的动作并保存
                    self.remaining_actions = self.remaining_actions[1:]
                    self.save_remaining_actions()
                else:
                    logger.warning("事项block，退出执行")
                    self.remaining_actions = []
            # 检查是否有剩余的动作
            if not self.remaining_actions:
                logger.warning("所有动作执行完毕，开始删除临时文件")
                self.remove_temp_file()
            logger.warning("所有动作执行完毕，解禁按钮")
            time.sleep(1)
            wx.CallAfter(self.window.after_test)
        except Exception as e:
            logger.error(f"未知错误: {e}")

    def on_close(self, event):
        self.save_remaining_actions()
        self.window.Destroy()
        wx.GetApp().ExitMainLoop()

    def monitor_audio_event(self, action_key, target_count, display_action=None):
        """监控音频日志文件中的关键字出现次数。"""
        open_files = []
        try:
            if action_key not in AUDIO_EVENT_KEYWORDS:
                wx.CallAfter(self.window.add_log_message,
                             f"未在音频事件常量中找到 {display_action or action_key} 对应的关键字。")
                return

            keyword = AUDIO_EVENT_KEYWORDS[action_key]
            target_count = int(float(target_count)) if target_count is not None else 0
            target_count = max(0, target_count)

            if target_count == 0:
                wx.CallAfter(self.window.add_log_message,
                             f"音频事件 {display_action or action_key} 目标次数为 0，自动跳过。")
                return

            if not self.audio_log_files:
                wx.CallAfter(self.window.add_log_message,
                             f"未选择任何 Lab Audio 日志文件，无法监控 {display_action or action_key}。")
                return

            current_count = self.audio_event_cache.get(action_key, 0)
            if current_count >= target_count:
                wx.CallAfter(
                    self.window.add_log_message,
                    f"音频事件 {display_action or action_key} 已提前满足目标次数 {target_count}，当前计数 {current_count}。"
                )
                return

            for path in self.audio_log_files:
                try:
                    file_obj = open(path, 'r', encoding='utf-8', errors='ignore')
                    start_pos = self.audio_log_offsets.get(path)
                    if start_pos is None:
                        file_obj.seek(0, os.SEEK_END)
                    else:
                        file_obj.seek(start_pos)
                    open_files.append((path, file_obj))
                except Exception as file_error:
                    logger.error(f"无法打开音频日志文件 {path}: {file_error}")
                    wx.CallAfter(self.window.add_log_message,
                                 f"无法打开音频日志文件 {path}: {file_error}")

            if not open_files:
                wx.CallAfter(self.window.add_log_message,
                             f"无法监控 {display_action or action_key}，音频日志文件打开失败。")
                return

            wx.CallAfter(
                self.window.add_log_message,
                f"开始监控音频事件 {display_action or action_key}，目标 {target_count} 次，关键字: {keyword}"
            )
            if current_count > 0:
                wx.CallAfter(
                    self.window.add_log_message,
                    f"音频事件 {display_action or action_key} 当前已有计数 {current_count}/{target_count}。"
                )

            while self.stop_event and current_count < target_count:
                progress_made = False
                for path, file_obj in open_files:
                    line = file_obj.readline()
                    while line:
                        progress_made = True
                        for normalized_key, event_keyword in AUDIO_EVENT_KEYWORDS.items():
                            if event_keyword in line:
                                cached = self.audio_event_cache.get(normalized_key, 0) + 1
                                self.audio_event_cache[normalized_key] = cached
                                if normalized_key == action_key:
                                    current_count = cached
                                    wx.CallAfter(
                                        self.window.add_log_message,
                                        f"[{os.path.basename(path)}] 检测到 {keyword} ({current_count}/{target_count})"
                                    )
                        line = file_obj.readline()
                    self.audio_log_offsets[path] = file_obj.tell()
                    if current_count >= target_count or not self.stop_event:
                        break
                if current_count >= target_count or not self.stop_event:
                    break
                if not progress_made:
                    time.sleep(0.5)

            if current_count >= target_count:
                wx.CallAfter(
                    self.window.add_log_message,
                    f"音频事件 {display_action or action_key} 已达到目标次数 {target_count}。"
                )
            else:
                wx.CallAfter(
                    self.window.add_log_message,
                    f"音频事件 {display_action or action_key} 监控结束，当前计数 {current_count}/{target_count}。"
                )
        except Exception as error:
            logger.error(f"监控音频事件 {display_action or action_key} 出现异常: {error}")
            wx.CallAfter(self.window.add_log_message,
                         f"监控音频事件 {display_action or action_key} 出现异常: {error}")
        finally:
            for _, file_obj in open_files:
                try:
                    file_obj.close()
                except Exception:
                    pass
            self.action_complete.set()


if __name__ == '__main__':
    a = Patvs_Fuction(1, True)
    s3_sleep_count = a.count_s3_sleep_events(start_time='2024/3/19 17:51:50')
    print(f"The system entered S3 sleep state {s3_sleep_count} times.")
