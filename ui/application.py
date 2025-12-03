"""Application bootstrap for the redesigned TTS client."""
from __future__ import annotations

import logging
import sys

from PyQt5 import QtGui, QtWidgets

from monitoring.manager import MonitoringManager
from services.api_client import ApiClient
from services.auth import AuthStore, RememberedCredentials
from services.update_manager import UpdateManager
from .login_dialog import LoginDialog
from .main_window import MainWindow
from .state import WindowStateStore
from utils.exceptions import AuthenticationError, ClientError, NetworkError
from utils.logging import configure_logging

logger = logging.getLogger(__name__)


def main() -> int:
    """Run the Qt event loop."""

    log_dir = configure_logging()
    logger.info("应用启动，日志目录: %s", log_dir)

    app = QtWidgets.QApplication(sys.argv)
    default_font = QtGui.QFont(app.font())
    base_size = default_font.pointSize()
    default_font.setPointSize(base_size + 2 if base_size > 0 else 12)
    app.setFont(default_font)
    api_client = ApiClient()
    auth_store = AuthStore()
    window_state = WindowStateStore()
    monitoring = MonitoringManager()
    update_manager = UpdateManager()

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

    window = MainWindow(api_client, monitoring, window_state, user_info, update_manager)
    window.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
