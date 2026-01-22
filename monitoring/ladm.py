"""LADM 关键字的环境检查。"""
from __future__ import annotations

import logging

import psutil
import win32service

logger = logging.getLogger(__name__)

LADM_SERVICE_NAME = "LenovoAccessoriesandDisplayManagerService"
LADM_PROCESS_NAME = "LenovoAccessoriesandDisplayManager.exe"


def is_ladm_service_running() -> bool:
    """检查 LADM 服务是否处于运行状态。"""
    try:
        manager = win32service.OpenSCManager(
            None, None, win32service.SC_MANAGER_CONNECT
        )
        try:
            service = win32service.OpenService(
                manager,
                LADM_SERVICE_NAME,
                win32service.SERVICE_QUERY_STATUS,
            )
            try:
                status = win32service.QueryServiceStatus(service)
                return status[1] == win32service.SERVICE_RUNNING
            finally:
                win32service.CloseServiceHandle(service)
        finally:
            win32service.CloseServiceHandle(manager)
    except Exception as exc:
        logger.warning("读取 LADM 服务状态失败: %s", exc)
        return False


def is_ladm_process_running() -> bool:
    """检查 LADM 进程是否存在。"""
    target = LADM_PROCESS_NAME.lower()
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info.get("name")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        if name and name.lower() == target:
            return True
    return False


def check_ladm_ready() -> tuple[bool, str]:
    """返回 LADM 是否就绪以及失败原因。"""
    service_running = is_ladm_service_running()
    process_running = is_ladm_process_running()
    if service_running and process_running:
        return True, ""
    missing: list[str] = []
    if not service_running:
        missing.append(f"服务 {LADM_SERVICE_NAME} 未运行")
    if not process_running:
        missing.append(f"进程 {LADM_PROCESS_NAME} 未运行")
    message = "；".join(missing) if missing else "LADM 未就绪"
    return False, message
