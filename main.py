"""Entry point for the PATVS desktop client."""
from __future__ import annotations

import logging
import sys

from PyQt5 import QtWidgets

from .api.client import ApiClient, ApiError
from .auth import AuthStore, RememberMePayload
from .monitoring.controller import MonitoringController
from .settings import SettingsStore
from .ui.login import LoginDialog
from .ui.main_window import MainWindow
from .updater import OTAUpdater

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")


def run() -> int:
    app = QtWidgets.QApplication(sys.argv)

    api_client = ApiClient()
    auth_store = AuthStore()
    settings = SettingsStore()
    monitoring = MonitoringController()
    updater = OTAUpdater()

    login_dialog = LoginDialog()
    remembered = auth_store.load()
    if remembered:
        login_dialog.set_initial_values(remembered.username, True)
        api_client.set_token(remembered.token)

    user_info = {}

    def handle_login(username: str, password: str, remember: bool) -> None:
        nonlocal user_info
        try:
            data = api_client.authenticate(username, password)
        except ApiError as exc:
            login_dialog.set_error(str(exc))
            return
        user_info = data.get("user", {})
        token = data.get("token")
        if remember and token:
            auth_store.save(RememberMePayload(username=username, token=token))
        else:
            auth_store.clear()
        login_dialog.accept()

    login_dialog.login_requested.connect(handle_login)
    if login_dialog.exec_() != QtWidgets.QDialog.Accepted:
        return 0

    window = MainWindow(api_client, monitoring, settings, user_info)
    window.show()

    update_info = updater.check_for_updates()
    if update_info:
        QtWidgets.QMessageBox.information(
            window,
            "发现新版本",
            f"检测到新版本 {update_info.version}，请访问 OTA 服务器下载安装。",
        )

    return app.exec_()


if __name__ == "__main__":
    sys.exit(run())
