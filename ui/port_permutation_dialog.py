"""多口排列用例生成对话框。"""
from __future__ import annotations

import re
from typing import List

from PyQt5 import QtCore, QtWidgets


class PortPermutationDialog(QtWidgets.QDialog):
    """多口排列生成工具。"""

    generate_requested = QtCore.pyqtSignal(object, object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._port_checkboxes: List[QtWidgets.QCheckBox] = []
        self._devices_edit: QtWidgets.QPlainTextEdit | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("多口排列")
        self.setModal(True)
        self.setMinimumSize(460, 420)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        ports_group = QtWidgets.QGroupBox("端口选择")
        ports_layout = QtWidgets.QGridLayout(ports_group)
        ports_layout.setHorizontalSpacing(12)
        ports_layout.setVerticalSpacing(8)

        ports = ["C1", "C2", "C3", "C4", "A1", "A2", "A3", "A4"]
        for index, port in enumerate(ports):
            checkbox = QtWidgets.QCheckBox(port)
            self._port_checkboxes.append(checkbox)
            row = index // 4
            col = index % 4
            ports_layout.addWidget(checkbox, row, col)

        layout.addWidget(QtWidgets.QLabel("请选择端口:"))
        layout.addWidget(ports_group)

        layout.addWidget(QtWidgets.QLabel("请输入设备型号（每行一个）:"))
        self._devices_edit = QtWidgets.QPlainTextEdit()
        self._devices_edit.setPlaceholderText("例如:\nModel-A\nModel-B\nModel-C")
        self._devices_edit.setMinimumHeight(140)
        layout.addWidget(self._devices_edit)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch()
        generate_btn = QtWidgets.QPushButton("生成排列")
        close_btn = QtWidgets.QPushButton("关闭")
        generate_btn.clicked.connect(self._emit_generate)
        close_btn.clicked.connect(self.reject)
        button_row.addWidget(generate_btn)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

    def _emit_generate(self) -> None:
        ports = [cb.text() for cb in self._port_checkboxes if cb.isChecked()]
        if not ports:
            QtWidgets.QMessageBox.warning(self, "提示", "请至少选择一个端口。")
            return
        devices = self._parse_devices()
        if not devices:
            QtWidgets.QMessageBox.warning(self, "提示", "请至少输入一个设备型号。")
            return
        if len(devices) < len(ports):
            QtWidgets.QMessageBox.warning(
                self,
                "提示",
                f"设备型号数量 ({len(devices)}) 不能小于选中端口数量 ({len(ports)})。",
            )
            return
        self.generate_requested.emit(ports, devices)

    def _parse_devices(self) -> List[str]:
        if not self._devices_edit:
            return []
        raw = self._devices_edit.toPlainText()
        devices: List[str] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [item.strip() for item in re.split(r"[,;，；]+", line) if item.strip()]
            if parts:
                devices.extend(parts)
        return devices
