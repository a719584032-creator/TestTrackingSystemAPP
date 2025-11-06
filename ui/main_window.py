"""Qt widgets that power the main workflow window."""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

from models import (
    CaseExecutionResult,
    Department,
    PlanCase,
    PlanDetail,
    Project,
    TestPlan,
)
from monitoring.manager import MonitoringManager
from monitoring.parser import MonitoringAction, parse_keywords, require_attachment
from services.api_client import ApiClient, encode_attachment
from ui.state import WindowStateStore
from utils.exceptions import AuthenticationError, ClientError, ValidationError
from config.settings import SETTINGS


STATUS_COLORS = {
    "未开始": "#6B7280",
    "进行中": "#10B981",
    "挂起": "#F59E0B",
    "已完成": "#2563EB",
}

DEFAULT_STATUS_COLOR = "#6B7280"

PASS_SYMBOL_COLOR = "#16A34A"
FAIL_SYMBOL_COLOR = "#DC2626"
BLOCK_SYMBOL_COLOR = "#6B7280"

STATUS_ICON_SIZE = 24

_STATUS_ICON_CACHE: Dict[str, QtGui.QIcon] = {}
_STATUS_ICON_PIXMAP_CACHE: Dict[str, QtGui.QPixmap] = {}

RESULT_LABELS = {
    "pass": "通过",
    "fail": "失败",
    "blocked": "阻塞",
    "block": "阻塞",
    "pending": "未执行",
    "skipped": "已跳过",
}


@dataclass(slots=True)
class CaseDisplayEntry:
    """Flattened representation of a plan case row for the tree view."""

    case: PlanCase
    execution: Optional[CaseExecutionResult]
    device_label: str
    device_model_id: Optional[int]
    plan_device_model_id: Optional[int]
    is_general: bool

    def result_value(self) -> str:
        if self.execution and self.execution.result:
            return self.execution.result.lower()
        if self.is_general and self.case.latest_result:
            return self.case.latest_result.lower()
        return "pending"


class ResultDialog(QtWidgets.QDialog):
    """Dialog used to collect execution metadata before submitting results."""

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        result_label: str,
        case_title: str,
        device_hint: Optional[str],
        require_attachment: bool,
    ) -> None:
        super().__init__(parent)
        self._require_attachment = require_attachment
        self._attachments: List[Dict[str, str]] = []

        self.setWindowTitle(f"提交结果 - {result_label}")
        self.resize(520, 480)

        layout = QtWidgets.QVBoxLayout(self)
        # header = QtWidgets.QLabel(f"当前用例：{case_title}")
        # header.setWordWrap(True)
        # header.setStyleSheet("font-weight: 600; font-size: 14px;")
        # layout.addWidget(header)

        form = QtWidgets.QFormLayout()
        self._remark_edit = QtWidgets.QPlainTextEdit()
        self._remark_edit.setPlaceholderText("执行备注，可记录关键步骤或说明。")
        self._remark_edit.setFixedHeight(100)
        form.addRow("备注", self._remark_edit)

        self._failure_edit = QtWidgets.QLineEdit()
        self._failure_edit.setPlaceholderText("失败原因（可选）")
        form.addRow("失败原因", self._failure_edit)

        self._bug_edit = QtWidgets.QLineEdit()
        self._bug_edit.setPlaceholderText("缺陷编号（可选）")
        form.addRow("缺陷编号", self._bug_edit)

        if device_hint:
            hint_label = QtWidgets.QLabel(device_hint)
            hint_label.setStyleSheet("color: #4B5563;")
            form.addRow("执行机型:", hint_label)
        layout.addLayout(form)

        attachment_box = QtWidgets.QGroupBox("截图 / 附件")
        attachment_layout = QtWidgets.QVBoxLayout(attachment_box)
        self._attachment_list = QtWidgets.QListWidget()
        attachment_layout.addWidget(self._attachment_list)
        btn_row = QtWidgets.QHBoxLayout()
        self._add_attachment_btn = QtWidgets.QPushButton("添加图片")
        self._remove_attachment_btn = QtWidgets.QPushButton("移除选中")
        btn_row.addWidget(self._add_attachment_btn)
        btn_row.addWidget(self._remove_attachment_btn)
        btn_row.addStretch()
        attachment_layout.addLayout(btn_row)
        layout.addWidget(attachment_box)

        if self._require_attachment:
            hint = QtWidgets.QLabel("该结果需要至少上传一张截图作为佐证。")
            hint.setStyleSheet("color: #2563eb;")
            layout.addWidget(hint)

        layout.addStretch()

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._add_attachment_btn.clicked.connect(self._add_attachment)
        self._remove_attachment_btn.clicked.connect(self._remove_attachment)

    # ------------------------------------------------------------------
    def _add_attachment(self) -> None:
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "选择图片",
            os.path.expanduser("~"),
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        for path in files:
            try:
                payload = encode_attachment(path)
            except OSError as exc:  # pragma: no cover - file IO
                QtWidgets.QMessageBox.warning(self, "读取失败", str(exc))
                continue
            payload["local_path"] = path
            self._attachments.append(payload)
            self._attachment_list.addItem(os.path.basename(path))

    def _remove_attachment(self) -> None:
        row = self._attachment_list.currentRow()
        if row < 0 or row >= len(self._attachments):
            return
        self._attachment_list.takeItem(row)
        self._attachments.pop(row)

    # ------------------------------------------------------------------
    def attachments(self) -> List[Dict[str, str]]:
        return list(self._attachments)

    def remark(self) -> str:
        return self._remark_edit.toPlainText().strip()

    def failure_reason(self) -> Optional[str]:
        value = self._failure_edit.text().strip()
        return value or None

    def bug_ref(self) -> Optional[str]:
        value = self._bug_edit.text().strip()
        return value or None

    # ------------------------------------------------------------------
    def accept(self) -> None:  # noqa: D401 - inherited docstring
        if self._require_attachment and not self._attachments:
            QtWidgets.QMessageBox.warning(self, "缺少附件", "请至少上传一张截图后再提交。")
            return
        super().accept()



