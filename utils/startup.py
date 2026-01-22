"""Windows 开机自启动注册辅助模块。"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - 非 Windows 平台
    winreg = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _absolute_path(path: str) -> str:
    """返回绝对路径。"""
    return os.path.abspath(path)


def _startup_command() -> str:
    """构造写入注册表的启动命令（带引号）。"""
    if getattr(sys, "frozen", False):
        exe_path = _absolute_path(sys.executable)
        return f"\"{exe_path}\""
    script = sys.argv[0] if sys.argv else sys.executable
    script_path = _absolute_path(script)
    python_path = _absolute_path(sys.executable)
    if Path(script_path).suffix.lower() in {".py", ".pyw"}:
        return f"\"{python_path}\" \"{script_path}\""
    return f"\"{script_path}\""


def _normalize_command(command: str) -> str:
    """归一化命令用于比较：去多余空白并忽略大小写。"""
    return " ".join(str(command).strip().split()).casefold()


def is_in_startup(app_name: str) -> bool:
    """检测是否已注册到 HKCU\\Run。"""
    if winreg is None:
        logger.info("当前非 Windows 平台，无法检测自启动。")
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as reg_key:
            value, _ = winreg.QueryValueEx(reg_key, app_name)
            logger.info("已读取自启动项: %s -> %s", app_name, value)
    except FileNotFoundError:
        logger.info("未找到自启动项: %s", app_name)
        return False
    except OSError as exc:
        logger.warning("读取自启动项失败: %s (%s)", app_name, exc)
        return False
    expected = _normalize_command(_startup_command())
    actual = _normalize_command(value)
    if actual == expected:
        logger.info("自启动项已存在且路径一致: %s", app_name)
        return True
    logger.info("自启动项已存在但路径不同: %s", app_name)
    logger.info("期望: %s", _startup_command())
    logger.info("当前: %s", value)
    return False


def add_to_startup(app_name: str) -> bool:
    """写入 HKCU\\Run，注册为开机自启动。"""
    if winreg is None:
        logger.info("非 Windows 平台，跳过自启动注册。")
        return False
    command = _startup_command()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as reg_key:
            winreg.SetValueEx(reg_key, app_name, 0, winreg.REG_SZ, command)
        logger.info("已写入自启动项: %s", app_name)
        logger.info("注册表路径: HKCU\\%s", _RUN_KEY)
        logger.info("命令: %s", command)
        return True
    except OSError as exc:
        logger.error("写入自启动项失败: %s (%s)", app_name, exc)
        return False


def ensure_startup(app_name: str) -> None:
    """确保开机自启动已注册，已存在则跳过。"""
    logger.info("检查开机自启动: %s", app_name)
    if is_in_startup(app_name):
        logger.info("开机自启动已就绪，跳过写入: %s", app_name)
        return
    if add_to_startup(app_name):
        logger.info("开机自启动注册完成: %s", app_name)
