"""联想小天安装/运行监控。"""
from __future__ import annotations

import psutil
from typing import TYPE_CHECKING
import winreg  # 注意这里直接使用winreg，无需win32reg

from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

if TYPE_CHECKING:  # pragma: no cover
    from ..patvs_monitor import Patvs_Fuction
def get_running_processes(context,software_name='xiaotian.exe'):

    for proc in psutil.process_iter(['pid', 'name', 'exe', 'status']):
        try:

            if software_name in proc.info['name']:
                context.log(f"检测到联想小天进程正在运行，PID: {proc.info['pid']}, 路径: {proc.info['exe']}")
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False
def get_installed_software_pywin32(context,software_name='xiaotian.exe'):
    flags_=False
    software_list = []
    # 注册表路径（32位和64位软件，以及当前用户软件）
    paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    ]
    hives = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]  # 本地机器和当前用户

    for hive in hives:
        for path in paths:
            try:
                # 打开注册表项（需指定访问权限，兼容64位系统）
                key = winreg.OpenKey(
                    hive,
                    path,
                    0,
                    winreg.KEY_READ | winreg.KEY_WOW64_64KEY  # 允许读取64位注册表
                )
                index = 0
                while not flags_:
                    try:
                        # 枚举子项（每个子项对应一个软件）
                        subkey_name = winreg.EnumKey(key, index)
                        subkey = winreg.OpenKey(key, subkey_name)

                        # 获取软件名称（DisplayName是必填项，无名称则跳过）
                        try:
                            name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        except FileNotFoundError:
                            index += 1
                            continue

                        # 获取版本号（可选，不存在则为None）
                        try:
                            version = winreg.QueryValueEx(subkey, "DisplayVersion")[0]
                        except FileNotFoundError:
                            version = None

                        if software_name in name:
                            context.log(f"检测到已安装联想小天软件，版本: {version}")
                            flags_=True
                            return flags_

                        # software_list.append({"name": name, "version": version})
                        index += 1
                        winreg.CloseKey(subkey)  # 关闭子项
                    except OSError:
                        break  # 子项枚举完毕
                winreg.CloseKey(key)  # 关闭主项
            except FileNotFoundError:
                continue  # 路径不存在，跳过
            except PermissionError:
                print(f"无权限访问注册表路径：{path}")
                continue
    return flags_
    # return software_list


def run(
    context: "Patvs_Fuction",
    target_change_count: float,
    remaining_change_count: float | None = None,
) -> None:

    try:
        total_target = float(target_change_count)
    except (TypeError, ValueError):
        total_target = 0.0
    context.log(f"检测安装联想小天软件安装状况")
    # app_infos_=get_installed_software_pywin32(context)
    if get_installed_software_pywin32(context):
        if not get_running_processes(context):
            context.log("联想小天软件未运行，等待运行中...")
    else:
        context.log("未检测到联想小天软件的安装。")

    context.log("退出联想小天软件事件监控。")

