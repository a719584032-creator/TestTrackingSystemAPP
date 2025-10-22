"""Application bootstrap for the redesigned TTS client."""
from __future__ import annotations

import logging
import sys

from PyQt5 import QtWidgets

from .core.api_client import ApiClient
from .core.auth import AuthStore, RememberMePayload
from .core.exceptions import AuthenticationError, ClientError, NetworkError
from .core.ota import OTAUpdater
from .core.settings import WindowStateStore
from .monitoring.manager import MonitoringManager
from .ui.login_dialog import LoginDialog
from .ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def main() -> int:
    """Run the Qt event loop."""

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")

    app = QtWidgets.QApplication(sys.argv)
    api_client = ApiClient()
    auth_store = AuthStore()
    window_state = WindowStateStore()
    monitoring = MonitoringManager()
    updater = OTAUpdater()

    login_dialog = LoginDialog()
    remembered = auth_store.load()
    if remembered:
        login_dialog.set_initial_values(remembered.username, True)
        api_client.set_token(remembered.token)

    user_info: dict[str, object] = {}

    def handle_login(username: str, password: str, remember: bool) -> None:
        nonlocal user_info
        try:
            data = api_client.authenticate(username, password)
        except AuthenticationError as exc:
            login_dialog.set_error(str(exc))
            return
        except (ClientError, NetworkError) as exc:
            login_dialog.set_error(str(exc))
            return
        user_info = data.get("user", {}) if isinstance(data, dict) else {}
        token = data.get("token")
        if remember and token:
            auth_store.save(RememberMePayload(username=username, token=token))
        else:
            auth_store.clear()
        login_dialog.accept()

    login_dialog.login_requested.connect(handle_login)
    if login_dialog.exec_() != QtWidgets.QDialog.Accepted:
        return 0

    window = MainWindow(api_client, monitoring, window_state, user_info)
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
