"""显示器用例选择对话框。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

from PyQt5 import QtCore, QtWidgets


@dataclass(frozen=True)
class DisplayCaseSelection:
    system_port: str
    lcd_state: str
    monitor_qty: str
    tbt_monitor: str
    type_c_monitor: str
    dp1_monitor: str
    dp2_monitor: str
    hdmi1_monitor: str
    hdmi2_monitor: str

    def action_text(self) -> str:
        payload = {
            "system_port": self.system_port,
            "lcd_off_on": self.lcd_state,
            "monitor_qty": self.monitor_qty,
            "tbt_monitor": self.tbt_monitor,
            "type_c_monitor": self.type_c_monitor,
            "dp1_monitor": self.dp1_monitor,
            "dp2_monitor": self.dp2_monitor,
            "hdmi1_monitor": self.hdmi1_monitor,
            "hdmi2_monitor": self.hdmi2_monitor,
        }
        return json.dumps(payload)


class DisplayCaseDialog(QtWidgets.QDialog):
    """收集显示器组合的对话框。"""

    generate_requested = QtCore.pyqtSignal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._selections: List[DisplayCaseSelection] = []
        self._system_port_combo: QtWidgets.QComboBox | None = None
        self._lcd_combo: QtWidgets.QComboBox | None = None
        self._monitor_qty_combo: QtWidgets.QComboBox | None = None
        self._tbt_monitor_combo: QtWidgets.QComboBox | None = None
        self._type_c_monitor_combo: QtWidgets.QComboBox | None = None
        self._dp1_monitor_combo: QtWidgets.QComboBox | None = None
        self._dp2_monitor_combo: QtWidgets.QComboBox | None = None
        self._hdmi1_monitor_combo: QtWidgets.QComboBox | None = None
        self._hdmi2_monitor_combo: QtWidgets.QComboBox | None = None
        self._table: QtWidgets.QTableWidget | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("DisplayMatrix")
        self.setModal(True)
        self.setMinimumSize(980, 600)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form_box = QtWidgets.QGroupBox("DisplayMatrix")
        form_layout = QtWidgets.QGridLayout(form_box)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(10)

        self._system_port_combo = QtWidgets.QComboBox()
        self._system_port_combo.addItems(["TBT Port", "USB-C Port"])

        self._lcd_combo = QtWidgets.QComboBox()
        self._lcd_combo.addItems(["On", "Off"])

        self._monitor_qty_combo = QtWidgets.QComboBox()
        self._monitor_qty_combo.addItems(["1", "2", "3", "4"])

        monitor_options = [
            "7680*4320*60",
            "7680*4320*30",
            "5120*2160*60",
            "5120*2160*30",
            "3840*2160*240",
            "3440*1440*100",
            "3840*2160*144",
            "3840*2160*120",
            "3840*2160*60",
            "3840*2160*59",
            "3840*2160*30",
            "3840*2160*29",
            "2560*1440*60",
            "2560*1440*59",
            "1920*1200*60",
            "1920*1200*59",
            "1920*1080*60",
            "1920*1080*59",
            "1024*768*60",
            "1024*768*59",
            "1024*768*30",
            "1024*768*29",
        ]

        def build_monitor_combo() -> QtWidgets.QComboBox:
            combo = QtWidgets.QComboBox()
            combo.addItems(monitor_options)
            combo.setCurrentIndex(-1)
            combo.setMinimumWidth(160)
            return combo

        self._tbt_monitor_combo = build_monitor_combo()
        self._type_c_monitor_combo = build_monitor_combo()
        self._dp1_monitor_combo = build_monitor_combo()
        self._dp2_monitor_combo = build_monitor_combo()
        self._hdmi1_monitor_combo = build_monitor_combo()
        self._hdmi2_monitor_combo = build_monitor_combo()

        form_layout.addWidget(QtWidgets.QLabel("System Port:"), 0, 0)
        form_layout.addWidget(self._system_port_combo, 0, 1)
        form_layout.addWidget(QtWidgets.QLabel("LCD off/on:"), 0, 2)
        form_layout.addWidget(self._lcd_combo, 0, 3)

        form_layout.addWidget(QtWidgets.QLabel("Monitor Qty:"), 1, 0)
        form_layout.addWidget(self._monitor_qty_combo, 1, 1)
        form_layout.addWidget(QtWidgets.QLabel("TBT Monitor:"), 1, 2)
        form_layout.addWidget(self._tbt_monitor_combo, 1, 3)
        form_layout.addWidget(QtWidgets.QLabel("TYPE-C Monitor:"), 1, 4)
        form_layout.addWidget(self._type_c_monitor_combo, 1, 5)

        form_layout.addWidget(QtWidgets.QLabel("DP1/DP5/DP L:"), 2, 0)
        form_layout.addWidget(self._dp1_monitor_combo, 2, 1)
        form_layout.addWidget(QtWidgets.QLabel("DP2/DP6/DP R:"), 2, 2)
        form_layout.addWidget(self._dp2_monitor_combo, 2, 3)
        form_layout.addWidget(QtWidgets.QLabel("HDMI1:"), 2, 4)
        form_layout.addWidget(self._hdmi1_monitor_combo, 2, 5)
        form_layout.addWidget(QtWidgets.QLabel("HDMI2:"), 2, 6)
        form_layout.addWidget(self._hdmi2_monitor_combo, 2, 7)

        add_button = QtWidgets.QPushButton("Add")
        add_button.setMinimumWidth(120)
        add_button.clicked.connect(self._add_selection)

        remove_button = QtWidgets.QPushButton("移除选中")
        remove_button.setMinimumWidth(120)
        remove_button.clicked.connect(self._remove_selection)

        button_column = QtWidgets.QVBoxLayout()
        button_column.setSpacing(8)
        button_column.addWidget(add_button)
        button_column.addWidget(remove_button)
        button_column.addStretch()

        button_container = QtWidgets.QWidget()
        button_container.setLayout(button_column)

        form_row = QtWidgets.QHBoxLayout()
        form_row.addWidget(form_box, stretch=1)
        form_row.addWidget(button_container, 0, QtCore.Qt.AlignTop)
        layout.addLayout(form_row)

        list_label = QtWidgets.QLabel("Test Monitor List:")
        list_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(list_label)

        headers = [
            "System Port",
            "LCD off/on",
            "Monitor Qty",
            "TBT Monitor",
            "TYPE-C Monitor",
            "DP1/DP5/DP L",
            "DP2/DP6/DP R",
            "HDMI1",
            "HDMI2",
        ]
        self._table = QtWidgets.QTableWidget(0, len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table, stretch=1)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch()
        generate_btn = QtWidgets.QPushButton("生成用例")
        close_btn = QtWidgets.QPushButton("关闭")
        generate_btn.clicked.connect(self._emit_generate)
        close_btn.clicked.connect(self.reject)
        button_row.addWidget(generate_btn)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

    def _current_selection(self) -> DisplayCaseSelection | None:
        if not self._system_port_combo or not self._lcd_combo or not self._monitor_qty_combo:
            return None
        if not all(
            [
                self._tbt_monitor_combo,
                self._type_c_monitor_combo,
                self._dp1_monitor_combo,
                self._dp2_monitor_combo,
                self._hdmi1_monitor_combo,
                self._hdmi2_monitor_combo,
            ]
        ):
            return None
        return DisplayCaseSelection(
            system_port=self._system_port_combo.currentText().strip(),
            lcd_state=self._lcd_combo.currentText().strip(),
            monitor_qty=self._monitor_qty_combo.currentText().strip(),
            tbt_monitor=self._tbt_monitor_combo.currentText().strip(),
            type_c_monitor=self._type_c_monitor_combo.currentText().strip(),
            dp1_monitor=self._dp1_monitor_combo.currentText().strip(),
            dp2_monitor=self._dp2_monitor_combo.currentText().strip(),
            hdmi1_monitor=self._hdmi1_monitor_combo.currentText().strip(),
            hdmi2_monitor=self._hdmi2_monitor_combo.currentText().strip(),
        )

    def _add_selection(self) -> None:
        selection = self._current_selection()
        if selection is None:
            QtWidgets.QMessageBox.warning(self, "数据缺失", "请先选择完整的显示器组合。")
            return
        if not any(
            [
                selection.tbt_monitor,
                selection.type_c_monitor,
                selection.dp1_monitor,
                selection.dp2_monitor,
                selection.hdmi1_monitor,
                selection.hdmi2_monitor,
            ]
        ):
            QtWidgets.QMessageBox.information(
                self,
                "请选择分辨率",
                "请至少选择一个显示器分辨率后再添加。",
            )
            return
        self._selections.append(selection)
        if not self._table:
            return
        row = self._table.rowCount()
        self._table.insertRow(row)
        values = [
            selection.system_port,
            selection.lcd_state,
            selection.monitor_qty,
            selection.tbt_monitor,
            selection.type_c_monitor,
            selection.dp1_monitor,
            selection.dp2_monitor,
            selection.hdmi1_monitor,
            selection.hdmi2_monitor,
        ]
        for col, value in enumerate(values):
            item = QtWidgets.QTableWidgetItem(value)
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
            self._table.setItem(row, col, item)

    def _remove_selection(self) -> None:
        if not self._table:
            return
        row = self._table.currentRow()
        if row < 0 or row >= len(self._selections):
            QtWidgets.QMessageBox.information(self, "未选择", "请先选择要移除的行。")
            return
        self._table.removeRow(row)
        self._selections.pop(row)

    def _emit_generate(self) -> None:
        if not self._selections:
            QtWidgets.QMessageBox.information(self, "暂无组合", "请先添加显示器组合。")
            return
        self.generate_requested.emit(list(self._selections))

    def selections(self) -> List[DisplayCaseSelection]:
        return list(self._selections)
