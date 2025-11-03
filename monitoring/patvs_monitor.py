"""PATVS 监控主调度模块。"""
from __future__ import annotations

import datetime
import json
import logging
import math
import threading
import time
from pathlib import Path
from typing import Callable

import win32evtlog
from cryptography.fernet import Fernet
from pynput import keyboard

from .audio_event_constants import AUDIO_EVENT_KEYWORDS
from .qt_compat import wx
from .actions import (
    audio_event_monitor,
    camera_monitor,
    display_monitor,
    keyboard_any_monitor,
    keyboard_specific_monitor,
    lock_screen_monitor,
    mouse_monitor,
    power_plug_monitor,
    restart_monitor,
    s3_power_cycle_monitor,
    s3_sleep_monitor,
    s3_usb_cycle_monitor,
    s4_sleep_monitor,
    s5_sleep_monitor,
    time_monitor,
    usb_monitor,
    volume_monitor,
)
from config.settings import SETTINGS

logger = logging.getLogger(__name__)


class Patvs_Fuction:
    """负责任务编排的监控上下文。"""

    TEMP_FILE = SETTINGS.monitoring_temp_file
    CACHE_FILE = SETTINGS.monitoring_cache_file
    ENCRYPTION_KEY = b"JZfpG9N5K4PQoQMtImxPv80DS-D-WPXr9DN0eF7zhR4="

    KEY_MAPPING = {
        "alt": keyboard.Key.alt,
        "alt_l": keyboard.Key.alt_l,
        "alt_r": keyboard.Key.alt_r,
        "alt_gr": keyboard.Key.alt_gr,
        "backspace": keyboard.Key.backspace,
        "caps_lock": keyboard.Key.caps_lock,
        "cmd": keyboard.Key.cmd,
        "cmd_l": keyboard.Key.cmd_l,
        "cmd_r": keyboard.Key.cmd_r,
        "ctrl": keyboard.Key.ctrl,
        "ctrl_l": keyboard.Key.ctrl_l,
        "ctrl_r": keyboard.Key.ctrl_r,
        "delete": keyboard.Key.delete,
        "down": keyboard.Key.down,
        "end": keyboard.Key.end,
        "enter": keyboard.Key.enter,
        "esc": keyboard.Key.esc,
        "f1": keyboard.Key.f1,
        "f2": keyboard.Key.f2,
        "f3": keyboard.Key.f3,
        "f4": keyboard.Key.f4,
        "f5": keyboard.Key.f5,
        "f6": keyboard.Key.f6,
        "f7": keyboard.Key.f7,
        "f8": keyboard.Key.f8,
        "f9": keyboard.Key.f9,
        "f10": keyboard.Key.f10,
        "f11": keyboard.Key.f11,
        "f12": keyboard.Key.f12,
        "f13": keyboard.Key.f13,
        "f14": keyboard.Key.f14,
        "f15": keyboard.Key.f15,
        "home": keyboard.Key.home,
        "left": keyboard.Key.left,
        "page_down": keyboard.Key.page_down,
        "page_up": keyboard.Key.page_up,
        "right": keyboard.Key.right,
        "shift": keyboard.Key.shift,
        "shift_l": keyboard.Key.shift_l,
        "shift_r": keyboard.Key.shift_r,
        "space": keyboard.Key.space,
        "tab": keyboard.Key.tab,
        "up": keyboard.Key.up,
        "media_play_pause": keyboard.Key.media_play_pause,
        "media_volume_mute": keyboard.Key.media_volume_mute,
        "media_volume_down": keyboard.Key.media_volume_down,
        "media_volume_up": keyboard.Key.media_volume_up,
        "media_previous": keyboard.Key.media_previous,
        "media_next": keyboard.Key.media_next,
        "insert": keyboard.Key.insert,
        "menu": keyboard.Key.menu,
        "num_lock": keyboard.Key.num_lock,
        "pause": keyboard.Key.pause,
        "prtsc": keyboard.Key.print_screen,
        "scrlk": keyboard.Key.scroll_lock,
        "a": keyboard.KeyCode.from_char("a"),
        "b": keyboard.KeyCode.from_char("b"),
        "c": keyboard.KeyCode.from_char("c"),
        "d": keyboard.KeyCode.from_char("d"),
        "e": keyboard.KeyCode.from_char("e"),
        "f": keyboard.KeyCode.from_char("f"),
        "g": keyboard.KeyCode.from_char("g"),
        "h": keyboard.KeyCode.from_char("h"),
        "i": keyboard.KeyCode.from_char("i"),
        "j": keyboard.KeyCode.from_char("j"),
        "k": keyboard.KeyCode.from_char("k"),
        "l": keyboard.KeyCode.from_char("l"),
        "m": keyboard.KeyCode.from_char("m"),
        "n": keyboard.KeyCode.from_char("n"),
        "o": keyboard.KeyCode.from_char("o"),
        "p": keyboard.KeyCode.from_char("p"),
        "q": keyboard.KeyCode.from_char("q"),
        "r": keyboard.KeyCode.from_char("r"),
        "s": keyboard.KeyCode.from_char("s"),
        "t": keyboard.KeyCode.from_char("t"),
        "u": keyboard.KeyCode.from_char("u"),
        "v": keyboard.KeyCode.from_char("v"),
        "w": keyboard.KeyCode.from_char("w"),
        "x": keyboard.KeyCode.from_char("x"),
        "y": keyboard.KeyCode.from_char("y"),
        "z": keyboard.KeyCode.from_char("z"),
        "`": keyboard.KeyCode.from_char("`"),
        "1": keyboard.KeyCode.from_char("1"),
        "2": keyboard.KeyCode.from_char("2"),
        "3": keyboard.KeyCode.from_char("3"),
        "4": keyboard.KeyCode.from_char("4"),
        "5": keyboard.KeyCode.from_char("5"),
        "6": keyboard.KeyCode.from_char("6"),
        "7": keyboard.KeyCode.from_char("7"),
        "8": keyboard.KeyCode.from_char("8"),
        "9": keyboard.KeyCode.from_char("9"),
        "0": keyboard.KeyCode.from_char("0"),
        "-": keyboard.KeyCode.from_char("-"),
        "=": keyboard.KeyCode.from_char("="),
        "[": keyboard.KeyCode.from_char("["),
        "]": keyboard.KeyCode.from_char("]"),
        "\\": keyboard.KeyCode.from_char("\\"),
        ";": keyboard.KeyCode.from_char(";"),
        ",": keyboard.KeyCode.from_char(","),
        ".": keyboard.KeyCode.from_char("."),
        "/": keyboard.KeyCode.from_char("/"),
    }

    def __init__(self, window, is_running: bool):
        self.window = window
        self.is_running = is_running
        self.logger = logger

        self.remaining_actions: list[dict] = []
        self.case_id: str | None = None
        self.action_complete = threading.Event()
        self.msg_loop_thread_id: int | None = None
        self.audio_log_files: list[str] = []
        self.audio_log_offsets: dict[str, int] = {}
        self.audio_event_cache: dict[str, int] = {}
        self.case_start_time: str | None = None
        self.state_lock = threading.Lock()
        self.session_reset_requested = False

    # ------------------------------------------------------------------
    def log(self, message: str) -> None:
        """统一的日志输出接口，保证在主线程更新界面。"""

        wx.CallAfter(self.window.add_log_message, message)

    def call_after(self, func, *args, **kwargs) -> None:
        """封装 wx.CallAfter，供动作内部复用。"""

        wx.CallAfter(func, *args, **kwargs)

    # ------------------------------------------------------------------
    def _build_action_state(self, action, amount):
        """规范化动作定义，方便持久化与进度跟踪。"""

        normalized = {"name": action, "unit": "count"}
        try:
            numeric_amount = float(amount)
        except (TypeError, ValueError):
            numeric_amount = 0.0
        action_key = action.strip().lower()
        if "时间" in action or action_key == "time":
            seconds = max(0, int(math.ceil(numeric_amount * 60)))
            normalized.update(
                {
                    "target": float(seconds),
                    "remaining": float(seconds),
                    "unit": "seconds",
                }
            )
        else:
            normalized.update(
                {
                    "target": float(max(0.0, numeric_amount)),
                    "remaining": float(max(0.0, numeric_amount)),
                }
            )
        return normalized

    def _normalize_stored_action(self, action):
        """将历史动作数据规整成统一字典格式。"""

        if isinstance(action, dict):
            name = action.get("name") or action.get("action")
            if not name:
                return None
            unit = action.get("unit", "count")
            try:
                target = float(action.get("target", 0))
            except (TypeError, ValueError):
                target = 0.0
            try:
                remaining = float(action.get("remaining", target))
            except (TypeError, ValueError):
                remaining = target
            normalized = {
                "name": name,
                "unit": unit if unit in {"count", "seconds"} else "count",
                "target": max(0.0, target),
                "remaining": max(0.0, remaining),
            }
            name_key = str(name).strip().lower()
            if (
                normalized["unit"] == "seconds"
                and normalized["target"]
                and "时间" not in str(name)
                and name_key != "time"
            ):
                normalized["unit"] = "count"
            return normalized
        if isinstance(action, (list, tuple)) and len(action) == 2:
            return self._build_action_state(action[0], action[1])
        return None

    def _update_current_action_remaining(self, remaining):
        updated = False
        with self.state_lock:
            if self.remaining_actions:
                self.remaining_actions[0]["remaining"] = max(0.0, float(remaining))
                updated = True
        if updated:
            self.save_session_state()

    def _complete_current_action(self):
        removed = False
        with self.state_lock:
            if self.remaining_actions:
                try:
                    remaining = float(self.remaining_actions[0].get("remaining", 0))
                except (TypeError, ValueError):
                    remaining = 0.0
                if remaining <= 0:
                    self.remaining_actions = self.remaining_actions[1:]
                    removed = True
        self.save_session_state()
        return removed

    def _record_count_progress(self, target, completed, action_key=None):
        if action_key is not None:
            with self.state_lock:
                current_name = (
                    self.remaining_actions[0]["name"]
                    if self.remaining_actions
                    else None
                )
            if current_name is None or self.normalize_action(current_name) != action_key:
                return
        try:
            remaining = float(target) - float(completed)
        except (TypeError, ValueError):
            remaining = 0.0
        self._update_current_action_remaining(max(0.0, remaining))

    def record_count_progress_if_current(self, target, completed, expected_keys=None):
        """更新当前动作的次数进度，避免串扰其他动作。"""

        normalized_expected = None
        if expected_keys:
            normalized_expected = {
                self.normalize_action(key)
                for key in expected_keys
                if key is not None
            }
        with self.state_lock:
            if not self.remaining_actions:
                return
            current_name = self.remaining_actions[0]["name"]
        normalized_current = self.normalize_action(current_name)
        if normalized_expected and normalized_current not in normalized_expected:
            return
        self._record_count_progress(target, completed, action_key=normalized_current)

    def _record_time_progress(self, remaining_seconds):
        with self.state_lock:
            current_name = (
                self.remaining_actions[0]["name"]
                if self.remaining_actions
                else None
            )
        if current_name is None:
            return
        normalized = self.normalize_action(current_name)
        if "时间" not in current_name and normalized != "time":
            return
        try:
            remaining = max(0, int(math.ceil(float(remaining_seconds))))
        except (TypeError, ValueError):
            remaining = 0
        self._update_current_action_remaining(remaining)

    def update_audio_log_files(self, files):
        self.audio_log_files = list(dict.fromkeys(files))

    def initialize_audio_monitor_state(self, offsets=None):
        self.audio_log_offsets = {}
        if offsets:
            for path, position in offsets.items():
                self.audio_log_offsets[path] = position
        self.audio_event_cache = {}

    def _normalize_start_time(self, start_time):
        if isinstance(start_time, datetime.datetime):
            return start_time

        if isinstance(start_time, str):
            value = start_time.strip()
            if not value:
                self.logger.warning("Received empty start_time string; defaulting to now.")
                return datetime.datetime.now()

            iso_candidate = value
            if iso_candidate.endswith("Z"):
                iso_candidate = iso_candidate[:-1] + "+00:00"
            try:
                parsed = datetime.datetime.fromisoformat(iso_candidate)
                if parsed.tzinfo is not None:
                    parsed = parsed.astimezone().replace(tzinfo=None)
                return parsed
            except ValueError:
                pass

            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.datetime.strptime(value, fmt)
                except ValueError:
                    continue

        self.logger.error(
            f"Unsupported start_time format: {start_time}, defaulting to current time."
        )
        return datetime.datetime.now()

    def _bootstrap_event_progress(
        self, start_time, match_event: Callable[[object], bool]
    ):
        normalized_start = self._normalize_start_time(start_time)
        count = 0
        last_record_number = 0
        last_event_time = None
        handle = None
        flags = win32evtlog.EVENTLOG_FORWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ

        try:
            handle = win32evtlog.OpenEventLog(None, "System")
        except Exception as exc:
            self.logger.warning(f"Failed to open event log for bootstrap scan: {exc}")
            return normalized_start, 0, 0, normalized_start

        try:
            while True:
                events = win32evtlog.ReadEventLog(handle, flags, 0)
                if not events:
                    break
                for event in events:
                    if match_event(event):
                        occurred_time = event.TimeGenerated
                        if occurred_time > normalized_start:
                            count += 1
                            record_number = getattr(event, "RecordNumber", 0) or 0
                            if record_number > last_record_number:
                                last_record_number = record_number
                            if (
                                last_event_time is None
                                or occurred_time > last_event_time
                            ):
                                last_event_time = occurred_time
        except Exception as exc:
            self.logger.warning(f"Error scanning existing events: {exc}")
        finally:
            if handle:
                try:
                    win32evtlog.CloseEventLog(handle)
                except Exception as close_exc:
                    self.logger.warning(
                        f"Error closing bootstrap event log: {close_exc}"
                    )

        if last_event_time is None:
            last_event_time = normalized_start

        return normalized_start, count, last_record_number, last_event_time

    def encrypt_data(self, data):
        fernet = Fernet(self.ENCRYPTION_KEY)
        return fernet.encrypt(data.encode())

    def decrypt_data(self, encrypted_data):
        fernet = Fernet(self.ENCRYPTION_KEY)
        return fernet.decrypt(encrypted_data).decode()

    def _read_session_payload(self, path: Path):
        try:
            with path.open("rb") as file:
                encrypted_data = file.read()
        except FileNotFoundError:
            return None
        except Exception as exc:
            self.logger.warning(f"读取监控临时文件 {path} 失败: {exc}")
            return None
        if not encrypted_data:
            self.logger.warning(f"监控临时文件 {path} 内容为空，将忽略该文件。")
            return None
        try:
            decrypted_data = self.decrypt_data(encrypted_data)
            data = json.loads(decrypted_data)
        except Exception as exc:
            self.logger.warning(f"解密监控临时文件 {path} 失败: {exc}")
            return None
        return data

    def _persist_session_payload(self, payload):
        try:
            serialized = json.dumps(payload)
        except (TypeError, ValueError) as exc:
            self.logger.warning(f"序列化监控状态失败: {exc}")
            return
        try:
            encrypted_data = self.encrypt_data(serialized)
        except Exception as exc:
            self.logger.warning(f"加密监控状态失败: {exc}")
            return

        for path in {self.TEMP_FILE, self.CACHE_FILE}:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("wb") as file:
                    file.write(encrypted_data)
            except Exception as exc:
                self.logger.warning(f"写入监控临时文件 {path} 失败: {exc}")

    def load_session_state(self):
        data = self._read_session_payload(self.TEMP_FILE)
        restored_from_cache = False
        if data is None:
            data = self._read_session_payload(self.CACHE_FILE)
            if data is not None:
                restored_from_cache = True
                self.logger.warning(
                    "检测到 temp_action_and_num.json 缺失，尝试从备份缓存恢复监控进度。"
                )

        if not data or data.get("case_id") != self.case_id:
            if restored_from_cache and data and data.get("case_id") != self.case_id:
                self.logger.warning("备份缓存中的监控状态与当前用例不匹配，已忽略。")
            return [], None, False

        if restored_from_cache:
            self._persist_session_payload(data)

        normalized_actions = []
        for action in data.get("actions", []):
            normalized = self._normalize_stored_action(action)
            if normalized:
                normalized_actions.append(normalized)
        completed = bool(data.get("completed"))
        if completed and not normalized_actions:
            return [], None, True
        return normalized_actions, data.get("start_time"), completed

    def request_session_reset(self):
        """Mark the current session as invalid so it will not resume next time."""

        self.session_reset_requested = True
        self.remove_temp_file()

    def save_session_state(self):
        if self.session_reset_requested:
            return
        with self.state_lock:
            actions_snapshot = [dict(action) for action in self.remaining_actions]
            start_time = self.case_start_time
            case_id = self.case_id
        session_completed = not actions_snapshot
        logger.debug("开始保存临时文件")
        logger.debug(actions_snapshot)
        payload = {
            "case_id": case_id,
            "actions": actions_snapshot,
            "start_time": start_time,
            "completed": session_completed,
        }
        self._persist_session_payload(payload)

    @classmethod
    def remove_temp_file(cls):
        for path in {cls.TEMP_FILE, cls.CACHE_FILE}:
            try:
                path.unlink(missing_ok=True)
            except Exception as exc:
                logger.warning(f"删除监控临时文件 {path} 失败: {exc}")

    def normalize_action(self, action):
        return action.lower().replace(" ", "")

    def run_main(self, case_id, action_and_num, start_time):
        try:
            self.case_id = case_id
            stored_actions, stored_start_time, session_completed = self.load_session_state()
            if stored_actions:
                self.remaining_actions = stored_actions
                case_start_time = stored_start_time or start_time
            else:
                self.remaining_actions = [
                    self._build_action_state(action, amount)
                    for action, amount in action_and_num
                ]
                case_start_time = start_time
            if isinstance(case_start_time, datetime.datetime):
                case_start_time = case_start_time.isoformat()
            if not case_start_time:
                case_start_time = datetime.datetime.now().isoformat()
            self.case_start_time = case_start_time

            if not stored_actions and session_completed:
                self.logger.warning(
                    "检测到上一次监控已完成，为当前用例重新开始新的监控会话。"
                )

            self.log("请按照提示依次执行以下动作:")
            with self.state_lock:
                actions_snapshot = [dict(action) for action in self.remaining_actions]
            for action_state in actions_snapshot:
                action = action_state["name"]
                target = action_state.get("target", 0)
                remaining = action_state.get("remaining", target)
                unit = action_state.get("unit", "count")
                if unit == "seconds":
                    target_minutes = target / 60 if target else 0
                    remaining_minutes = remaining / 60 if remaining else 0
                    if remaining < target:
                        self.log(
                            f"您选择的动作是: {action}，剩余测试时间: {remaining_minutes:g} min / 总计 {target_minutes:g} min"
                        )
                    else:
                        self.log(
                            f"您选择的动作是: {action}，目标测试时间: {target_minutes:g} min"
                        )
                else:
                    if remaining < target:
                        self.log(
                            f"您选择的动作是: {action}，剩余测试次数: {remaining:g} / 总计 {target:g}"
                        )
                    else:
                        self.log(
                            f"您选择的动作是: {action}，目标测试次数: {target:g}"
                        )

            while self.is_running:
                with self.state_lock:
                    if not self.remaining_actions:
                        break
                    current_action = dict(self.remaining_actions[0])
                action = current_action["name"]
                unit = current_action.get("unit", "count")
                target_value = current_action.get("target", 0)
                remaining_value = current_action.get("remaining", target_value)
                if self.is_running:
                    display_action = action
                    normalized_action = self.normalize_action(action)
                    self.save_session_state()
                    self.action_complete.clear()

                    if "时间" in normalized_action or normalized_action == "time":
                        total_minutes = target_value / 60 if target_value else 0
                        remaining_minutes = remaining_value / 60 if remaining_value else 0
                        self.log(
                            f"开始执行监控时间，目标测试时间: {total_minutes:g} min，剩余 {remaining_minutes:g} min"
                        )
                        threading.Thread(
                            target=time_monitor.run,
                            args=(self, remaining_value, target_value),
                        ).start()
                    elif normalized_action == "电源插拔":
                        self.log(
                            f"开始执行监控: {action}，目标测试次数: {target_value:g}"
                        )
                        threading.Thread(
                            target=power_plug_monitor.run, args=(self, target_value)
                        ).start()
                    elif normalized_action.lower() == "usb插拔":
                        self.log(
                            f"开始执行监控: {action}，目标测试次数: {target_value:g}"
                        )
                        thread = threading.Thread(
                            target=usb_monitor.run, args=(self, target_value)
                        )
                        thread.start()
                        self.msg_loop_thread_id = thread.ident
                    elif normalized_action == "键盘按键":
                        self.log(
                            f"开始执行监控: {action}，目标测试次数: {target_value:g}"
                        )
                        threading.Thread(
                            target=keyboard_any_monitor.run, args=(self, target_value)
                        ).start()
                    elif normalized_action == "锁屏":
                        self.log(
                            f"开始执行监控: {action}，目标测试次数: {target_value:g}"
                        )
                        thread = threading.Thread(
                            target=lock_screen_monitor.run, args=(self, target_value)
                        )
                        thread.start()
                        self.msg_loop_thread_id = thread.ident
                    elif normalized_action == "鼠标点击":
                        self.log(
                            f"开始执行监控: {action}，目标测试次数: {target_value:g}"
                        )
                        threading.Thread(
                            target=mouse_monitor.run, args=(self, target_value)
                        ).start()
                    elif normalized_action == "s3":
                        self.log(
                            f"开始执行监控: {action}，目标测试次数: {target_value:g}"
                        )
                        threading.Thread(
                            target=s3_sleep_monitor.run,
                            args=(self, self.case_start_time, target_value),
                        ).start()
                    elif normalized_action == "s4":
                        self.log(
                            f"开始执行监控: {action}，目标测试次数: {target_value:g}"
                        )
                        threading.Thread(
                            target=s4_sleep_monitor.run,
                            args=(self, self.case_start_time, target_value),
                        ).start()
                    elif normalized_action == "s5":
                        self.log(
                            f"开始执行监控: {action}，目标测试次数: {target_value:g}"
                        )
                        threading.Thread(
                            target=s5_sleep_monitor.run,
                            args=(self, self.case_start_time, target_value),
                        ).start()
                    elif normalized_action == "restart":
                        self.log(
                            f"开始执行监控: {action}，目标测试次数: {target_value:g}"
                        )
                        threading.Thread(
                            target=restart_monitor.run,
                            args=(self, self.case_start_time, target_value),
                        ).start()
                    elif normalized_action.lower() in self.KEY_MAPPING:
                        self.log(
                            f"开始执行监控按键: {action}，目标测试次数: {target_value:g}"
                        )
                        threading.Thread(
                            target=keyboard_specific_monitor.run,
                            args=(self, target_value, action),
                        ).start()
                    elif normalized_action == "s3插拔":
                        self.log(
                            f"开始执行监控: {action}，目标测试次数: {target_value:g}"
                        )
                        threading.Thread(
                            target=s3_usb_cycle_monitor.run,
                            args=(self, self.case_start_time, target_value, target_value),
                        ).start()
                    elif normalized_action == "s3电源插拔":
                        self.log(
                            f"开始执行监控: {action}，目标测试次数: {target_value:g}"
                        )
                        threading.Thread(
                            target=s3_power_cycle_monitor.run,
                            args=(self, self.case_start_time, target_value),
                        ).start()
                    elif normalized_action == "显示器":
                        self.log(
                            f"开始执行监控: {action} 开关事件，目标测试次数: {target_value:g}"
                        )
                        threading.Thread(
                            target=display_monitor.run, args=(self, target_value)
                        ).start()
                    elif normalized_action == "音量":
                        self.log(
                            f"开始执行监控: {action} 加减事件，目标测试次数: {target_value:g}"
                        )
                        threading.Thread(
                            target=volume_monitor.run, args=(self, target_value)
                        ).start()
                    elif normalized_action in {"摄像头", "camera"}:
                        self.log(
                            f"开始执行监控: {action} 开关事件，目标测试次数: {target_value:g}"
                        )
                        threading.Thread(
                            target=camera_monitor.run, args=(self, target_value)
                        ).start()
                    elif normalized_action in AUDIO_EVENT_KEYWORDS:
                        self.log(
                            f"开始执行监控音频事件: {display_action}，目标测试次数: {int(target_value)}"
                        )
                        threading.Thread(
                            target=audio_event_monitor.run,
                            args=(self, normalized_action, target_value, display_action),
                        ).start()
                    else:
                        self.log(f"未匹配到任何监控事项，请检查 {action} 填写是否正确")
                        self.action_complete.set()

                    self.action_complete.wait()
                    remaining_after = 0.0
                    unit_after = unit
                    with self.state_lock:
                        snapshot = (
                            dict(self.remaining_actions[0])
                            if self.remaining_actions
                            else None
                        )
                    if snapshot and snapshot.get("name") == current_action.get("name"):
                        unit_after = snapshot.get("unit", unit)
                        try:
                            remaining_after = float(snapshot.get("remaining", 0))
                        except (TypeError, ValueError):
                            remaining_after = 0.0
                    if remaining_after <= 0:
                        self.log(f"动作 {action} 完成")
                    else:
                        if unit_after == "seconds":
                            self.log(
                                f"动作 {action} 未完成，剩余测试时间: {remaining_after / 60:g} min ({remaining_after:g} 秒)"
                            )
                        else:
                            self.log(
                                f"动作 {action} 未完成，剩余测试次数: {remaining_after:g}"
                            )
                    completed = self._complete_current_action()
                    if not completed:
                        self.log(
                            f"动作 {action} 已暂停，本次监控将保留剩余进度以便下次继续。"
                        )
                        break
                else:
                    self.logger.warning("事项block，退出执行")
                    self.save_session_state()
                    break

            with self.state_lock:
                has_remaining = bool(self.remaining_actions)
            if self.session_reset_requested:
                self.logger.warning("收到会话重置请求，开始删除临时文件")
                self.remove_temp_file()
            elif has_remaining:
                self.logger.warning("检测到未完成的动作，保留临时文件以便下次继续执行")
            else:
                self.logger.warning(
                    "所有动作执行完毕，本次将保留临时文件，确保重启后仍可读取上次执行记录。"
                )
            self.logger.warning("所有动作执行完毕，解禁按钮")
            time.sleep(1)
            self.call_after(self.window.after_test)
        except Exception as e:  # pragma: no cover - 防御性捕获
            self.logger.error(f"未知错误: {e}")

    def on_close(self, event):
        self.save_session_state()
        self.window.Destroy()
        wx.GetApp().ExitMainLoop()
