
from mss import mss
from mss.tools import to_png
import os
import time
import threading
import win32api
import win32con
import psutil
import winreg
from pathlib import Path
from services.api_client import ApiClient, encode_attachment
from PyQt5 import QtCore, QtGui, QtWidgets
class AutoFunc:
    def __init__(self):
        super().__init__()
    def high_perf_screenshot(self):
        """高频自动截屏"""
        # 创建保存目录
        interval = 1
        count = 1
        save_dir=os.path.dirname(os.path.abspath(__file__))
        print(save_dir)
        # os.makedirs(save_dir, exist_ok=True)

        with mss() as sct:
            # 截取主显示器全屏（可通过sct.monitors获取所有显示器，0为虚拟全屏，1+为实际显示器）
            monitor = sct.monitors[1]  # 1表示第一个显示器

            for i in range(count):
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                save_path = f"{save_dir}\screenshot_{timestamp}.png"

                # 截屏（返回原始像素数据）
                sct_img = sct.grab(monitor)
                # 保存为PNG
                to_png(sct_img.rgb, sct_img.size, output=save_path)

                print(f"第{i + 1}次高频截屏保存至：{save_path}")
                time.sleep(interval)

        self._attachments.append(save_path)
        self._attachment_list.addItem(os.path.basename(save_path))





