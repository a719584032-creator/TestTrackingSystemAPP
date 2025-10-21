# -*- coding: utf-8 -*-
"""
Auto-generated constants for PATVS event log monitoring.
Each event code maps to a spec with keywords and a human-readable description.
"""
from typing import Dict, List, Optional, TypedDict

DEFAULT_LOG_DIR: str = r"C:\\PATVS\\logs"
DEFAULT_FILE_PATTERNS: List[str] = ['*.log', '*.txt']

class EventSpec(TypedDict):
    keywords: List[str]
    description: str

EVENT_SPECS: Dict[str, EventSpec] = {
    "HEADSET_POWER_ON": {'keywords': ["LENOVO_HEADSET_POWER_ON"], 'description': "耳机拨动开机"},
    "HEADSET_BATTERY_ANNOUNCE": {'keywords': ["LENOVO_HEADSET_BATTERY_ANNOUNCE"], 'description': "耳机拨动提示电量"},
    "HEADSET_BT_PAIRING": {'keywords': ["LENOVO_HEADSET_BT_PAIRING"], 'description': "拨动2S蓝牙进入配对"},
    "USB_PID_VID": {'keywords': ["LENOVO_USB_PID_VID"], 'description': "PID&VID"},
    "CONNECT_FAIL": {'keywords': ["LENOVO_CONNECT_FAIL"], 'description': "连接失败+原因"},
    "CONNECT_DONGLE": {'keywords': ["LENOVO_CONNECT_DONGLE"], 'description': "连接一台陪测设备（插入Dongle）"},
    "CONNECT_BT": {'keywords': ["LENOVO_CONNECT_BT"], 'description': "连接一台陪测设备（连接蓝牙）"},
    "CONNECT_TWO_DEVICES": {'keywords': ["LENOVO_CONNECT_TWO_DEVICES"], 'description': "连接两台陪测设备"},
    "DISCONNECT_DONGLE": {'keywords': ["LENOVO_DISCONNECT_DONGLE"], 'description': "断开连接陪测设备（Dongle）"},
    "DISCONNECT_BT": {'keywords': ["LENOVO_DISCONNECT_BT"], 'description': "断开连接陪测设备（蓝牙）"},
    "DISCONNECT_ABNORMAL": {'keywords': ["LENOVO_DISCONNECT_ABNORMAL"], 'description': "异常断开+原因"},
    "DEFAULT_VOLUME_DONGLE": {'keywords': ["LENOVO_DEFAULT_VOLUME_DONGLE"], 'description': "默认音量（Dongle模式）"},
    "DEFAULT_VOLUME_BT": {'keywords': ["LENOVO_DEFAULT_VOLUME_BT"], 'description': "默认音量（BT模式）"},
    "CALL_ACCEPT_BT_DEVICE": {'keywords': ["LENOVO_CALL_ACCEPT_BT_DEVICE"], 'description': "陪测设备端接听（BT模式）"},
    "CALL_ACCEPT_DONGLE_DEVICE": {'keywords': ["LENOVO_CALL_ACCEPT_DONGLE_DEVICE"], 'description': "陪测设备端接听（Dongle模式）"},
    "CALL_ACCEPT_BT_HEADSET": {'keywords': ["LENOVO_CALL_ACCEPT_BT_HEADSET"], 'description': "耳机按键通话接听（BT模式）"},
    "CALL_ACCEPT_DONGLE_HEADSET": {'keywords': ["LENOVO_CALL_ACCEPT_DONGLE_HEADSET"], 'description': "耳机按键通话接听（Dongle模式）"},
    "CALL_OUT_BT_DEVICE": {'keywords': ["LENOVO_CALL_OUT_BT_DEVICE"], 'description': "陪测设备通话去电（BT模式）"},
    "CALL_OUT_DONGLE_DEVICE": {'keywords': ["LENOVO_CALL_OUT_DONGLE_DEVICE"], 'description': "陪测设备通话去电（Dongle模式）"},
    "CALL_HANGUP_DONGLE_DEVICE": {'keywords': ["LENOVO_CALL_HANGUP_DONGLE_DEVICE"], 'description': "陪测设备端挂断（Dongle模式）"},
    "CALL_HANGUP_BT_DEVICE": {'keywords': ["LENOVO_CALL_HANGUP_BT_DEVICE"], 'description': "陪测设备端挂断（BT模式）"},
    "CALL_HANGUP_DONGLE_HEADSET": {'keywords': ["LENOVO_CALL_HANGUP_DONGLE_HEADSET"], 'description': "按键通话挂断（Dongle模式）"},
    "CALL_HANGUP_BT_HEADSET": {'keywords': ["LENOVO_CALL_HANGUP_BT_HEADSET"], 'description': "按键通话挂断（BT模式）"},
    "CALL_REJECT_BT_DEVICE": {'keywords': ["LENOVO_CALL_REJECT_BT_DEVICE"], 'description': "陪测设备端拒绝（BT模式）"},
    "CALL_REJECT_DONGLE_DEVICE": {'keywords': ["LENOVO_CALL_REJECT_DONGLE_DEVICE"], 'description': "陪测设备端拒绝（Dongle模式）"},
    "CALL_REJECT_BT_HEADSET": {'keywords': ["LENOVO_CALL_REJECT_BT_HEADSET"], 'description': "耳机按键通话拒接（BT模式）"},
    "CALL_REJECT_DONGLE_HEADSET": {'keywords': ["LENOVO_CALL_REJECT_DONGLE_HEADSET"], 'description': "耳机按键通话拒接（Dongle模式）"},
    "CALL_ACCEPT_MICUP_BT": {'keywords': ["LENOVO_CALL_ACCEPT_MICUP_BT"], 'description': "麦秆接听来电（BT模式）"},
    "CALL_ACCEPT_MICUP_DONGLE": {'keywords': ["LENOVO_CALL_ACCEPT_MICUP_DONGLE"], 'description': "麦秆接听来电（Dongle模式）"},
    "MIC_MUTE_UP_BT": {'keywords': ["LENOVO_MIC_MUTE_UP_BT"], 'description': "麦秆向上mute（BT模式）"},
    "MIC_MUTE_UP_DONGLE": {'keywords': ["LENOVO_MIC_MUTE_UP_DONGLE"], 'description': "麦秆向上mute（Dongle模式）"},
    "MIC_UNMUTE_DOWN_BT": {'keywords': ["LENOVO_MIC_UNMUTE_DOWN_BT"], 'description': "麦秆向下unmute（BT模式）"},
    "MIC_UNMUTE_DOWN_DONGLE": {'keywords': ["LENOVO_MIC_UNMUTE_DOWN_DONGLE"], 'description': "麦秆向下unmute（Dongle模式）"},
    "MUTE_BT_BUTTON": {'keywords': ["LENOVO_MUTE_BT_BUTTON"], 'description': "按键Mute（BT模式）"},
    "MUTE_DONGLE_BUTTON": {'keywords': ["LENOVO_MUTE_DONGLE_BUTTON"], 'description': "按键Mute（Dongle模式）"},
    "UNMUTE_BT_BUTTON": {'keywords': ["LENOVO_UNMUTE_BT_BUTTON"], 'description': "按键unMute（BT模式）"},
    "UNMUTE_DONGLE_BUTTON": {'keywords': ["LENOVO_UNMUTE_DONGLE_BUTTON"], 'description': "按键unMute（Dongle模式）"},
    "HEADSET_SLIDE_20S": {'keywords': ["LENOVO_HEADSET_SLIDE_20S"], 'description': "耳机向上拨动20S"},
    "VOLUME_UP_BT": {'keywords': ["LENOVO_VOLUME_UP_BT"], 'description': "音量键+（BT模式）"},
    "VOLUME_UP_DONGLE": {'keywords': ["LENOVO_VOLUME_UP_DONGLE"], 'description': "音量键+（Dongle模式）"},
    "VOLUME_DOWN_BT": {'keywords': ["LENOVO_VOLUME_DOWN_BT"], 'description': "音量键-（BT模式）"},
    "VOLUME_DOWN_DONGLE": {'keywords': ["LENOVO_VOLUME_DOWN_DONGLE"], 'description': "音量键-（Dongle模式）"},
    "VOLUME_MAX_BT": {'keywords': ["LENOVO_VOLUME_MAX_BT"], 'description': "最大音量（BT模式）"},
    "VOLUME_MAX_DONGLE": {'keywords': ["LENOVO_VOLUME_MAX_DONGLE"], 'description': "最大音量（Dongle模式）"},
    "VOLUME_MIN_BT": {'keywords': ["LENOVO_VOLUME_MIN_BT"], 'description': "最小音量（BT模式）"},
    "VOLUME_MIN_DONGLE": {'keywords': ["LENOVO_VOLUME_MIN_DONGLE"], 'description': "最小音量（Dongle模式）"},
    "IDLE_MODE_ENTER": {'keywords': ["LENOVO_IDLE_MODE_ENTER"], 'description': "进入 IDLE mode"},
    "IDLE_MODE_EXIT": {'keywords': ["LENOVO_IDLE_MODE_EXIT"], 'description': "退出 IDLE mode"},
    "PLAY_MUSIC_BT": {'keywords': ["LENOVO_PLAY_MUSIC_BT"], 'description': "耳机单击播放音乐（BT模式）"},
    "PLAY_MUSIC_DONGLE": {'keywords': ["LENOVO_PLAY_MUSIC_DONGLE"], 'description': "耳机单击播放音乐（Dongle模式）"},
    "PAUSE_MUSIC_BT": {'keywords': ["LENOVO_PAUSE_MUSIC_BT"], 'description': "耳机单击暂停音乐（BT模式）"},
    "PAUSE_MUSIC_DONGLE": {'keywords': ["LENOVO_PAUSE_MUSIC_DONGLE"], 'description': "耳机单击暂停音乐（Dongle模式）"},
    "NEXT_TRACK_BT": {'keywords': ["LENOVO_NEXT_TRACK_BT"], 'description': "耳机双击下一首（BT模式）"},
    "NEXT_TRACK_DONGLE": {'keywords': ["LENOVO_NEXT_TRACK_DONGLE"], 'description': "耳机双击下一首（Dongle模式）"},
    "PREV_TRACK_BT": {'keywords': ["LENOVO_PREV_TRACK_BT"], 'description': "耳机三击上一首（BT模式）"},
    "PREV_TRACK_DONGLE": {'keywords': ["LENOVO_PREV_TRACK_DONGLE"], 'description': "耳机三击上一首（Dongle模式）"},
    "DEVICE_PLAY_BT": {'keywords': ["LENOVO_DEVICE_PLAY_BT"], 'description': "陪测设备端单击播放音乐（BT模式）"},
    "DEVICE_PAUSE_DONGLE": {'keywords': ["LENOVO_DEVICE_PAUSE_DONGLE"], 'description': "陪测设备端单击暂停音乐（Dongle模式）"},
    "DEVICE_PAUSE_BT": {'keywords': ["LENOVO_DEVICE_PAUSE_BT"], 'description': "陪测设备端单击暂停音乐（BT模式）"},
    "DEVICE_PLAY_DONGLE": {'keywords': ["LENOVO_DEVICE_PLAY_DONGLE"], 'description': "陪测设备端单击播放音乐（Dongle模式）"},
    "DEVICE_NEXT_BT": {'keywords': ["LENOVO_DEVICE_NEXT_BT"], 'description': "陪测设备端双击下一首（BT模式）"},
    "DEVICE_NEXT_DONGLE": {'keywords': ["LENOVO_DEVICE_NEXT_DONGLE"], 'description': "陪测设备端双击下一首（Dongle模式）"},
    "DEVICE_PREV_BT": {'keywords': ["LENOVO_DEVICE_PREV_BT"], 'description': "陪测设备端三击上一首（BT模式）"},
    "DEVICE_PREV_DONGLE": {'keywords': ["LENOVO_DEVICE_PREV_DONGLE"], 'description': "陪测设备端三击上一首（Dongle模式）"},
    "HEADSET_WAKE_ASSISTANT_BT": {'keywords': ["LENOVO_HEADSET_WAKE_ASSISTANT_BT"], 'description': "耳机按键唤醒语音助手（BT模式）"},
    "HEADSET_WAKE_ASSISTANT_DONGLE": {'keywords': ["LENOVO_HEADSET_WAKE_ASSISTANT_DONGLE"], 'description': "耳机按键唤醒语音助手（Dongle模式）"},
    "DEVICE_WAKE_ASSISTANT": {'keywords': ["LENOVO_DEVICE_WAKE_ASSISTANT"], 'description': "陪测设备端唤醒语音助手"},
    "TEAMS_RAISE_HAND": {'keywords': ["LENOVO_TEAMS_RAISE_HAND"], 'description': "Teams会议中长按Hook键举手"},
    "HEADSET_AUTO_SHUTDOWN": {'keywords': ["LENOVO_HEADSET_AUTO_SHUTDOWN"], 'description': "耳机无业务120min自动关机"},
    "VOLUME_REBOOT": {'keywords': ["LENOVO_VOLUME_REBOOT"], 'description': "音量+-键软重启"},
    "HEADSET_POWER_OFF": {'keywords': ["LENOVO_HEADSET_POWER_OFF"], 'description': "耳机拨动关机"},
    "USB_CHARGE_START": {'keywords': ["LENOVO_USB_CHARGE_START"], 'description': "插入USB开始充电"},
    "USB_CHARGE_STOP": {'keywords': ["LENOVO_USB_CHARGE_STOP"], 'description': "拔掉USB停止充电"},
    "TEAMS_CHECK_START": {'keywords': ["LENOVO_TEAMS_CHECK_START"], 'description': "检测Teams是否启动"},
    "FW_UPGRADE_START": {'keywords': ["LENOVO_FW_UPGRADE_START"], 'description': "固件开始升级"},
    "TEAMS_WAKEUP": {'keywords': ["LENOVO_TEAMS_WAKEUP"], 'description': "单击唤醒Teams至前台"},
    "DEVICE_SPEAKER_SWITCH": {'keywords': ["LENOVO_DEVICE_SPEAKER_SWITCH"], 'description': "陪测设备端扬声器切换回耳机（dongle+bt）"},
    "BATTERY_LEVEL_ANNOUNCE": {'keywords': ["LENOVO_BATTERY_LEVEL_ANNOUNCE"], 'description': "不同电量区间播报"},
    "DONGLE_SCAN_START": {'keywords': ["LENOVO_DONGLE_SCAN_START"], 'description': "Dongle搜索配对耳机（启动扫描）"},
    "ANC_ON": {'keywords': ["LENOVO_ANC_ON"], 'description': "降噪开模式（ANC）"},
    "ANC_OFF": {'keywords': ["LENOVO_ANC_OFF"], 'description': "降噪关模式（ANC）"},
    "GAME_MODE_ON": {'keywords': ["LENOVO_GAME_MODE_ON"], 'description': "游戏模式开"},
    "GAME_MODE_OFF": {'keywords': ["LENOVO_GAME_MODE_OFF"], 'description': "游戏模式关"},
    "EQ_MODE": {'keywords': ["LENOVO_EQ_MODE"], 'description': "不同EQ模式"},
    "FW_UPGRADE_ABORT": {'keywords': ["LENOVO_FW_UPGRADE_ABORT"], 'description': "固件中断升级"},
    "DISCONNECT_DISTANCE_BT": {'keywords': ["LENOVO_DISCONNECT_DISTANCE_BT"], 'description': "拉距断连（BT模式）"},
    "DISCONNECT_DISTANCE_DONGLE": {'keywords': ["LENOVO_DISCONNECT_DISTANCE_DONGLE"], 'description': "拉距断连（Dongle模式）"},
    "RECONNECT_DISTANCE_BT": {'keywords': ["LENOVO_RECONNECT_DISTANCE_BT"], 'description': "拉距后回连（BT模式）"},
    "RECONNECT_DISTANCE_DONGLE": {'keywords': ["LENOVO_RECONNECT_DISTANCE_DONGLE"], 'description': "拉距后回连（Dongle模式）"},
    "SLEEP_MODE_ENTER": {'keywords': ["LENOVO_SLEEP_MODE_ENTER"], 'description': "耳机进入Sleep mode"},
    "AI_BUTTON": {'keywords': ["LENOVO_AI_BUTTON"], 'description': "AI button"},
    "EXIT_SLEEP_BUTTON": {'keywords': ["LENOVO_EXIT_SLEEP_BUTTON"], 'description': "按键退出休眠"},
    "EXIT_SLEEP_MIC": {'keywords': ["LENOVO_EXIT_SLEEP_MIC"], 'description': "麦秆拨动退出休眠"},
}


def _normalize_for_mapping(action: str) -> str:
    return action.lower().replace(" ", "") if isinstance(action, str) else action


AUDIO_EVENT_KEYWORDS: Dict[str, str] = {
    _normalize_for_mapping(key): spec['keywords'][0]
    for key, spec in EVENT_SPECS.items()
    if spec.get('keywords')
}

def normalize_action(s: str) -> str:
    return s.strip() if isinstance(s, str) else s

def is_event_code(action: str) -> bool:
    a = normalize_action(action)
    return a in EVENT_SPECS

def get_event_spec(action: str) -> Optional[EventSpec]:
    a = normalize_action(action)
    return EVENT_SPECS.get(a)

def get_keywords(action: str) -> List[str]:
    spec = get_event_spec(action)
    return spec['keywords'] if spec else []

__all__ = [
    'DEFAULT_LOG_DIR',
    'DEFAULT_FILE_PATTERNS',
    'EventSpec',
    'EVENT_SPECS',
    'AUDIO_EVENT_KEYWORDS',
    'is_event_code',
    'get_event_spec',
    'get_keywords',
]
