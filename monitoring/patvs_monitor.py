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

import pywintypes
import win32api
import win32con
import win32evtlog
from cryptography.fernet import Fernet
from pynput import keyboard
from win32print import PRINTER_STATUS_POWER_SAVE

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
    s3_time_monitor,
    s4_time_monitor,
    Tools_Log_monitor,
)

from config.settings import SETTINGS
from .session_store import SessionStateStore

logger = logging.getLogger(__name__)


class Patvs_Fuction:
    """负责任务编排的监控上下文。"""

    TEMP_FILE = SETTINGS.monitoring_temp_file
    CACHE_FILE = SETTINGS.monitoring_cache_file

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
        # 提前点击失败/阻塞使用
        self.is_running = is_running
        self.logger = logger
        # 未完成动作
        self.remaining_actions: list[dict] = []
        self.case_id: str | None = None
        # 动作信号
        self.action_complete = threading.Event()
        # 线程ID，windows消息循环需要使用
        self.msg_loop_thread_id: int | None = None
        self.audio_log_files: list[str] = []
        self.audio_log_offsets: dict[str, int] = {}
        self.audio_event_cache: dict[str, int] = {}
        self.case_start_time: str | None = None
        # 线程锁，保护状态字段的并发访问
        self.state_lock = threading.Lock()
        self.session_reset_requested = False
        # 写文件锁
        self._state_persist_lock = threading.Lock()
        self._pending_state_payload: dict[str, object] | None = None
        self._last_state_persist = 0.0
        # 最小保存间隔
        self._min_state_save_interval = 5.0
        self._last_persisted_payload: dict[str, object] | None = None
        self._encryption_key = SETTINGS.monitoring_encryption_key
        # 监控状态记录
        self.session_store = SessionStateStore(
            self.TEMP_FILE, self.CACHE_FILE, self._encryption_key
        )

    # ------------------------------------------------------------------
    def log(self, message: str) -> None:
        """统一的日志输出接口，保证在主线程更新界面。"""

        wx.CallAfter(self.window.add_log_message, message)

    def call_after(self, func, *args, **kwargs) -> None:
        """封装 wx.CallAfter，供动作内部复用。"""

        wx.CallAfter(func, *args, **kwargs)

    # ------------------------------------------------------------------
    def register_message_loop_thread(self, thread_id: int | None) -> None:
        """记录当前使用消息循环的线程。"""

        with self.state_lock:
            self.msg_loop_thread_id = thread_id

    def clear_message_loop_thread(self, thread_id: int | None = None) -> None:
        """清理消息循环线程 ID，避免后续误用。"""

        with self.state_lock:
            if thread_id is None or self.msg_loop_thread_id == thread_id:
                self.msg_loop_thread_id = None

    def stop_message_loop(self) -> None:
        """尝试停止当前活动的 Windows 消息循环。"""

        with self.state_lock:
            thread_id = self.msg_loop_thread_id
        if not thread_id:
            return
        try:
            win32api.PostThreadMessage(thread_id, win32con.WM_QUIT, 0, 0)
        except pywintypes.error as exc:  # pragma: no cover - 系统级调用难以覆盖
            self.logger.warning("无法停止消息循环线程 %s: %s", thread_id, exc)
        finally:
            self.clear_message_loop_thread(thread_id)

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
            # 时间转成秒
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
        if self.normalize_action(str(action)) == "s3电源插拔":
            normalized.setdefault("s3_progress", 0.0)
            normalized.setdefault("power_progress", 0.0)
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
            if self.normalize_action(name) == "s3电源插拔":
                try:
                    s3_progress = float(action.get("s3_progress", 0.0))
                except (TypeError, ValueError):
                    s3_progress = 0.0
                try:
                    power_progress = float(action.get("power_progress", 0.0))
                except (TypeError, ValueError):
                    power_progress = 0.0
                normalized["s3_progress"] = max(0.0, s3_progress)
                normalized["power_progress"] = max(0.0, power_progress)
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
        """ 更新当前第一个动作的剩余次数，然后保存会话状态。 """
        updated = False
        with self.state_lock:
            if self.remaining_actions:
                self.remaining_actions[0]["remaining"] = max(0.0, float(remaining))
                updated = True
        if updated:
            self.save_session_state()

    def _complete_current_action(self):
        """
        检查当前动作 remaining 是否 <= 0
        如果完成，从 remaining_actions 列表中弹出这一个
        触发 save_session_state(force=removed)，即完成后强制写一遍。
        """
        removed = False
        with self.state_lock:
            if self.remaining_actions:
                try:
                    remaining = float(self.remaining_actions[0].get("remaining", 0))
                except (TypeError, ValueError):
                    remaining = 0.0
                if remaining <= 0:
                    # 完成当前动作后剔除这个动作
                    self.remaining_actions = self.remaining_actions[1:]
                    removed = True
        self.save_session_state(force=removed)
        return removed

    def _record_count_progress(self, target, completed, action_key=None):
        """ 常规“次数类动作”的通用进度更新 """
        normalized_action_key = (
            self.normalize_action(action_key) if action_key is not None else None
        )
        with self.state_lock:
            current_name = (
                self.remaining_actions[0]["name"]
                if self.remaining_actions
                else None
            )
        if current_name is None:
            return
        normalized_current = self.normalize_action(current_name)
        if normalized_current == "s3电源插拔":
            if normalized_action_key == "s3":
                self._record_s3_power_progress(target, s3_completed=completed)
                return
            if normalized_action_key in {None, "电源插拔"}:
                self._record_s3_power_progress(target, power_completed=completed)
                return
        if (
            action_key is not None
            and normalized_action_key is not None
            and normalized_current != normalized_action_key
        ):
            return
        try:
            remaining = float(target) - float(completed)
        except (TypeError, ValueError):
            remaining = 0.0
        self._update_current_action_remaining(max(0.0, remaining))

    def _record_s3_power_progress(
        self,
        target,
        *,
        s3_completed: float | None = None,
        power_completed: float | None = None,
    ) -> None:
        """ 保存S3和电源两个进度，取最小值为准 """
        updated = False
        with self.state_lock:
            if not self.remaining_actions:
                return
            current = self.remaining_actions[0]
            if self.normalize_action(current.get("name", "")) != "s3电源插拔":
                return
            try:
                target_total = float(target)
            except (TypeError, ValueError):
                target_total = float(current.get("target", 0.0) or 0.0)
            target_total = max(0.0, target_total)

            def _clamp(value, default=0.0):
                try:
                    return max(0.0, float(value))
                except (TypeError, ValueError):
                    return default

            if s3_completed is not None:
                new_s3 = _clamp(s3_completed)
                if new_s3 != _clamp(current.get("s3_progress", 0.0)):
                    current["s3_progress"] = new_s3
                    updated = True
            if power_completed is not None:
                new_power = _clamp(power_completed)
                if new_power != _clamp(current.get("power_progress", 0.0)):
                    current["power_progress"] = new_power
                    updated = True

            s3_value = _clamp(current.get("s3_progress", 0.0))
            power_value = _clamp(current.get("power_progress", 0.0))
            combined = min(target_total, s3_value, power_value)
            remaining = max(0.0, target_total - combined)
            if remaining != _clamp(current.get("remaining", target_total), target_total):
                current["remaining"] = remaining
                updated = True
        if updated:
            self.save_session_state()

    def record_count_progress_if_current(self, target, completed, expected_keys=None):
        """
        更新当前动作的次数进度，避免串扰其他动作。
        防止 错把其他动作的事件 记到当前动作上（通过名字匹配）。
        expected_keys 不为空时，会先判断当前动作是否在目标关键字中，再更新。
        """

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
        """
        针对时间类动作（“xxx时间”、“time”），根据剩余秒数更新 remaining
        """
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

    # ------------------------------------------------------------------
    # audio 事件管理

    def update_audio_log_files(self, files):
        unique: list[str] = []
        seen: set[str] = set()
        for path in files or []:
            if path is None:
                continue
            normalized = str(path)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(normalized)
        with self.state_lock:
            self.audio_log_files = unique

    def initialize_audio_monitor_state(self, offsets=None, cache=None):
        normalized_offsets: dict[str, int] = {}
        if offsets:
            for path, position in offsets.items():
                try:
                    normalized_offsets[str(path)] = max(0, int(position))
                except (TypeError, ValueError):
                    continue
        normalized_cache: dict[str, int] = {}
        if cache:
            for key, value in cache.items():
                normalized_key = self.normalize_action(key)
                try:
                    normalized_cache[normalized_key] = max(0, int(value))
                except (TypeError, ValueError):
                    continue
        with self.state_lock:
            self.audio_log_offsets = normalized_offsets
            self.audio_event_cache = normalized_cache

    def get_audio_log_files(self) -> list[str]:
        with self.state_lock:

            return list(self.audio_log_files)


    def get_audio_log_offset(self, path: str) -> int | None:
        with self.state_lock:
            return self.audio_log_offsets.get(path)

    def update_audio_log_offset(self, path: str, position: int) -> None:
        with self.state_lock:
            self.audio_log_offsets[path] = max(0, int(position))

    def get_audio_event_count(self, action_key: str) -> int:
        normalized = self.normalize_action(action_key)
        with self.state_lock:
            return self.audio_event_cache.get(normalized, 0)

    def increment_audio_event_count(self, action_key: str) -> int:
        normalized = self.normalize_action(action_key)
        with self.state_lock:
            new_value = self.audio_event_cache.get(normalized, 0) + 1
            self.audio_event_cache[normalized] = new_value
            return new_value

    def snapshot_audio_monitor_state(self) -> dict[str, object]:
        with self.state_lock:
            files = list(self.audio_log_files)
            offsets = {path: int(position) for path, position in self.audio_log_offsets.items()}
            cache = dict(self.audio_event_cache)
        return {"files": files, "offsets": offsets, "cache": cache}

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


    # ------------------------------------------------------------------
    # 加密/解密 本地的缓存文件，防止被恶意篡改
    def encrypt_data(self, data):
        fernet = Fernet(self._encryption_key)
        return fernet.encrypt(data.encode())

    def decrypt_data(self, encrypted_data):
        fernet = Fernet(self._encryption_key)
        return fernet.decrypt(encrypted_data).decode()

    def load_session_state(self):
        """ 读取当前用例的执行数据 """
        data, _ = self.session_store.load(self.case_id)
        if not data:
            return [], None, False, None

        normalized_actions = []
        for action in data.get("actions", []):
            normalized = self._normalize_stored_action(action)
            if normalized:
                normalized_actions.append(normalized)
        completed = bool(data.get("completed"))
        audio_state = data.get("audio_state")
        if not isinstance(audio_state, dict):
            audio_state = None
        if completed and not normalized_actions:
            return [], None, True, audio_state
        return normalized_actions, data.get("start_time"), completed, audio_state

    def _log_previous_crash_if_needed(self) -> None:
        """ 异常崩溃处理，防御性代码，如果发现异常崩溃之后的补救 """
        report = self.session_store.read_crash_report()
        if not report:
            return
        case_id = report.get("case_id")
        timestamp = report.get("timestamp")
        message = report.get("message", "未知错误")
        self.logger.warning(
            "检测到上一轮监控异常终止 (case_id=%s, time=%s): %s",
            case_id,
            timestamp,
            message,
        )
        self.log("检测到上一轮监控异常退出，将尝试从临时文件恢复。")
        traceback_text = report.get("traceback")
        if traceback_text:
            self.logger.debug("上一轮监控堆栈:\n%s", traceback_text)
        payload = report.get("payload") or {}
        pending_actions = payload.get("actions") or []
        if pending_actions:
            self.logger.warning("崩溃前仍有 %d 个动作未完成。", len(pending_actions))

    def request_session_reset(self):
        """ 是否重置当前会话 """

        self.session_reset_requested = True
        self.session_store.discard()

    def _snapshot_session_payload(self) -> dict[str, object]:
        """ 会话状态快照 & 持久化 """
        with self.state_lock:
            actions_snapshot = [dict(action) for action in self.remaining_actions]
            start_time = self.case_start_time
            case_id = self.case_id
        session_completed = not actions_snapshot
        payload: dict[str, object] = {
            "case_id": case_id,
            "actions": actions_snapshot,
            "start_time": start_time,
            "completed": session_completed,
        }
        audio_state = self.snapshot_audio_monitor_state()
        if any(audio_state.values()):
            payload["audio_state"] = audio_state
        return payload

    def save_session_state(self, force: bool = False):
        """ 保存会话记录 """
        if self.session_reset_requested:
            return
        # 记录请求快照
        payload = self._snapshot_session_payload()
        now = time.monotonic()
        with self._state_persist_lock:
            if not force:
                self._pending_state_payload = payload
                recent_write = now - self._last_state_persist < self._min_state_save_interval
                if recent_write and self._last_persisted_payload is not None:
                    return
                payload_to_write = self._pending_state_payload
            else:
                payload_to_write = payload
                self._pending_state_payload = None

            if (
                not force
                and self._last_persisted_payload is not None
                and payload_to_write == self._last_persisted_payload
            ):
                return

            logger.debug("开始保存临时文件")
            logger.debug(payload_to_write.get("actions"))
            self.session_store.save(payload_to_write)
            self._last_persisted_payload = payload_to_write
            self._last_state_persist = now

    @classmethod
    def remove_temp_file(cls):
        SessionStateStore(
            cls.TEMP_FILE, cls.CACHE_FILE, SETTINGS.monitoring_encryption_key
        ).discard()

    def normalize_action(self, action):
        """ 规范化动作格式 """
        return action.lower().replace(" ", "")

    def run_main(self, case_id, action_and_num, start_time):
        """ 根据用例关键字统一调用监控， action_and_num示例: [("S3", 5), ("USB插拔", 10), ("时间", 30)] """
        # 记录用例ID
        self.case_id = case_id
        run_completed = False
        try:
            # 查看上次是否有崩溃记录
            self._log_previous_crash_if_needed()
            # 读取上一次会话记录
            (
                stored_actions,
                stored_start_time,
                session_completed,
                stored_audio_state,
            ) = self.load_session_state()
            # 如果有未完成的 audio 动作，恢复上一次会话状态
            if stored_actions and stored_audio_state:
                self.update_audio_log_files(stored_audio_state.get("files"))
                self.initialize_audio_monitor_state(
                    offsets=stored_audio_state.get("offsets"),
                    cache=stored_audio_state.get("cache"),
                )
            else:
                # 没有则初始化 audio 状态
                self.initialize_audio_monitor_state()
                current_files = self.get_audio_log_files()
                # 边缘情况：如果当前没有 audio 文件，但 audio_state 里有记录，补上。
                if (
                    not current_files
                    and stored_audio_state
                    and stored_audio_state.get("files")
                ):
                    self.update_audio_log_files(stored_audio_state.get("files"))
            # 如果有记录，使用上一次剩余的动作和开始时间
            if stored_actions:
                self.remaining_actions = stored_actions
                case_start_time = stored_start_time or start_time
            # 没有则重新构建动作状态，
            else:
                self.remaining_actions = [
                    self._build_action_state(action, amount)
                    for action, amount in action_and_num
                ]
                case_start_time = start_time
            # 规范化用例开始时间，转成 ISO 字符串
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
                # 快照备份当前用例监控的动作
                actions_snapshot = [dict(action) for action in self.remaining_actions]
            for action_state in actions_snapshot:
                # 分解当前用例所需执行的动作和次数，并提示用户
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
                    # 按照列表顺序依次执行监控动作
                    if not self.remaining_actions:
                        break
                    current_action = dict(self.remaining_actions[0])
                action = current_action["name"]
                unit = current_action.get("unit", "count")
                target_value = current_action.get("target", 0)
                remaining_value = current_action.get("remaining", target_value)
                try:
                    target_value_float = float(target_value)
                except (TypeError, ValueError):
                    target_value_float = 0.0
                try:
                    remaining_value_float = float(remaining_value)
                except (TypeError, ValueError):
                    remaining_value_float = target_value_float

                if self.is_running:
                    # 监控执行准备
                    display_action = action
                    normalized_action = self.normalize_action(action)
                    self.save_session_state()
                    self.action_complete.clear()
                    # 根据关键字调起线程调对应的监控方法
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
                        self.log(f"开始执行监控: {action}，目标测试次数: {target_value:g}")
                        threading.Thread(
                            target=power_plug_monitor.run,
                            args=(self, target_value),
                            kwargs={"remaining_cycles": remaining_value_float},
                        ).start()

                    elif normalized_action.lower() == "usb插拔":
                        self.log(f"开始执行监控: {action}，目标测试次数: {target_value:g}")
                        thread = threading.Thread(
                            target=usb_monitor.run,
                            args=(self, target_value),
                            kwargs={"remaining_cycles": remaining_value_float},
                        )
                        thread.start()
                        self.register_message_loop_thread(thread.ident)
                    elif normalized_action == "键盘按键":
                        self.log(f"开始执行监控: {action}，目标测试次数: {target_value:g}")
                        threading.Thread(
                            target=keyboard_any_monitor.run,
                            args=(self, target_value),
                            kwargs={"remaining_cycles": remaining_value_float},
                        ).start()
                    elif normalized_action == "锁屏":
                        self.log(f"开始执行监控: {action}，目标测试次数: {target_value:g}")
                        thread = threading.Thread(
                            target=lock_screen_monitor.run,
                            args=(self, target_value),
                            kwargs={"remaining_cycles": remaining_value_float},
                        )
                        thread.start()
                        self.register_message_loop_thread(thread.ident)
                    elif normalized_action == "鼠标点击":
                        self.log(f"开始执行监控: {action}，目标测试次数: {target_value:g}")
                        threading.Thread(
                            target=mouse_monitor.run,
                            args=(self, target_value),
                            kwargs={"remaining_cycles": remaining_value_float},
                        ).start()
                    elif normalized_action == "s3":
                        self.log(f"开始执行监控: {action}，目标测试次数: {target_value:g}")
                        threading.Thread(
                            target=s3_sleep_monitor.run,
                            args=(self, self.case_start_time, target_value),
                        ).start()
                    elif normalized_action == "s4":
                        self.log(f"开始执行监控: {action}，目标测试次数: {target_value:g}")
                        threading.Thread(
                            target=s4_sleep_monitor.run,
                            args=(self, self.case_start_time, target_value),
                        ).start()

                    elif normalized_action == "s4记时":
                        self.log(
                            f"开始执行监控: {action}，目标测试次数: {target_value:g}"
                        )
                        threading.Thread(
                            target=s4_time_monitor.run,
                            args=(self, self.case_start_time, target_value),
                        ).start()

                    elif normalized_action == "s3记时":
                        self.log(
                            f"开始执行监控: {action}，目标测试次数: {target_value:g}"
                        )
                        threading.Thread(
                            target=s3_time_monitor.run,
                            args=(self, self.case_start_time, target_value),
                        ).start()

                    elif normalized_action == "mikelog":
                        self.log(f"开始执行监控: {display_action} 对MikeII的Log进行解析判断")
                        threading.Thread(
                            target=Tools_Log_monitor.run,
                            args=(self,target_value,display_action),
                        ).start()

                    elif normalized_action == "TransitionCapLog".lower():
                        self.log(f"开始执行监控: {display_action} 对TransitionCapLog的Log进行解析判断")
                        threading.Thread(
                            target=Tools_Log_monitor.run,
                            args=(self, target_value, display_action),
                        ).start()

                    elif normalized_action == "s5":
                        self.log(f"开始执行监控: {action}，目标测试次数: {target_value:g}")
                        threading.Thread(
                            target=s5_sleep_monitor.run,
                            args=(self, self.case_start_time, target_value),
                        ).start()
                    elif normalized_action == "restart":
                        self.log(f"开始执行监控: {action}，目标测试次数: {target_value:g}")
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
                            kwargs={"remaining_cycles": remaining_value_float},
                        ).start()
                    elif normalized_action == "s3插拔":
                        self.log(f"开始执行监控: {action}，目标测试次数: {target_value:g}")
                        threading.Thread(
                            target=s3_usb_cycle_monitor.run,
                            args=(
                                self,
                                self.case_start_time,
                                target_value,
                                target_value,
                            ),
                            kwargs={"remaining_cycles": remaining_value_float},
                        ).start()
                    elif normalized_action == "s3电源插拔":
                        self.log(f"开始执行监控: {action}，目标测试次数: {target_value:g}")
                        threading.Thread(
                            target=s3_power_cycle_monitor.run,
                            args=(self, self.case_start_time, target_value),
                            kwargs={
                                "remaining_cycles": remaining_value_float,
                                "s3_progress": current_action.get("s3_progress"),
                                "power_progress": current_action.get("power_progress"),
                            },
                        ).start()
                    elif normalized_action == "显示器":
                        self.log(f"开始执行监控: {action} 开关事件，目标测试次数: {target_value:g}")
                        threading.Thread(
                            target=display_monitor.run,
                            args=(self, target_value),
                            kwargs={"remaining_cycles": remaining_value_float},
                        ).start()
                    elif normalized_action == "音量":
                        self.log(f"开始执行监控: {action} 加减事件，目标测试次数: {target_value:g}")
                        threading.Thread(
                            target=volume_monitor.run,
                            args=(self, target_value),
                            kwargs={"remaining_change_count": remaining_value_float},
                        ).start()
                    elif normalized_action in {"摄像头", "camera"}:
                        self.log(f"开始执行监控: {action} 开关事件，目标测试次数: {target_value:g}")
                        threading.Thread(
                            target=camera_monitor.run,
                            args=(self, target_value),
                            kwargs={"remaining_cycles": remaining_value_float},
                        ).start()
                    elif normalized_action in AUDIO_EVENT_KEYWORDS:
                        self.log(f"开始执行监控音频事件: {display_action}，目标测试次数: {int(target_value)}")
                        threading.Thread(
                            target=audio_event_monitor.run,
                            args=(self, normalized_action, target_value, display_action),
                        ).start()
                    else:
                        self.log(f"未匹配到任何监控事项，请检查 {action} 填写是否正确")
                        self.action_complete.set()
                    # 等待线程完成
                    self.action_complete.wait()
                    # 校验 snapshot，对比下 remaining_after，检查动作是否完成
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
                    # 打印结果
                    if remaining_after <= 0:
                        self.log(f"动作 {action} 完成")
                    else:
                        if unit_after == "seconds":
                            self.log(f"动作 {action} 未完成，剩余测试时间: {remaining_after / 60:g} min ({remaining_after:g} 秒)")
                        else:
                            self.log(f"动作 {action} 未完成，剩余测试次数: {remaining_after:g}")
                    # 移除完成的动作
                    completed = self._complete_current_action()
                    if not completed:
                        self.log(f"动作 {action} 已暂停，本次监控将保留剩余进度以便下次继续。")
                        break
                else:
                    self.logger.warning("事项block，退出执行")
                    self.save_session_state()
                    break

            # 全部完成后，保留备份的临时文件
            with self.state_lock:
                has_remaining = bool(self.remaining_actions)
            if self.session_reset_requested:
                self.logger.warning("收到会话重置请求，开始删除临时文件")
                self.remove_temp_file()
            elif has_remaining:
                self.logger.warning("检测到未完成的动作，保留临时文件以便下次继续执行")
            else:
                self.logger.warning("所有动作执行完毕，本次将保留临时文件，确保重启后仍可读取上次执行记录。")
            self.logger.warning("所有动作执行完毕，解禁按钮")
            self.save_session_state(force=True)
            time.sleep(1) # 究极防御崩溃代码
            # 通知UI完成监控，解禁按钮
            self.call_after(self.window.after_test)
            run_completed = True
        except Exception as exc:  # pragma: no cover - 防御性捕获
            self.logger.exception("监控执行出现未知错误")
            payload = self._snapshot_session_payload()
            self.session_store.record_crash(self.case_id, payload, exc)
            self.log("监控执行出现未知错误，已保存当前进度并生成崩溃报告。")
            self.save_session_state(force=True)
        finally:
            if run_completed:
                self.session_store.clear_crash_report()

    def on_close(self, event):
        # 用户直接关闭窗口时记录当前会话信息
        self.save_session_state(force=True)
        self.window.Destroy()
        wx.GetApp().ExitMainLoop()
