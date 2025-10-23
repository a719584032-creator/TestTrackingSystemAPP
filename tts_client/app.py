"""Application bootstrap for the redesigned TTS client."""
from __future__ import annotations

import logging
import sys

from PyQt5 import QtWidgets

from .core.api_client import ApiClient
from .core.auth import AuthStore, RememberedCredentials
from .core.exceptions import AuthenticationError, ClientError, NetworkError
from .core.logging import configure_logging
from .core.ota import OTAUpdater
from .core.settings import ExecutionStateStore, WindowStateStore
from .monitoring.manager import MonitoringManager
from .ui.login_dialog import LoginDialog
from .ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def main() -> int:
    """Run the Qt event loop."""

    log_dir = configure_logging()
    logger.info("应用启动，日志目录: %s", log_dir)

    app = QtWidgets.QApplication(sys.argv)
    api_client = ApiClient()
    auth_store = AuthStore()
    window_state = WindowStateStore()
    execution_state = ExecutionStateStore()
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

    window = MainWindow(api_client, monitoring, window_state, execution_state, user_info)
    window.show()

    try:
        update_info = updater.check()
    except NetworkError as exc:
        logger.warning("OTA 检查失败: %s", exc)
    else:
        if update_info:
            QtWidgets.QMessageBox.information(
                window,
                "发现新版本",
                f"检测到新版本 {update_info.version}\n{update_info.release_notes}\n请访问 OTA 服务器下载: {update_info.download_url}",
            )

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
