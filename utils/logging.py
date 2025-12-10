"""日志工具模块"""
from __future__ import annotations

import datetime as dt
import logging
import sys
import traceback
from pathlib import Path

from config.settings import SETTINGS


def configure_logging() -> Path:
    """配置全局日志记录器并返回当前日志目录路径。"""

    # 日志根目录（从配置中读取）
    log_root = SETTINGS.log_root

    # 按日期创建日志子目录，例如：20250112
    log_dir = log_root / dt.datetime.now().strftime("%Y%m%d")
    log_dir.mkdir(parents=True, exist_ok=True)

    # 主日志文件
    log_file = log_dir / "application.log"

    # 定义日志格式：包含时间、日志等级、日志器名称和消息
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(name)s - %(message)s")

    # 控制台输出处理器
    console = logging.StreamHandler()
    console.setFormatter(formatter)

    # 文件输出处理器
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    # 获取根日志器，并清空已有的处理器（避免重复日志）
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()  # 关闭旧处理器，释放资源

    # 设置日志等级，并注册新的处理器
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console)
    root_logger.addHandler(file_handler)

    # 安装全局未捕获异常钩子，确保异常写入 crash.log
    install_exception_hook(log_dir / "crash.log")

    return log_dir


def install_exception_hook(crash_file: Path) -> None:
    """安装未捕获异常处理钩子，将异常信息写入指定的 crash_file 文件。"""

    def handle_exception(exc_type, exc_value, exc_traceback):  # type: ignore[override]
        # 对 Ctrl+C 中断不进行特殊处理，按默认行为执行
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        # 格式化完整异常堆栈信息
        message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        # 在日志中记录严重级别的错误信息
        logging.critical("应用发生未处理异常:\n%s", message)

        # 确保 crash 文件目录存在
        crash_file.parent.mkdir(parents=True, exist_ok=True)

        # 将异常信息追加写入 crash.log
        with crash_file.open("a", encoding="utf-8") as handle:
            handle.write(f"[{dt.datetime.now().isoformat()}] {message}\n")

    # 将 Python 全局异常钩子替换为自定义实现
    sys.excepthook = handle_exception  # type: ignore[assignment]
