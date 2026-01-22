"""客户端启动入口"""
from __future__ import annotations

import logging
import sys

from PyQt5 import QtGui, QtWidgets

from monitoring.manager import MonitoringManager
from utils.startup import ensure_startup
from config.settings import APP_NAME
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
    """运行 Qt 事件循环，启动应用程序。"""

    # 初始化日志系统（按日期生成日志目录，并配置全局日志器）
    log_dir = configure_logging()
    logger.info("应用启动，日志目录: %s", log_dir)
    ensure_startup(APP_NAME)

    # 创建 Qt 应用对象
    app = QtWidgets.QApplication(sys.argv)

    # 设置应用默认字体，使 UI 更易阅读
    default_font = QtGui.QFont(app.font())
    base_size = default_font.pointSize()
    default_font.setPointSize(base_size + 2 if base_size > 0 else 12)
    app.setFont(default_font)

    # 初始化核心服务组件
    api_client = ApiClient()                # 负责 API 通信
    auth_store = AuthStore()                # 负责保存和加载本地登录信息
    window_state = WindowStateStore()       # 负责窗口状态持久化
    monitoring = MonitoringManager()        # 监控服务，例如性能或运行状态
    update_manager = UpdateManager()        # OTA 更新管理器

    # 登录后存储从服务器返回的用户信息
    user_info: dict[str, object] = {}

    def attempt_authenticate(username: str, password: str) -> tuple[dict[str, object], Exception | None]:
        """调用认证接口并返回响应数据或异常。"""
        try:
            data = api_client.authenticate(username, password)
        except AuthenticationError as exc:
            logger.warning("用户 %s 登录失败（认证错误）: %s", username, exc)
            return {}, exc
        except (ClientError, NetworkError) as exc:
            # 网络问题或客户端错误
            logger.error("用户 %s 登录失败（网络/客户端错误）: %s", username, exc)
            return {}, exc
        if not isinstance(data, dict):
            data = {}
        return data, None

    # 读取记住的用户凭据
    remembered = auth_store.load()
    auto_login_error: Exception | None = None
    auto_login_success = False
    if remembered:
        data, auto_login_error = attempt_authenticate(
            remembered.username,
            remembered.password
        )
        if auto_login_error is None:
            user_info = data.get("user", {})
            logger.info("用户 %s 自动登录成功", remembered.username)
            auto_login_success = True
        elif isinstance(auto_login_error, AuthenticationError):
            auth_store.clear()

    if not auto_login_success:
        # 登录窗口
        login_dialog = LoginDialog()
        if remembered:
            login_dialog.set_initial_values(
                remembered.username,
                remembered.password,
                True
            )
        if auto_login_error:
            login_dialog.set_error(str(auto_login_error))

        # 登录按钮事件回调
        def handle_login(username: str, password: str, remember: bool) -> None:
            nonlocal user_info
            data, error = attempt_authenticate(username, password)
            if error is not None:
                login_dialog.set_error(str(error))
                return

            # 提取 user 字段
            user_info = data.get("user", {})

            # 是否保存凭据（记住我）
            if remember:
                auth_store.save(
                    RememberedCredentials(username=username, password=password)
                )
            else:
                auth_store.clear()

            logger.info("用户 %s 登录成功", username)

            # 关闭登录对话框并让主界面继续加载
            login_dialog.accept()

        # 绑定登录事件
        login_dialog.login_requested.connect(handle_login)

        # 显示登录对话框
        if login_dialog.exec_() != QtWidgets.QDialog.Accepted:
            # 若用户取消或关闭窗口，则退出应用
            return 0

    # 创建主窗口（传入各服务组件与用户信息）
    window = MainWindow(
        api_client,
        monitoring,
        window_state,
        user_info,
        update_manager
    )

    # 显示主界面
    window.show()

    # 启动 Qt 主事件循环
    return app.exec_()
