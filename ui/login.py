"""Login dialog implementation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt5 import QtCore, QtWidgets


@dataclass
class LoginResult:
    username: str
    password: str
    remember_me: bool


class LoginDialog(QtWidgets.QDialog):
    login_requested = QtCore.pyqtSignal(str, str, bool)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("登录 PATVS")
        self.setModal(True)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        form_layout = QtWidgets.QFormLayout()
        self.username_edit = QtWidgets.QLineEdit()
        self.username_edit.setPlaceholderText("用户名")
        self.password_edit = QtWidgets.QLineEdit()
        self.password_edit.setPlaceholderText("密码")
        self.password_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        form_layout.addRow("用户名", self.username_edit)
        form_layout.addRow("密码", self.password_edit)
        layout.addLayout(form_layout)

        self.remember_checkbox = QtWidgets.QCheckBox("记住我")
        layout.addWidget(self.remember_checkbox)

        self.error_label = QtWidgets.QLabel()
        self.error_label.setStyleSheet("color: red;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        button_box = QtWidgets.QDialogButtonBox()
        self.login_button = button_box.addButton("登录", QtWidgets.QDialogButtonBox.AcceptRole)
        self.cancel_button = button_box.addButton("取消", QtWidgets.QDialogButtonBox.RejectRole)
        layout.addWidget(button_box)

    def _connect_signals(self) -> None:
        self.login_button.clicked.connect(self._on_login_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def set_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def set_initial_values(self, username: str, remember: bool) -> None:
        self.username_edit.setText(username)
        self.remember_checkbox.setChecked(remember)

    def _on_login_clicked(self) -> None:
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        remember = self.remember_checkbox.isChecked()
        if not username or not password:
            self.set_error("请输入用户名和密码")
            return
        self.login_requested.emit(username, password, remember)

    def accept_login(self) -> LoginResult:
        return LoginResult(
            username=self.username_edit.text().strip(),
            password=self.password_edit.text(),
            remember_me=self.remember_checkbox.isChecked(),
        )
