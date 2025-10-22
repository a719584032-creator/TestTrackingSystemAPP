"""Modern login dialog with remember-me functionality."""
from __future__ import annotations

from typing import Callable, Optional

from PyQt5 import QtCore, QtGui, QtWidgets


class LoginDialog(QtWidgets.QDialog):
    """Presents the login form."""

    login_requested = QtCore.pyqtSignal(str, str, bool)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("登录 Test Tracking System")
        self.setModal(True)
        self.setMinimumSize(420, 360)
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#141a26"))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#f7f9fc"))
        self.setPalette(palette)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(24)

        title_label = QtWidgets.QLabel("欢迎回来")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 26px; font-weight: 600; color: #f7f9fc;")

        subtitle = QtWidgets.QLabel("请使用公司账号登录以继续")
        subtitle.setAlignment(QtCore.Qt.AlignCenter)
        subtitle.setStyleSheet("color: #8a94a6; font-size: 14px;")

        main_layout.addWidget(title_label)
        main_layout.addWidget(subtitle)

        form_widget = QtWidgets.QWidget()
        form_widget.setObjectName("form_panel")
        form_widget.setStyleSheet(
            "#form_panel {"
            "  background: #1f2937;"
            "  border-radius: 16px;"
            "  padding: 28px;"
            "  color: #f7f9fc;"
            "}"
        )

        form_layout = QtWidgets.QVBoxLayout(form_widget)
        form_layout.setSpacing(18)

        self._username = QtWidgets.QLineEdit()
        self._username.setPlaceholderText("用户名")
        self._username.setClearButtonEnabled(True)
        self._username.setStyleSheet(_INPUT_STYLE)

        self._password = QtWidgets.QLineEdit()
        self._password.setPlaceholderText("密码")
        self._password.setEchoMode(QtWidgets.QLineEdit.Password)
        self._password.setStyleSheet(_INPUT_STYLE)

        self._remember = QtWidgets.QCheckBox("记住我")
        self._remember.setStyleSheet("color: #d1d5db;")

        self._error_label = QtWidgets.QLabel()
        self._error_label.setVisible(False)
        self._error_label.setStyleSheet("color: #f87171; font-size: 13px;")

        button = QtWidgets.QPushButton("登录")
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setStyleSheet(
            "QPushButton {"
            "  background-color: #3b82f6;"
            "  color: white;"
            "  padding: 12px;"
            "  border-radius: 8px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover { background-color: #2563eb; }"
            "QPushButton:pressed { background-color: #1d4ed8; }"
        )
        button.clicked.connect(self._on_login_clicked)

        form_layout.addWidget(self._username)
        form_layout.addWidget(self._password)
        form_layout.addWidget(self._remember)
        form_layout.addWidget(self._error_label)
        form_layout.addWidget(button)

        main_layout.addWidget(form_widget)

        footer = QtWidgets.QLabel("© 2025 PATVS QA Platform")
        footer.setAlignment(QtCore.Qt.AlignCenter)
        footer.setStyleSheet("color: #4b5563; font-size: 12px;")
        main_layout.addStretch()
        main_layout.addWidget(footer)

        self._username.returnPressed.connect(self._password.setFocus)
        self._password.returnPressed.connect(self._on_login_clicked)

    # ------------------------------------------------------------------
    def set_initial_values(self, username: str, remember: bool) -> None:
        self._username.setText(username)
        self._remember.setChecked(remember)

    def set_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    # ------------------------------------------------------------------
    def _on_login_clicked(self) -> None:
        username = self._username.text().strip()
        password = self._password.text()
        remember = self._remember.isChecked()
        if not username or not password:
            self.set_error("请输入用户名和密码")
            return
        self._error_label.setVisible(False)
        self.login_requested.emit(username, password, remember)


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
