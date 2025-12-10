"""登录对话框"""
from __future__ import annotations

from typing import Callable, Optional

from PyQt5 import QtCore, QtGui, QtWidgets


class LoginDialog(QtWidgets.QDialog):
    """展示登录界面的对话框类。"""

    # 登录请求信号：用户名、密码、是否记住我
    login_requested = QtCore.pyqtSignal(str, str, bool)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("登录 Test Tracking System")
        self.setModal(True)  # 设置为模态窗口，阻塞其他 UI 操作
        # self.setMinimumSize(420, 360)
        self.setMinimumSize(450, 550)  # 设定窗口最小尺寸
        self._build_ui()  # 创建 UI 组件

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """构建整个登录界面的 UI 结构。"""

        # 设置背景样式（渐变 + 暗黑主题）
        self.setStyleSheet(
            "QDialog {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0f172a, stop:1 #1e293b);"
            "  color: #f7f9fc;"
            "}"
        )

        # 主布局（垂直排列）
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(24)

        # 标题文本
        title_label = QtWidgets.QLabel("欢迎回来")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 26px; font-weight: 600; color: #f7f9fc;")

        # 副标题
        subtitle = QtWidgets.QLabel("请登录账号以继续")
        subtitle.setAlignment(QtCore.Qt.AlignCenter)
        subtitle.setStyleSheet("color: #8a94a6; font-size: 14px;")

        main_layout.addWidget(title_label)
        main_layout.addWidget(subtitle)

        # 表单容器
        form_widget = QtWidgets.QWidget()
        form_widget.setObjectName("form_panel")
        form_widget.setStyleSheet(
            "#form_panel {"
            "  background: rgba(17, 25, 40, 0.82);"   # 半透明背景
            "  border: 1px solid rgba(148, 163, 184, 0.18);"
            "  border-radius: 18px;"
            "  padding: 32px;"
            "  color: #f7f9fc;"
            "}"
        )

        form_layout = QtWidgets.QVBoxLayout(form_widget)
        form_layout.setSpacing(18)

        # 用户名输入框
        self._username = QtWidgets.QLineEdit()
        self._username.setPlaceholderText("用户名")
        self._username.setClearButtonEnabled(True)
        self._username.setStyleSheet(_INPUT_STYLE)

        # 密码输入框
        self._password = QtWidgets.QLineEdit()
        self._password.setPlaceholderText("密码")
        self._password.setEchoMode(QtWidgets.QLineEdit.Password)  # 隐藏密码字符
        self._password.setStyleSheet(_INPUT_STYLE)

        # “记住我”勾选框
        self._remember = QtWidgets.QCheckBox("记住我")
        self._remember.setStyleSheet("color: #d1d5db;")

        # 错误提示标签（默认隐藏）
        self._error_label = QtWidgets.QLabel()
        self._error_label.setVisible(False)
        self._error_label.setStyleSheet("color: #f87171; font-size: 13px;")

        # 登录按钮
        button = QtWidgets.QPushButton("登录")
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setStyleSheet(
            "QPushButton {"
            "  background-color: #3b82f6;"
            "  color: white;"
            "  padding: 12px;"
            "  border-radius: 8px;"
            "  font-weight: 600;"
            "outline: none;"
            "}"
            "QPushButton:hover { background-color: #2563eb; }"
            "QPushButton:pressed { background-color: #1d4ed8; }"
        )
        button.clicked.connect(self._on_login_clicked)  # 绑定登录按钮事件

        # 将输入组件添加到表单布局
        form_layout.addWidget(self._username)
        form_layout.addWidget(self._password)
        form_layout.addWidget(self._remember)
        form_layout.addWidget(self._error_label)
        form_layout.addWidget(button)

        main_layout.addWidget(form_widget)

        # 页脚信息
        footer = QtWidgets.QLabel("© 2025 TestTrackingSystem QA Platform")
        footer.setAlignment(QtCore.Qt.AlignCenter)
        footer.setStyleSheet("color: #4b5563; font-size: 12px;")

        main_layout.addStretch()
        main_layout.addWidget(footer)

        # 回车键行为：在用户名框按回车 → 跳到密码框；在密码框回车 → 尝试登录
        self._username.returnPressed.connect(self._password.setFocus)
        self._password.returnPressed.connect(self._on_login_clicked)

    # ------------------------------------------------------------------
    def set_initial_values(self, username: str, password: str = "", remember: bool = True) -> None:
        """初始化输入框内容（用于自动填充记住的账号信息）。"""
        self._username.setText(username)
        self._password.setText(password)
        self._remember.setChecked(remember)

    def set_error(self, message: str) -> None:
        """显示错误提示信息。"""
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    # ------------------------------------------------------------------
    def _on_login_clicked(self) -> None:
        """处理登录按钮点击事件。"""
        username = self._username.text().strip()
        password = self._password.text()
        remember = self._remember.isChecked()

        # 输入校验
        if not username or not password:
            self.set_error("请输入用户名和密码")
            return

        # 若无明显错误，隐藏旧的错误标签
        self._error_label.setVisible(False)

        # 发射登录请求信号，由外部业务逻辑处理登录
        self.login_requested.emit(username, password, remember)


# 输入框样式（单独定义便于复用）
_INPUT_STYLE = (
    "QLineEdit {"
    "  background: #111827;"
    "  border: 1px solid #374151;"
    "  border-radius: 8px;"
    "  padding: 12px;"
    "  color: #f7f9fc;"
    "}"
    "QLineEdit:focus { border-color: #3b82f6; }"
)
