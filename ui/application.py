"""Application bootstrap for the redesigned TTS client."""
from __future__ import annotations

import logging
import sys

from PyQt5 import QtCore, QtWidgets

from config.settings import SETTINGS
from monitoring.manager import MonitoringManager
from services.api_client import ApiClient
from services.auth import AuthStore, RememberedCredentials
from services.ota import OTAUpdater
from .login_dialog import LoginDialog
from .main_window import MainWindow
from .state import WindowStateStore
from utils.exceptions import AuthenticationError, ClientError, NetworkError
from utils.logging import configure_logging

logger = logging.getLogger(__name__)


def _acquire_instance_lock() -> QtCore.QLockFile | None:
    """Ensure only one client instance runs at a time."""

    lock = QtCore.QLockFile(str(SETTINGS.app_lock_file))
    lock.setStaleLockTime(0)
    if lock.tryLock():
        return lock

    if lock.error() == QtCore.QLockFile.LockFailedError and lock.removeStaleLock():
        if lock.tryLock():
            return lock

    if lock.error() == QtCore.QLockFile.LockFailedError:
        message = "已检测到另一个客户端实例正在运行，请先关闭后再尝试。"
    else:
        message = f"无法创建实例锁({lock.errorString()})，请检查权限或清理锁文件。"
    QtWidgets.QMessageBox.critical(None, "客户端已在运行", message)
    return None


def main() -> int:
    """Run the Qt event loop."""

    log_dir = configure_logging()
    logger.info("应用启动，日志目录: %s", log_dir)

    app = QtWidgets.QApplication(sys.argv)
    instance_lock = _acquire_instance_lock()
    if instance_lock is None:
        return 0
    app.setProperty("instance_lock", instance_lock)

    try:
        api_client = ApiClient()
        auth_store = AuthStore()
        window_state = WindowStateStore()
        monitoring = MonitoringManager()
        updater = OTAUpdater()

        login_dialog = LoginDialog()
        remembered = auth_store.load()
        if remembered:
            login_dialog.set_initial_values(remembered.username, remembered.password, True)

        user_info: dict[str, object] = {}

        def handle_login(username: str, password: str, remember: bool) -> None:
            nonlocal user_info
            try:
                data = api_client.authenticate(username, password)
            except AuthenticationError as exc:
                login_dialog.set_error(str(exc))
                logger.warning("用户 %s 登录失败（认证）: %s", username, exc)
                return
            except (ClientError, NetworkError) as exc:
                login_dialog.set_error(str(exc))
                logger.error("用户 %s 登录失败（网络/客户端）: %s", username, exc)
                return
            user_info = data.get("user", {}) if isinstance(data, dict) else {}
            if remember:
                auth_store.save(RememberedCredentials(username=username, password=password))
            else:
                auth_store.clear()
            logger.info("用户 %s 登录成功", username)
            login_dialog.accept()

        login_dialog.login_requested.connect(handle_login)
        if login_dialog.exec_() != QtWidgets.QDialog.Accepted:
            return 0

        window = MainWindow(api_client, monitoring, window_state, user_info)
        window.show()

        # OTA 自动更新检查示例（以后需要时可按照下列步骤恢复逻辑）：
        # 1. 调用 updater.check() 获取 update_info。
        # 2. 捕获 NetworkError，将失败原因写入日志但不中断 UI。
        # 3. 若获取到新版本，则弹窗提示用户访问下载链接。

        return app.exec_()
    finally:
        if instance_lock.isLocked():
            instance_lock.unlock()


if __name__ == "__main__":
    sys.exit(main())