class MainWindow(QtWidgets.QMainWindow):
    """Primary window containing the execution UI."""

    def __init__(
        self,
        api_client: ApiClient,
        monitoring: MonitoringManager,
        state_store: WindowStateStore,
        user_info: Dict[str, object],
    ) -> None:
        super().__init__()
        self._api = api_client
        self._monitoring = monitoring
        self._state_store = state_store
        self._user = user_info
        self._logger = logging.getLogger(__name__)

        self._departments: List[Department] = []
        self._projects: List[Project] = []
        self._plans: List[TestPlan] = []
        self._cases: List[PlanCase] = []
        self._filtered_entries: List[CaseDisplayEntry] = []
        self._current_entry: Optional[CaseDisplayEntry] = None
        self._current_case: Optional[PlanCase] = None
        self._current_actions: List[MonitoringAction] = []
        self._plan_detail: Optional[PlanDetail] = None
        self._current_device_id: Optional[int] = None
        self._current_plan_device_model_id: Optional[int] = None
        self._execution_locked = False
        self._awaiting_monitor_completion_for_pass = False
        self._pending_filter_state: Optional[Dict[str, object]] = None
        self._pending_selection: Optional[Tuple[int, Optional[int], Optional[int], bool]] = None
        self._auto_start_in_progress = False

        self._state_file_path = SETTINGS.ui_state_file
        self._restore_department_id: Optional[int] = None
        self._restore_project_id: Optional[int] = None
        self._restore_plan_id: Optional[int] = None
        self._restore_start_clicked = False
        self.restore_state()

        self.setWindowTitle("TTS 测试执行客户端")
        self.resize(1200, 680)
        self.setMinimumSize(1024, 640)
        self._build_ui()
        self._connect_signals()
        self._restore_window_state()

        QtCore.QTimer.singleShot(100, self._load_departments)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(16)

        # ------------------------------------------------------------------
        # Unified filter area
        filter_box = QtWidgets.QGroupBox("筛选")
        filter_layout = QtWidgets.QGridLayout(filter_box)
        filter_layout.setHorizontalSpacing(12)
        filter_layout.setVerticalSpacing(10)

        filter_layout.addWidget(QtWidgets.QLabel("部门"), 0, 0)
        self._department_combo = QtWidgets.QComboBox()
        self._department_combo.setMinimumWidth(180)
        self._department_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        filter_layout.addWidget(self._department_combo, 0, 1)

        filter_layout.addWidget(QtWidgets.QLabel("项目"), 0, 2)
        self._project_combo = QtWidgets.QComboBox()
        self._project_combo.setMinimumWidth(200)
        self._project_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        filter_layout.addWidget(self._project_combo, 0, 3)

        filter_layout.addWidget(QtWidgets.QLabel("计划"), 0, 4)
        self._plan_combo = QtWidgets.QComboBox()
        self._plan_combo.setMinimumWidth(200)
        self._plan_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        filter_layout.addWidget(self._plan_combo, 0, 5)

        filter_layout.addWidget(QtWidgets.QLabel("机型"), 1, 0)
        self._device_filter = QtWidgets.QComboBox()
        self._device_filter.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self._device_filter.setMinimumWidth(200)
        filter_layout.addWidget(self._device_filter, 1, 1)

        filter_layout.addWidget(QtWidgets.QLabel("模块目录"), 1, 2)
        self._directory_filter = QtWidgets.QComboBox()
        self._directory_filter.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self._directory_filter.addItem("全部", None)
        filter_layout.addWidget(self._directory_filter, 1, 3)

        filter_layout.addWidget(QtWidgets.QLabel("结果"), 1, 4)
        self._result_filter = QtWidgets.QComboBox()
        self._result_filter.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self._result_filter.addItem("全部", None)
        for value in ["pass", "fail", "blocked", "pending", "skipped"]:
            self._result_filter.addItem(value, value)
        filter_layout.addWidget(self._result_filter, 1, 5)

        self._refresh_btn = QtWidgets.QPushButton("刷新计划数据")
        self._refresh_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        self._refresh_btn.clicked.connect(self._reload_current_plan)
        filter_layout.addWidget(self._refresh_btn, 0, 6, 2, 1)

        filter_layout.setColumnStretch(1, 1)
        filter_layout.setColumnStretch(3, 1)
        filter_layout.setColumnStretch(5, 1)
        root_layout.addWidget(filter_box)

        plan_box = QtWidgets.QGroupBox("计划总览")
        plan_box.setStyleSheet(
            """
            QGroupBox {
                border: 1px solid #E5E7EB;
                border-radius: 10px;
                margin-top: 12px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 6px;
                color: #1F2937;
                font-size: 15px;
            }
            """
        )
        plan_layout = QtWidgets.QVBoxLayout(plan_box)
        plan_layout.setSpacing(14)
        plan_layout.setContentsMargins(20, 24, 20, 20)

        header_row = QtWidgets.QHBoxLayout()
        header_row.setSpacing(12)

        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setSpacing(4)

        plan_header_style = "font-size: 18px; font-weight: 600; color: #111827;"
        plan_body_style = "font-size: 18px; color: #111827;"

        self._plan_title_label = QtWidgets.QLabel("未选择计划")
        self._plan_title_label.setStyleSheet(plan_header_style)
        self._plan_title_label.setWordWrap(True)
        info_layout.addWidget(self._plan_title_label)

        self._plan_period_label = QtWidgets.QLabel("执行时间：—")
        self._plan_period_label.setStyleSheet(plan_body_style)
        self._plan_period_label.setWordWrap(True)
        info_layout.addWidget(self._plan_period_label)

        self._plan_tester_label = QtWidgets.QLabel("执行人员：—")
        self._plan_tester_label.setStyleSheet(plan_body_style)
        self._plan_tester_label.setWordWrap(True)
        info_layout.addWidget(self._plan_tester_label)

        header_row.addLayout(info_layout, stretch=1)

        self._plan_status_label = QtWidgets.QLabel("未选择")
        self._plan_status_label.setAlignment(QtCore.Qt.AlignCenter)
        self._plan_status_label.setFixedHeight(36)
        self._plan_status_label.setMinimumWidth(96)
        self._plan_status_label.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )
        self._apply_status_style(DEFAULT_STATUS_COLOR)
        header_row.addWidget(
            self._plan_status_label, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignTop
        )

        plan_layout.addLayout(header_row)

        stats_box = QtWidgets.QWidget()
        stats_box.setStyleSheet(
            "background-color: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px;"
        )
        stats_layout = QtWidgets.QHBoxLayout(stats_box)
        stats_layout.setContentsMargins(12, 10, 12, 10)
        stats_layout.setSpacing(8)
        self._plan_stat_labels: Dict[str, Tuple[QtWidgets.QLabel, str]] = {}
        stat_configs = [
            ("total", "总数", "#EEF2FF", "#1E3A8A"),
            ("executed", "已执行", "#ECFEFF", "#155E75"),
            ("pass", "通过", "#DCFCE7", "#047857"),
            ("fail", "失败", "#FEE2E2", "#B91C1C"),
            ("block", "阻塞", "#FEF3C7", "#B45309"),
            ("notrun", "未执行", "#E5E7EB", "#374151"),
        ]
        for key, title, bg, fg in stat_configs:
            pill = QtWidgets.QLabel(f"{title} 0")
            pill.setAlignment(QtCore.Qt.AlignCenter)
            pill.setStyleSheet(
                f"""
                QLabel {{
                    background-color: {bg};
                    color: {fg};
                    border-radius: 10px;
                    padding: 6px 12px;
                    font-weight: 600;
                    font-size: 18px;
                }}
                """
            )
            stats_layout.addWidget(pill)
            self._plan_stat_labels[key] = (pill, title)
        stats_layout.addStretch()
        plan_layout.addWidget(stats_box)

        root_layout.addWidget(plan_box)

        # ------------------------------------------------------------------
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        root_layout.addWidget(splitter, stretch=1)

        # Left panel: filters and case tree
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setSpacing(12)
        self._case_tree = QtWidgets.QTreeWidget()
        self._case_tree.setHeaderLabels(["测试用例"])
        self._case_tree.header().setStretchLastSection(True)
        self._case_tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._case_tree.setIndentation(18)
        self._case_tree.setUniformRowHeights(True)
        self._case_tree.setAlternatingRowColors(True)
        self._case_tree.setAnimated(True)
        self._case_tree.header().setDefaultAlignment(
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
        )
        self._case_tree.setStyleSheet(
            """
            QTreeWidget {
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                background-color: #FFFFFF;
                alternate-background-color: #F9FAFB;
            }
            QTreeWidget::item {
                padding: 8px 10px;
            }
            QTreeWidget::item:selected {
                background-color: #DBEAFE;
                color: #1E3A8A;
            }
            QTreeWidget::item:hover {
                background-color: #F3F4F6;
            }
            QTreeView::branch {
                background: transparent;
            }
            QTreeView::branch:has-siblings:!adjoins-item {
                border-image: none;
                image: none;
                border-left: 1px dashed #CBD5E1;
            }
            QTreeView::branch:has-siblings:adjoins-item {
                border-image: none;
                image: none;
                border-left: 1px dashed #CBD5E1;
                border-top: 1px dashed #CBD5E1;
            }
            QTreeView::branch:!has-children:!has-siblings:adjoins-item {
                border-image: none;
                image: none;
                border-left: 1px dashed #CBD5E1;
                border-top: 1px dashed #CBD5E1;
            }
            QTreeView::branch:has-children:!has-siblings:adjoins-item {
                border-image: none;
                image: none;
                border-left: 1px dashed #CBD5E1;
                border-top: 1px dashed #CBD5E1;
            }
            QTreeView::branch:has-children:has-siblings {
                border-image: none;
                image: none;
                border-left: 1px dashed #CBD5E1;
            }
            """
        )
        left_layout.addWidget(self._case_tree, stretch=1)

        splitter.addWidget(left_widget)

        # Right panel: case detail, monitoring
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setSpacing(12)

        case_box = QtWidgets.QGroupBox("用例详情")
        case_layout = QtWidgets.QVBoxLayout(case_box)
        case_layout.setSpacing(10)

        title_row = QtWidgets.QHBoxLayout()
        title_row.setSpacing(8)
        self._title_icon_label = QtWidgets.QLabel()
        self._title_icon_label.setFixedSize(STATUS_ICON_SIZE, STATUS_ICON_SIZE)
        self._title_icon_label.setScaledContents(True)
        self._title_icon_label.setVisible(False)
        title_row.addWidget(self._title_icon_label, 0, QtCore.Qt.AlignTop)

        self._title_label = QtWidgets.QLabel("请选择一条用例")
        self._title_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        self._title_label.setWordWrap(True)
        title_row.addWidget(self._title_label, 1)
        title_row.addStretch()
        case_layout.addLayout(title_row)

        self._precondition_title = QtWidgets.QLabel("前置条件")
        self._precondition_title.setStyleSheet("font-weight: 600;")
        case_layout.addWidget(self._precondition_title)

        self._precondition_view = QtWidgets.QPlainTextEdit()
        self._precondition_view.setReadOnly(True)
        self._precondition_view.setPlaceholderText("暂无前置条件")
        self._precondition_view.setMinimumHeight(80)
        case_layout.addWidget(self._precondition_view)

        self._steps_title = QtWidgets.QLabel("执行步骤")
        self._steps_title.setStyleSheet("font-weight: 600;")
        case_layout.addWidget(self._steps_title)

        self._steps_view = QtWidgets.QPlainTextEdit()
        self._steps_view.setReadOnly(True)
        self._steps_view.setPlaceholderText("暂无执行步骤")
        self._steps_view.setMinimumHeight(160)
        case_layout.addWidget(self._steps_view)

        self._expected_title = QtWidgets.QLabel("预期结果")
        self._expected_title.setStyleSheet("font-weight: 600;")
        case_layout.addWidget(self._expected_title)

        self._expected_view = QtWidgets.QPlainTextEdit()
        self._expected_view.setReadOnly(True)
        self._expected_view.setPlaceholderText("暂无预期结果")
        self._expected_view.setMinimumHeight(100)
        case_layout.addWidget(self._expected_view)

        self._attachment_hint = QtWidgets.QLabel("")
        self._attachment_hint.setStyleSheet("color: #2563eb;")
        case_layout.addWidget(self._attachment_hint)

        right_layout.addWidget(case_box)

        monitor_box = QtWidgets.QGroupBox("监控日志")
        monitor_layout = QtWidgets.QVBoxLayout(monitor_box)
        monitor_layout.setSpacing(12)

        self._start_monitor_btn = QtWidgets.QPushButton("开始执行")

        monitor_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        keyword_widget = QtWidgets.QWidget()
        keyword_layout = QtWidgets.QVBoxLayout(keyword_widget)
        keyword_layout.setContentsMargins(0, 0, 0, 0)
        keyword_layout.setSpacing(6)
        self._keyword_list = QtWidgets.QListWidget()
        keyword_layout.addWidget(self._keyword_list)
        self._keyword_error = QtWidgets.QLabel()
        self._keyword_error.setStyleSheet("color: #dc2626;")
        self._keyword_error.setVisible(False)
        keyword_layout.addWidget(self._keyword_error)
        monitor_splitter.addWidget(keyword_widget)

        log_widget = QtWidgets.QWidget()
        log_layout = QtWidgets.QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        self._log_view = QtWidgets.QPlainTextEdit()
        self._log_view.setReadOnly(True)
        log_layout.addWidget(self._log_view)
        monitor_splitter.addWidget(log_widget)
        monitor_splitter.setStretchFactor(0, 1)
        monitor_splitter.setStretchFactor(1, 2)
        monitor_layout.addWidget(monitor_splitter)

        right_layout.addWidget(monitor_box, stretch=1)

        action_frame = QtWidgets.QFrame()
        action_layout = QtWidgets.QHBoxLayout(action_frame)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(12)
        action_layout.addWidget(self._start_monitor_btn)
        self._pass_btn = QtWidgets.QPushButton("标记通过")
        self._fail_btn = QtWidgets.QPushButton("标记失败")
        self._block_btn = QtWidgets.QPushButton("标记阻塞")
        self._style_action_button(self._pass_btn, "#10B981")
        self._style_action_button(self._fail_btn, "#EF4444")
        self._style_action_button(self._block_btn, "#F59E0B")
        action_layout.addWidget(self._pass_btn)
        action_layout.addWidget(self._fail_btn)
        action_layout.addWidget(self._block_btn)
        action_layout.addStretch()
        right_layout.addWidget(action_frame)

        self._result_buttons = [self._pass_btn, self._fail_btn, self._block_btn]
        self._set_action_buttons_mode(False)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        # Status bar
        status = QtWidgets.QStatusBar()
        self.setStatusBar(status)
        user_name = self._user.get("real_name") or self._user.get("username", "未登录")
        status.showMessage(f"当前用户: {user_name}")

    # ------------------------------------------------------------------
    def _apply_status_style(self, color: str) -> None:
        self._plan_status_label.setStyleSheet(
            f"""
            QLabel {{
                background-color: {color};
                color: #FFFFFF;
                border: none;
                border-radius: 14px;
                padding: 4px 12px;
                font-weight: 600;
                font-size: 18px;
            }}
            """
        )

    def _style_action_button(self, button: QtWidgets.QPushButton, color: str) -> None:
        hover_color = self._tint_color(color, 1.1)
        button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:disabled {{
                background-color: #9CA3AF;
                color: #F9FAFB;
            }}
            """
        )

    @staticmethod
    def _tint_color(color: str, factor: float) -> str:
        hex_value = color.lstrip("#")
        if len(hex_value) != 6:
            return color
        r = min(255, int(int(hex_value[0:2], 16) * factor))
        g = min(255, int(int(hex_value[2:4], 16) * factor))
        b = min(255, int(int(hex_value[4:6], 16) * factor))
        return f"#{r:02X}{g:02X}{b:02X}"

    # ------------------------------------------------------------------
    def _refresh_start_button_state(self) -> None:
        enabled = bool(self._current_actions) and not self._execution_locked
        self._start_monitor_btn.setEnabled(enabled)

    def _set_action_buttons_mode(self, running: bool) -> None:
        self._start_monitor_btn.setVisible(not running)
        for button in self._result_buttons:
            button.setVisible(running)
        if running:
            self._fail_btn.setEnabled(True)
            self._block_btn.setEnabled(True)
            self._update_pass_button_state()
        else:
            self._awaiting_monitor_completion_for_pass = False
            for button in self._result_buttons:
                button.setEnabled(False)
            self._pass_btn.setToolTip("")
            self._refresh_start_button_state()

    def _update_pass_button_state(self) -> None:
        if self._awaiting_monitor_completion_for_pass:
            self._pass_btn.setEnabled(False)
            self._pass_btn.setToolTip("监控进行中，完成所有监控动作后才能标记通过")
        else:
            self._pass_btn.setEnabled(True)
            self._pass_btn.setToolTip("")

    def _set_execution_lock(self, locked: bool) -> None:
        if self._execution_locked == locked:
            return
        self._execution_locked = locked
        widgets: Sequence[QtWidgets.QWidget] = [
            self._department_combo,
            self._project_combo,
            self._plan_combo,
            self._device_filter,
            self._directory_filter,
            self._result_filter,
            self._refresh_btn,
        ]
        for widget in widgets:
            widget.setEnabled(not locked)
        self._case_tree.setDisabled(locked)
        self._refresh_start_button_state()

    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        # 使用整数重载，避免 PyQt 选择字符串信号导致比较时报错
        self._department_combo.currentIndexChanged[int].connect(
            self._on_department_changed
        )
        self._project_combo.currentIndexChanged[int].connect(self._on_project_changed)
        self._plan_combo.currentIndexChanged[int].connect(self._on_plan_changed)
        self._directory_filter.currentIndexChanged.connect(self._apply_filters)
        self._device_filter.currentIndexChanged.connect(self._apply_filters)
        self._result_filter.currentIndexChanged.connect(self._apply_filters)
        self._case_tree.currentItemChanged.connect(self._on_case_selected)

        self._start_monitor_btn.clicked.connect(self._start_monitoring)

        self._pass_btn.clicked.connect(lambda: self._submit_result("pass"))
        self._fail_btn.clicked.connect(lambda: self._submit_result("fail"))
        self._block_btn.clicked.connect(lambda: self._submit_result("block"))

        self._monitoring.log_generated.connect(self._append_log)
        self._monitoring.monitoring_finished.connect(self._on_monitoring_finished)
        self._monitoring.monitoring_error.connect(self._on_monitoring_error)

    # ------------------------------------------------------------------
    def _restore_window_state(self) -> None:
        geometry, state = self._state_store.load()
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)

    def _state_username(self) -> str:
        if not isinstance(self._user, dict):
            return ""
        for key in ("username", "account", "user_name"):
            value = self._user.get(key)
            if value:
                return str(value)
        return ""

    @staticmethod
    def _int_or_none(value: object) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _load_state_payload(self) -> Dict[str, object]:
        username = self._state_username()
        if not username:
            return {}
        try:
            with self._state_file_path.open("r", encoding="utf-8") as state_file:
                payload = json.load(state_file)
        except FileNotFoundError:
            return {}
        except Exception as exc:  # pragma: no cover - defensive cleanup
            self._logger.error("读取状态文件失败: %s", exc)
            try:
                self._state_file_path.unlink(missing_ok=True)
            except OSError:
                pass
            return {}
        if not isinstance(payload, dict):
            return {}
        if payload.get("username") != username:
            return {}
        return payload

    def restore_state(self) -> None:
        state = self._load_state_payload()
        if not state:
            self._pending_filter_state = None
            self._pending_selection = None
            self._restore_department_id = None
            self._restore_project_id = None
            self._restore_plan_id = None
            self._restore_start_clicked = False
            return

        self._restore_department_id = self._int_or_none(state.get("department_id"))
        self._restore_project_id = self._int_or_none(state.get("project_id"))
        self._restore_plan_id = self._int_or_none(state.get("plan_id"))

        filters = state.get("filters")
        if isinstance(filters, dict):
            self._pending_filter_state = {
                "directory": filters.get("directory"),
                "device": filters.get("device"),
                "result": filters.get("result"),
            }
        else:
            self._pending_filter_state = None

        selection = state.get("selection")
        if (
            isinstance(selection, (list, tuple))
            and len(selection) == 4
            and selection[0] is not None
        ):
            try:
                self._pending_selection = (
                    int(selection[0]),
                    self._int_or_none(selection[1]),
                    self._int_or_none(selection[2]),
                    bool(selection[3]),
                )
            except (TypeError, ValueError):
                self._pending_selection = None
        else:
            self._pending_selection = None

        self._restore_start_clicked = bool(state.get("start_clicked"))

    def save_state(self) -> None:
        username = self._state_username()
        if not username:
            return

        state: Dict[str, object] = {
            "username": username,
            "department_id": self._int_or_none(self._department_combo.currentData()),
            "project_id": self._int_or_none(self._project_combo.currentData()),
            "plan_id": self._int_or_none(self._plan_combo.currentData()),
            "filters": {
                "directory": self._directory_filter.currentData(),
                "device": self._device_filter.currentData(),
                "result": self._result_filter.currentData(),
            },
            "start_clicked": bool(self._monitoring.is_running() or self._execution_locked),
        }

        selection = self._selection_key(self._current_entry)
        if selection:
            state["selection"] = [selection[0], selection[1], selection[2], selection[3]]

        try:
            self._state_file_path.parent.mkdir(parents=True, exist_ok=True)
            with self._state_file_path.open("w", encoding="utf-8") as state_file:
                json.dump(state, state_file, ensure_ascii=False, indent=2)
        except OSError as exc:  # pragma: no cover - file IO errors are non-fatal
            self._logger.warning("保存状态失败: %s", exc)

    # ------------------------------------------------------------------
    def _append_log(self, message: str) -> None:
        self._log_view.appendPlainText(message)

    def _on_monitoring_finished(self) -> None:
        self._append_log("监控已结束")
        if self._awaiting_monitor_completion_for_pass:
            self._awaiting_monitor_completion_for_pass = False
            if self._pass_btn.isVisible():
                self._update_pass_button_state()
        self.save_state()

    def _on_monitoring_error(self, message: str) -> None:
        QtWidgets.QMessageBox.critical(self, "监控失败", message)
        self._set_action_buttons_mode(False)
        self._set_execution_lock(False)
        self.save_state()

    # ------------------------------------------------------------------
    def _clear_project_combo(self) -> None:
        with QtCore.QSignalBlocker(self._project_combo):
            self._project_combo.clear()
            self._project_combo.addItem("请选择项目", None)
            self._project_combo.setCurrentIndex(0)
        self._project_combo.setEnabled(bool(self._projects))

    def _clear_plan_combo(self) -> None:
        with QtCore.QSignalBlocker(self._plan_combo):
            self._plan_combo.clear()
            self._plan_combo.addItem("请选择计划", None)
            self._plan_combo.setCurrentIndex(0)
        self._plan_combo.setEnabled(bool(self._plans))

    def _clear_project_and_plan(self) -> None:
        self._clear_project_combo()
        self._clear_plan_combo()

    def _populate_project_combo(self) -> None:
        self._clear_project_combo()
        if not self._projects:
            self._restore_project_id = None
            self._plans = []
            self._clear_plan_combo()
            return

        with QtCore.QSignalBlocker(self._project_combo):
            self._project_combo.clear()
            self._project_combo.addItem("请选择项目", None)
            for project in self._projects:
                self._project_combo.addItem(project.name, project.id)

        target_index = 0
        if self._restore_project_id is not None:
            restored_index = self._project_combo.findData(self._restore_project_id)
            if restored_index >= 0:
                target_index = restored_index

        self._restore_project_id = None
        self._project_combo.setEnabled(True)
        self._project_combo.setCurrentIndex(target_index)

    def _populate_plan_combo(self) -> None:
        self._clear_plan_combo()
        if not self._plans:
            self._restore_plan_id = None
            return

        with QtCore.QSignalBlocker(self._plan_combo):
            self._plan_combo.clear()
            self._plan_combo.addItem("请选择计划", None)
            for plan in self._plans:
                self._plan_combo.addItem(plan.name, plan.id)

        target_index = 0
        if self._restore_plan_id is not None:
            restored_index = self._plan_combo.findData(self._restore_plan_id)
            if restored_index >= 0:
                target_index = restored_index

        self._restore_plan_id = None
        self._plan_combo.setEnabled(True)
        self._plan_combo.setCurrentIndex(target_index)

    # ------------------------------------------------------------------
    def _load_departments(self) -> None:
        try:
            self._departments = self._api.get_departments()
        except AuthenticationError:
            QtWidgets.QMessageBox.critical(self, "未授权", "凭据已失效，请重新登录。")
            self.close()
            return
        except ClientError as exc:
            QtWidgets.QMessageBox.warning(self, "加载失败", str(exc))
            return
        with QtCore.QSignalBlocker(self._department_combo):
            self._department_combo.clear()
            self._department_combo.addItem("请选择部门", None)
            for dept in self._departments:
                self._department_combo.addItem(dept.name, dept.id)

        self._department_combo.setEnabled(bool(self._departments))
        target_index = 0
        if self._restore_department_id is not None:
            restored_index = self._department_combo.findData(self._restore_department_id)
            if restored_index >= 0:
                target_index = restored_index
        self._department_combo.setCurrentIndex(target_index)
        if target_index == 0:
            self._projects = []
            self._plans = []
            self._clear_project_and_plan()
        self._restore_department_id = None
        self.save_state()

    def _on_department_changed(self, _index: object) -> None:
        dept_id = self._int_or_none(self._department_combo.currentData())
        if dept_id is None:
            self._projects = []
            self._plans = []
            self._clear_project_and_plan()
            self.save_state()
            return

        dept = next(
            (
                item
                for item in self._departments
                if self._int_or_none(getattr(item, "id", None)) == dept_id
            ),
            None,
        )
        if dept is None:
            self._logger.warning("未找到 ID 为 %s 的部门", dept_id)
            return

        self._logger.info("选择部门 %s (ID: %s)", dept.name, dept_id)

        try:
            self._projects = self._api.get_projects(int(dept_id))
        except ClientError as exc:
            QtWidgets.QMessageBox.warning(self, "加载项目失败", str(exc))
            self._projects = []
            self._plans = []
            self._clear_project_and_plan()
            return

        self._populate_project_combo()
        self.save_state()

    def _on_project_changed(self, _index: object) -> None:
        project_id = self._int_or_none(self._project_combo.currentData())
        dept_id = self._int_or_none(self._department_combo.currentData())
        if project_id is None:
            self._plans = []
            self._clear_plan_combo()
            self.save_state()
            return
        if dept_id is None:
            self._logger.warning("当前项目选择缺少部门上下文")
            return

        project = next(
            (
                item
                for item in self._projects
                if self._int_or_none(getattr(item, "id", None)) == project_id
            ),
            None,
        )
        if project is None:
            self._logger.warning("未找到 ID 为 %s 的项目", project_id)
            return

        self._logger.info(
            "选择项目 %s (ID: %s) 于部门 %s",
            project.name,
            project_id,
            dept_id,
        )

        try:
            self._plans = self._api.get_test_plans(int(dept_id), int(project_id))
        except ClientError as exc:
            QtWidgets.QMessageBox.warning(self, "加载计划失败", str(exc))
            self._plans = []
            self._clear_plan_combo()
            return

        self._populate_plan_combo()
        self.save_state()

    def _on_plan_changed(self, _index: object) -> None:
        plan_id = self._int_or_none(self._plan_combo.currentData())
        if plan_id is None:
            self._pending_filter_state = None
            self._cases = []
            self._plan_detail = None
            self._update_plan_summary()
            self._refresh_directory_filter()
            self._refresh_device_filter()
            self._filtered_entries = []
            self._refresh_case_tree()
            self.save_state()
            return

        plan = next(
            (
                item
                for item in self._plans
                if self._int_or_none(getattr(item, "id", None)) == plan_id
            ),
            None,
        )
        if plan is None:
            self._logger.warning("未找到 ID 为 %s 的计划", plan_id)
            return

        self._logger.info("选择计划 %s (ID: %s)", plan.name, plan_id)

        try:
            self._plan_detail = self._api.get_plan_detail(plan_id)
        except AuthenticationError:
            QtWidgets.QMessageBox.critical(self, "未授权", "凭据已失效，请重新登录。")
            self.close()
            return
        except ClientError as exc:
            QtWidgets.QMessageBox.warning(self, "加载计划详情失败", str(exc))
            self._plan_detail = None
        self._update_plan_summary()

        try:
            self._cases = self._api.get_plan_cases(plan_id)
        except ClientError as exc:
            QtWidgets.QMessageBox.warning(self, "加载用例失败", str(exc))
            self._cases = []
        else:
            self._logger.info("计划 %s 用例数量: %d", plan.name, len(self._cases))

        self._refresh_directory_filter()
        self._refresh_device_filter()
        self._restore_pending_filters()
        self._apply_filters()
        self.save_state()

    def _refresh_device_filter(self) -> None:
        devices: Dict[int, str] = {}
        for case in self._cases:
            for model in case.device_models:
                if getattr(model, "id", None) is None:
                    continue
                label = self._format_device_label(model.name, model.model_code, model.id)
                devices[int(model.id)] = label
            for execution in case.execution_results or []:
                if not execution.device_model_id:
                    continue
                device_id = int(execution.device_model_id)
                if device_id not in devices:
                    label = self._format_device_label(
                        execution.device_model_name,
                        execution.device_model_code,
                        device_id,
                    )
                    devices[device_id] = label

        self._device_filter.blockSignals(True)
        self._device_filter.clear()
        self._device_filter.addItem("请选择机型", None)
        self._device_filter.addItem("全部机型", "__ALL__")
        for device_id, label in sorted(devices.items(), key=lambda item: item[1]):
            self._device_filter.addItem(label, device_id)
        self._device_filter.setEnabled(True)
        self._device_filter.blockSignals(False)
        self._device_filter.setCurrentIndex(0)

    def _refresh_directory_filter(self) -> None:
        directories: List[str] = []
        seen: set[str] = set()
        for case in self._cases:
            directory = self._normalize_directory(case.group_path)
            if directory not in seen:
                seen.add(directory)
                directories.append(directory)
        directories.sort()
        self._directory_filter.blockSignals(True)
        self._directory_filter.clear()
        self._directory_filter.addItem("全部", None)
        for directory in directories:
            self._directory_filter.addItem(directory, directory)
        self._directory_filter.blockSignals(False)
        self._directory_filter.setCurrentIndex(0)

    def _set_combobox_current_data(
        self, combo: QtWidgets.QComboBox, value: object
    ) -> None:
        combo.blockSignals(True)
        try:
            target_index = None
            if value is None:
                target_index = 0 if combo.count() else -1
            else:
                for index in range(combo.count()):
                    if combo.itemData(index) == value:
                        target_index = index
                        break
            if target_index is None:
                target_index = 0 if combo.count() else -1
            if target_index >= 0:
                combo.setCurrentIndex(target_index)
        finally:
            combo.blockSignals(False)

    def _restore_pending_filters(self) -> None:
        if not self._pending_filter_state:
            return
        state = self._pending_filter_state
        self._pending_filter_state = None
        self._set_combobox_current_data(
            self._directory_filter, state.get("directory")
        )
        self._set_combobox_current_data(self._device_filter, state.get("device"))
        self._set_combobox_current_data(self._result_filter, state.get("result"))

    def _format_device_label(
        self,
        name: Optional[str],
        model_code: Optional[str],
        device_id: Optional[int],
    ) -> str:
        if name:
            return name
        if model_code:
            return model_code
        if device_id:
            return f"机型#{device_id}"
        return "通用"

    def _latest_execution_for_device(
        self,
        executions: Sequence[CaseExecutionResult],
        device_id: Optional[int],
    ) -> Optional[CaseExecutionResult]:
        candidates = [
            execution
            for execution in executions
            if (execution.device_model_id or None) == device_id
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.executed_at or "")

    def _build_case_entries(self, case: PlanCase) -> List[CaseDisplayEntry]:
        entries: List[CaseDisplayEntry] = []
        executions = case.execution_results or []
        device_models = {
            model.id: model
            for model in case.device_models
            if getattr(model, "id", None)
        }

        if device_models:
            seen_devices: set[int] = set()
            for device_id, model in device_models.items():
                execution = self._latest_execution_for_device(executions, device_id)
                label = self._format_device_label(model.name, model.model_code, device_id)
                plan_device_model_id = execution.plan_device_model_id if execution else None
                entries.append(
                    CaseDisplayEntry(
                        case=case,
                        execution=execution,
                        device_label=label,
                        device_model_id=device_id,
                        plan_device_model_id=plan_device_model_id,
                        is_general=False,
                    )
                )
                seen_devices.add(device_id)

            extra_results: Dict[int, CaseExecutionResult] = {}
            for execution in executions:
                if not execution.device_model_id:
                    continue
                device_id = int(execution.device_model_id)
                if device_id in seen_devices:
                    continue
                current = extra_results.get(device_id)
                if not current or (execution.executed_at or "") > (current.executed_at or ""):
                    extra_results[device_id] = execution
            for device_id, execution in extra_results.items():
                label = self._format_device_label(
                    execution.device_model_name,
                    execution.device_model_code,
                    device_id,
                )
                entries.append(
                    CaseDisplayEntry(
                        case=case,
                        execution=execution,
                        device_label=label,
                        device_model_id=device_id,
                        plan_device_model_id=execution.plan_device_model_id,
                        is_general=False,
                    )
                )
                seen_devices.add(device_id)

            if not entries:
                execution = self._latest_execution_for_device(executions, None)
                entries.append(
                    CaseDisplayEntry(
                        case=case,
                        execution=execution,
                        device_label="通用",
                        device_model_id=None,
                        plan_device_model_id=execution.plan_device_model_id if execution else None,
                        is_general=True,
                    )
                )
            return entries

        execution = self._latest_execution_for_device(executions, None)
        entries.append(
            CaseDisplayEntry(
                case=case,
                execution=execution,
                device_label="通用",
                device_model_id=None,
                plan_device_model_id=None,
                is_general=True,
            )
        )
        return entries

    def _apply_filters(self) -> None:
        directory_value = self._directory_filter.currentData()
        device_value = self._device_filter.currentData()
        result_value = self._result_filter.currentData()

        if device_value is None and self._device_filter.isEnabled():
            self._filtered_entries = []
            self._refresh_case_tree()
            self.save_state()
            return

        entries: List[CaseDisplayEntry] = []
        for case in self._cases:
            if directory_value and self._normalize_directory(case.group_path) != directory_value:
                continue
            case_entries = self._build_case_entries(case)
            for entry in case_entries:
                if device_value not in (None, "__ALL__"):
                    if isinstance(device_value, int):
                        if not entry.is_general and entry.device_model_id != int(device_value):
                            continue
                    else:
                        continue
                if result_value and entry.result_value() != result_value:
                    continue
                entries.append(entry)

        self._filtered_entries = entries
        self._logger.info("筛选后用例数量: %d", len(self._filtered_entries))
        self._refresh_case_tree()
        self.save_state()

    def _update_plan_summary(self) -> None:
        detail = self._plan_detail
        if not detail:
            self._plan_status_label.setText("未选择")
            self._apply_status_style(DEFAULT_STATUS_COLOR)
            self._plan_title_label.setText("未选择计划")
            self._plan_period_label.setText("执行时间：—")
            self._plan_tester_label.setText("执行人员：—")
            for key, (label, title) in self._plan_stat_labels.items():
                label.setText(f"{title} 0")
            return

        if detail.start_date and detail.end_date:
            period = f"{detail.start_date} ~ {detail.end_date}"
        elif detail.start_date:
            period = f"自 {detail.start_date}"
        elif detail.end_date:
            period = f"截至 {detail.end_date}"
        else:
            period = "-"

        testers = "、".join(detail.tester_names()) or "未分配"
        status_text = detail.status or "未开始"
        self._plan_status_label.setText(status_text)
        self._apply_status_style(STATUS_COLORS.get(status_text, DEFAULT_STATUS_COLOR))
        self._plan_title_label.setText(detail.name or "未命名计划")
        self._plan_period_label.setText(f"执行时间：{period}")
        self._plan_tester_label.setText(f"执行人员：{testers}")

        stats_values = {
            "total": 0,
            "executed": 0,
            "pass": 0,
            "fail": 0,
            "block": 0,
            "notrun": 0,
        }
        if detail.statistics:
            stats = detail.statistics
            stats_values.update(
                {
                    "total": stats.total_results,
                    "executed": stats.executed_results,
                    "pass": stats.passed,
                    "fail": stats.failed,
                    "block": stats.blocked,
                    "notrun": stats.not_run,
                }
            )

        for key, (label, title) in self._plan_stat_labels.items():
            label.setText(f"{title} {stats_values.get(key, 0)}")

    def _refresh_case_tree(self) -> None:
        self._case_tree.blockSignals(True)
        self._case_tree.clear()
        if not self._filtered_entries:
            self._case_tree.blockSignals(False)
            self._update_case_detail(None)
            return

        parents: dict[tuple[str, ...], QtWidgets.QTreeWidgetItem] = {}
        root = self._case_tree.invisibleRootItem()
        target_key = self._pending_selection or self._selection_key(self._current_entry)
        selected_item: Optional[QtWidgets.QTreeWidgetItem] = None

        for entry in self._filtered_entries:
            case = entry.case
            tokens = self._directory_tokens(case.group_path)
            parent = root
            key: tuple[str, ...] = ()
            for token in tokens:
                key = key + (token,)
                if key not in parents:
                    node = QtWidgets.QTreeWidgetItem([token])
                    node.setFlags(QtCore.Qt.ItemIsEnabled)
                    node.setFirstColumnSpanned(True)
                    node_font = node.font(0)
                    node_font.setBold(True)
                    node.setFont(0, node_font)
                    node.setForeground(0, QtGui.QBrush(QtGui.QColor("#1F2937")))
                    node.setBackground(0, QtGui.QBrush(QtGui.QColor("#F3F4F6")))
                    node.setSizeHint(0, QtCore.QSize(0, 30))
                    parent.addChild(node)
                    parents[key] = node
                parent = parents[key]
            display_text = self._case_display_text(entry)
            item = QtWidgets.QTreeWidgetItem([display_text])
            item.setData(0, QtCore.Qt.UserRole, entry)
            item.setSizeHint(0, QtCore.QSize(0, 28))
            result_color = self._status_color(entry)
            if result_color:
                item.setForeground(0, QtGui.QBrush(QtGui.QColor(result_color)))
            icon = self._status_icon(entry)
            if icon:
                item.setIcon(0, icon)
            keywords = case.display_keywords()
            if keywords:
                item.setToolTip(0, f"关键字: {keywords}")
            parent.addChild(item)
            if target_key and self._selection_key(entry) == target_key:
                selected_item = item

        self._case_tree.expandAll()
        self._case_tree.blockSignals(False)
        self._pending_selection = None
        if selected_item is not None:
            self._case_tree.setCurrentItem(selected_item)
        else:
            self._select_first_case()

    def _select_first_case(self) -> None:
        root = self._case_tree.invisibleRootItem()

        def find_case(node: QtWidgets.QTreeWidgetItem) -> Optional[QtWidgets.QTreeWidgetItem]:
            for index in range(node.childCount()):
                child = node.child(index)
                if child.data(0, QtCore.Qt.UserRole):
                    return child
                found = find_case(child)
                if found:
                    return found
            return None

        first_case = find_case(root)
        if first_case is not None:
            self._case_tree.setCurrentItem(first_case)
        else:
            self._update_case_detail(None)

    def _normalize_directory(self, path: Optional[str]) -> str:
        if not path:
            return "未分组"
        parts = [part.strip() for part in str(path).split("/") if part and part.lower() != "root"]
        return "/".join(parts) if parts else "未分组"

    def _directory_tokens(self, path: Optional[str]) -> List[str]:
        normalized = self._normalize_directory(path)
        if normalized == "未分组":
            return ["未分组"]
        return normalized.split("/")

    def _status_color(self, entry: CaseDisplayEntry) -> Optional[str]:
        result = entry.result_value()
        if result == "pass":
            return PASS_SYMBOL_COLOR
        if result == "fail":
            return FAIL_SYMBOL_COLOR
        if result in {"blocked", "block"}:
            return BLOCK_SYMBOL_COLOR
        return None

    def _status_icon(self, entry: CaseDisplayEntry) -> Optional[QtGui.QIcon]:
        mapping = {
            "pass": "pass",
            "fail": "fail",
            "blocked": "blocked",
            "block": "blocked",
        }
        key = mapping.get(entry.result_value())
        if not key:
            return None
        icon = _STATUS_ICON_CACHE.get(key)
        if icon is None:
            pixmap = self._status_icon_pixmap(key)
            icon = QtGui.QIcon(pixmap)
            _STATUS_ICON_CACHE[key] = icon
        return icon

    def _status_icon_pixmap(self, key: str) -> QtGui.QPixmap:
        pixmap = _STATUS_ICON_PIXMAP_CACHE.get(key)
        if pixmap is None:
            pixmap = self._create_status_pixmap(key)
            _STATUS_ICON_PIXMAP_CACHE[key] = pixmap
        return pixmap

    def _create_status_pixmap(self, key: str) -> QtGui.QPixmap:
        size = STATUS_ICON_SIZE
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        try:
            if key == "pass":
                self._draw_filled_circle(painter, QtGui.QColor(PASS_SYMBOL_COLOR), size)
                self._draw_check_mark(painter, size)
            elif key == "fail":
                self._draw_filled_circle(painter, QtGui.QColor(FAIL_SYMBOL_COLOR), size)
                self._draw_cross_mark(painter, size)
            elif key == "blocked":
                self._draw_block_sign(painter, QtGui.QColor(BLOCK_SYMBOL_COLOR), size)
        finally:
            painter.end()
        return pixmap

    @staticmethod
    def _draw_filled_circle(painter: QtGui.QPainter, color: QtGui.QColor, size: int) -> None:
        painter.setBrush(color)
        painter.setPen(QtCore.Qt.NoPen)
        inset = 1
        rect = QtCore.QRectF(inset, inset, size - inset * 2, size - inset * 2)
        painter.drawEllipse(rect)

    @staticmethod
    def _draw_check_mark(painter: QtGui.QPainter, size: int) -> None:
        pen = QtGui.QPen(QtGui.QColor("#FFFFFF"))
        pen.setWidthF(size * 0.18)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        painter.setPen(pen)
        path = QtGui.QPainterPath()
        path.moveTo(size * 0.28, size * 0.55)
        path.lineTo(size * 0.45, size * 0.72)
        path.lineTo(size * 0.76, size * 0.30)
        painter.drawPath(path)

    @staticmethod
    def _draw_cross_mark(painter: QtGui.QPainter, size: int) -> None:
        pen = QtGui.QPen(QtGui.QColor("#FFFFFF"))
        pen.setWidthF(size * 0.18)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(QtCore.QPointF(size * 0.32, size * 0.32), QtCore.QPointF(size * 0.72, size * 0.72))
        painter.drawLine(QtCore.QPointF(size * 0.72, size * 0.32), QtCore.QPointF(size * 0.32, size * 0.72))

    @staticmethod
    def _draw_block_sign(painter: QtGui.QPainter, color: QtGui.QColor, size: int) -> None:
        pen = QtGui.QPen(color)
        pen.setWidthF(size * 0.18)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        inset = pen.widthF() / 2 + 1
        rect = QtCore.QRectF(inset, inset, size - inset * 2, size - inset * 2)
        painter.drawEllipse(rect)
        painter.drawLine(QtCore.QPointF(size * 0.28, size * 0.28), QtCore.QPointF(size * 0.72, size * 0.72))

    def _selection_key(
        self, entry: Optional[CaseDisplayEntry]
    ) -> Optional[Tuple[int, Optional[int], Optional[int], bool]]:
        if not entry:
            return None
        case_identifier: Optional[int] = None
        if entry.case.id is not None:
            case_identifier = int(entry.case.id)
        elif entry.case.case_id is not None:
            case_identifier = int(entry.case.case_id)
        if case_identifier is None:
            return None
        device_id = entry.device_model_id
        if device_id is not None:
            device_id = int(device_id)
        plan_device_id = entry.plan_device_model_id
        if plan_device_id is not None:
            plan_device_id = int(plan_device_id)
        return (case_identifier, device_id, plan_device_id, entry.is_general)

    def _case_display_text(self, entry: CaseDisplayEntry) -> str:
        case = entry.case
        parts: List[str] = []
        title = (case.title or "").strip() or f"用例 {case.case_id}"
        parts.append(title)
        device_hint = entry.device_label.strip()
        if device_hint:
            parts.append(f"({device_hint})")
        keywords = case.display_keywords()
        if keywords:
            parts.append(f"[{keywords}]")
        return " ".join(parts)

    def _on_case_selected(
        self,
        current: Optional[QtWidgets.QTreeWidgetItem],
        previous: Optional[QtWidgets.QTreeWidgetItem],
    ) -> None:
        entry = current.data(0, QtCore.Qt.UserRole) if current else None
        if not entry:
            if previous and previous.data(0, QtCore.Qt.UserRole):
                self._case_tree.setCurrentItem(previous)
            else:
                self._update_case_detail(None)
            return
        case = entry.case
        self._logger.info("选中用例: %s (ID: %s)", case.title, case.case_id)
        self._update_case_detail(entry)
        self.save_state()
        if self._restore_start_clicked:
            self._restore_start_clicked = False
            self._auto_start_in_progress = True
            QtCore.QTimer.singleShot(0, self._start_monitoring)

    def _update_case_detail(self, entry: Optional[CaseDisplayEntry]) -> None:
        self._current_entry = entry
        case = entry.case if entry else None
        self._current_case = case
        self._current_actions = []
        self._current_device_id = entry.device_model_id if entry else None
        self._current_plan_device_model_id = entry.plan_device_model_id if entry else None
        if not self._execution_locked:
            self._set_action_buttons_mode(False)
        if not case:
            self._title_label.setText("请选择一条用例")
            self._title_icon_label.clear()
            self._title_icon_label.setVisible(False)
            self._precondition_view.clear()
            self._steps_view.clear()
            self._expected_view.clear()
            self._keyword_list.clear()
            self._keyword_error.setVisible(False)
            self._attachment_hint.clear()
            self._refresh_start_button_state()
            return

        self._title_label.setText(self._case_display_text(entry))
        icon = self._status_icon(entry)
        if icon:
            pixmap = icon.pixmap(STATUS_ICON_SIZE, STATUS_ICON_SIZE)
            self._title_icon_label.setPixmap(pixmap)
            self._title_icon_label.setVisible(True)
        else:
            self._title_icon_label.clear()
            self._title_icon_label.setVisible(False)

        preconditions = (case.preconditions or "").strip()
        self._precondition_view.setPlainText(preconditions or "暂无前置条件")
        self._precondition_view.verticalScrollBar().setValue(0)

        step_lines: List[str] = []
        for index, step in enumerate(case.steps or [], start=1):
            number = step.no if getattr(step, "no", None) else index
            header = f"{number}. {step.action or ''}".strip()
            parts: List[str] = [header] if header else []
            if step.expected:
                parts.append(f"预期: {step.expected}")
            if getattr(step, "note", None):
                parts.append(f"备注: {step.note}")
            if getattr(step, "keyword", None):
                parts.append(f"关键字: {step.keyword}")
            if parts:
                step_lines.append("\n".join(parts))
        steps_text = "\n\n".join(step_lines) if step_lines else "暂无执行步骤"
        self._steps_view.setPlainText(steps_text)
        self._steps_view.verticalScrollBar().setValue(0)

        expected = (case.expected_result or "").strip()
        self._expected_view.setPlainText(expected or "暂无预期结果")
        self._expected_view.verticalScrollBar().setValue(0)

        self._keyword_list.clear()
        try:
            actions = parse_keywords(case.keyword_actions())
        except ValidationError as exc:
            self._keyword_error.setText(str(exc))
            self._keyword_error.setVisible(True)
            self._current_actions = []
        else:
            self._keyword_error.setVisible(False)
            self._current_actions = actions
            for action in actions:
                self._keyword_list.addItem(f"{action.display_label()} -> {action.amount}")
        self._refresh_start_button_state()
        self._log_view.clear()
        if require_attachment(self._current_actions):
            self._attachment_hint.setText("此用例包含时间监控，提交 PASS/FAIL 必须上传截图")
        else:
            self._attachment_hint.clear()

    # ------------------------------------------------------------------
    def _start_monitoring(self) -> None:
        try:
            if not self._current_case:
                QtWidgets.QMessageBox.information(self, "未选择", "请先选择用例")
                return
            if not self._current_actions:
                QtWidgets.QMessageBox.warning(self, "关键字错误", "关键字无法解析，无法启动监控")
                return
            if self._current_entry:
                result_text = self._existing_result_label(self._current_entry)
                if result_text and not self._auto_start_in_progress:
                    confirm = QtWidgets.QMessageBox.question(
                        self,
                        "确认执行",
                        f"当前用例已有执行结果（{result_text}），是否再次执行？",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.No,
                    )
                    if confirm != QtWidgets.QMessageBox.Yes:
                        return
            self._awaiting_monitor_completion_for_pass = bool(self._current_actions)
            start_time = dt.datetime.now().isoformat()
            self._monitoring.start(self._current_case.case_id, self._current_actions, start_time)
            self._append_log("监控已启动")
            self._logger.info("已启动监控: 用例 %s", self._current_case.case_id)
            self._set_action_buttons_mode(True)
            self._set_execution_lock(True)
            self.save_state()
        finally:
            self._auto_start_in_progress = False

    def _existing_result_label(self, entry: CaseDisplayEntry) -> Optional[str]:
        result: Optional[str] = None
        if entry.execution and entry.execution.result:
            result = entry.execution.result
        elif entry.is_general and entry.case.latest_result:
            result = entry.case.latest_result
        normalized = (result or "").strip().lower()
        if not normalized or normalized == "pending":
            return None
        return RESULT_LABELS.get(normalized, result or normalized)

    def _resolve_submission_device(
        self, entry: CaseDisplayEntry
    ) -> Tuple[Optional[int], Optional[int], Optional[str]]:
        device_model_id = entry.device_model_id
        plan_device_model_id = entry.plan_device_model_id
        hint_text: Optional[str] = None

        if entry.is_general:
            device_model_id = None
            plan_device_model_id = None
            hint_text = "通用"
        else:
            if entry.device_label:
                hint_text = f"{entry.device_label}"
        return device_model_id, plan_device_model_id, hint_text

    def _submit_result(self, result: str) -> None:
        if not self._current_case:
            QtWidgets.QMessageBox.warning(self, "未选择", "请先选择用例")
            return
        if not self._current_entry:
            QtWidgets.QMessageBox.warning(self, "未选择", "请先选择用例")
            return
        if result == "pass" and self._awaiting_monitor_completion_for_pass:
            QtWidgets.QMessageBox.warning(
                self,
                "监控未完成",
                "监控尚未完成，暂不能标记通过。",
            )
            return
        try:
            actions = parse_keywords(self._current_case.keyword_actions())
        except ValidationError as exc:
            QtWidgets.QMessageBox.warning(self, "关键字错误", str(exc))
            return
        need_attachment = result in {"pass", "fail"} and require_attachment(actions)
        device_model_id, plan_device_model_id, device_hint = self._resolve_submission_device(
            self._current_entry
        )
        dialog = ResultDialog(
            self,
            {"pass": "通过", "fail": "失败", "blocked": "阻塞"}.get(result, result.upper()),
            self._case_display_text(self._current_entry),
            device_hint,
            need_attachment,
        )
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        plan_id = self._int_or_none(self._plan_combo.currentData())
        plan_case_id = self._current_case.id
        if plan_id is None or plan_case_id is None:
            QtWidgets.QMessageBox.warning(self, "提交失败", "当前计划信息缺失，请刷新后重试。")
            return
        remark = dialog.remark()
        failure_reason = dialog.failure_reason()
        bug_ref = dialog.bug_ref()
        attachments = [
            {k: v for k, v in payload.items() if k != "local_path"}
            for payload in dialog.attachments()
        ]
        if self._monitoring.is_running():
            self._monitoring.stop()
            self._append_log("监控停止请求已发送")
        self._monitoring.discard_session_state()
        self._awaiting_monitor_completion_for_pass = False
        try:
            self._api.submit_result(
                int(plan_id),
                int(plan_case_id),
                result,
                remark=remark,
                failure_reason=failure_reason,
                bug_ref=bug_ref,
                device_model_id=device_model_id,
                plan_device_model_id=plan_device_model_id,
                attachments=attachments or None,
            )
        except ClientError as exc:
            QtWidgets.QMessageBox.warning(self, "提交失败", str(exc))
            return
        self._logger.info(
            "提交结果: 用例 %s (结果=%s, 设备=%s, 计划设备=%s)",
            self._current_case.case_id,
            result,
            device_model_id,
            plan_device_model_id,
        )
        QtWidgets.QMessageBox.information(self, "成功", "结果已提交")
        self._set_action_buttons_mode(False)
        self._set_execution_lock(False)
        self.save_state()
        self._reload_current_plan()

    def _reload_current_plan(self) -> None:
        self._pending_selection = self._selection_key(self._current_entry)
        plan_id = self._int_or_none(self._plan_combo.currentData())
        if plan_id is not None:
            self._pending_filter_state = {
                "directory": self._directory_filter.currentData(),
                "device": self._device_filter.currentData(),
                "result": self._result_filter.currentData(),
            }
            self._on_plan_changed(self._plan_combo.currentIndex())
            if self._pending_filter_state:
                # 如果计划重新加载过程中未使用这些值，确保不要遗留旧状态。
                self._pending_filter_state = None

    # ------------------------------------------------------------------
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        self.save_state()
        geometry = self.saveGeometry()
        state = self.saveState()
        self._state_store.save(geometry, state)
        if self._monitoring.is_running():
            self._monitoring.stop()
        super().closeEvent(event)
