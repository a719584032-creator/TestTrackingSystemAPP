""" 测试执行客户端界面 """
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
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
from monitoring.audio_event_constants import AUDIO_EVENT_KEYWORDS
from monitoring.manager import MonitoringManager
from monitoring.parser import (
    MonitoringAction,
    parse_keywords,
    recording_requirement_minutes,
    require_attachment,
)
from monitoring.actions.luyin import get_audio_duration_seconds
from services.api_client import ApiClient, encode_attachment
from services.ota import UpdateInfo
from services.update_manager import UpdateManager
from ui.state import WindowStateStore
from utils.exceptions import AuthenticationError, ClientError, NetworkError, UpdateError, ValidationError
from config.settings import APP_VERSION, SETTINGS




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
    """ 展示/筛选“用例”最新结果 """

    case: PlanCase  # 计划用例对象
    execution: Optional[CaseExecutionResult]  # 执行结果对象
    device_label: str # 设备名称
    device_model_id: Optional[int]  # 设备ID
    plan_device_model_id: Optional[int]  # 计划中的设备ID
    is_general: bool #是否通用用例

    def result_value(self) -> str:
        # 获取最新用例结果并判断是否是通用用例
        if self.execution and self.execution.result:
            return self.execution.result.lower()
        if self.is_general and self.case.latest_result:
            return self.case.latest_result.lower()
        return "pending"


class ResultDialog(QtWidgets.QDialog):
    """ 记录结果对话框 """

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        result_label: str,
        case_title: str,
        device_hint: Optional[str],  # 机型提示
        require_attachment: bool,    # 是否必须上传附件
        recording_requirement: Optional[float] = None,  # 录音时长要求（分钟）
    ) -> None:
        super().__init__(parent)
        self._require_attachment = require_attachment
        self._recording_requirement = recording_requirement
        self._attachments: List[Dict[str, str]] = []

        self.setWindowTitle(f"提交结果 - {result_label}")
        self.resize(520, 480)

        layout = QtWidgets.QVBoxLayout(self)
        # 若需拼接用例标题，可在此创建 QLabel 并加入布局。

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

        attachment_box = QtWidgets.QGroupBox("附件")
        attachment_layout = QtWidgets.QVBoxLayout(attachment_box)
        self._attachment_list = QtWidgets.QListWidget()
        attachment_layout.addWidget(self._attachment_list)
        btn_row = QtWidgets.QHBoxLayout()
        self._add_attachment_btn = QtWidgets.QPushButton("添加附件")
        self._remove_attachment_btn = QtWidgets.QPushButton("移除选中")
        btn_row.addWidget(self._add_attachment_btn)
        btn_row.addWidget(self._remove_attachment_btn)
        btn_row.addStretch()
        attachment_layout.addLayout(btn_row)
        layout.addWidget(attachment_box)

        hint_messages: List[str] = []
        if self._require_attachment:
            hint_messages.append("该结果需要至少上传一个附件作为佐证。")
        if self._recording_requirement:
            hint_messages.append(
                f"请上传时长不少于 {self._recording_requirement:g} 分钟的录音文件，提交前会校验时长。"
            )
        if hint_messages:
            hint = QtWidgets.QLabel("\n".join(hint_messages))
            hint.setStyleSheet("color: #2563eb;")
            layout.addWidget(hint)

        layout.addStretch()

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        # 添加图片
        self._add_attachment_btn.clicked.connect(self._add_attachment)
        # 删除图片
        self._remove_attachment_btn.clicked.connect(self._remove_attachment)

    # ------------------------------------------------------------------
    def _add_attachment(self) -> None:
        """ 添加附件 """
        max_size_bytes = 50 * 1024 * 1024
        current_total = 0
        for payload in self._attachments:
            path = payload.get("local_path")
            if not path:
                continue
            try:
                current_total += Path(path).stat().st_size
            except OSError:
                continue
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "选择附件",
            os.path.expanduser("~"),
            "All Files (*)",
        )
        for path in files:
            try:
                file_size = Path(path).stat().st_size
            except OSError as exc:
                QtWidgets.QMessageBox.warning(self, "读取失败", str(exc))
                continue
            if file_size > max_size_bytes:
                QtWidgets.QMessageBox.warning(self, "文件过大", "请勿上传大于50MB的文件")
                continue
            if current_total + file_size > max_size_bytes:
                QtWidgets.QMessageBox.warning(self, "文件过大", "附件总大小不可超过50MB，请移除部分文件后重试。")
                continue
            try:
                payload = encode_attachment(path)
            except OSError as exc:  # pragma: no cover - 文件 IO 在测试环境难以稳定复现
                QtWidgets.QMessageBox.warning(self, "读取失败", str(exc))
                continue
            payload["local_path"] = path
            self._attachments.append(payload)
            self._attachment_list.addItem(os.path.basename(path))
            current_total += file_size

    def _remove_attachment(self) -> None:
        """ 删除附件 """
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
    def accept(self) -> None:  # noqa: D401 - 继承父类文档字符串
        if self._require_attachment and not self._attachments:
            QtWidgets.QMessageBox.warning(self, "缺少附件", "请至少上传一个附件后再提交。")
            return
        super().accept()



class MainWindow(QtWidgets.QMainWindow):
    """ 执行主窗口UI """
    _current_actions: list[MonitoringAction]
    # OTA 更新相关
    _update_prompt_signal = QtCore.pyqtSignal(object)
    _update_progress_signal = QtCore.pyqtSignal(int, object)
    _update_ready_signal = QtCore.pyqtSignal(object, object)
    _update_error_signal = QtCore.pyqtSignal(str)

    def __init__(
        self,
        api_client: ApiClient,
        monitoring: MonitoringManager,
        state_store: WindowStateStore,
        user_info: Dict[str, object],
        update_manager: UpdateManager,
    ) -> None:
        super().__init__()
        # 初始化所有业务需要字段，方法，对象
        self._api = api_client  # API请求
        self._monitoring = monitoring  # 监控管理器（负责日志解析/关键字监控）
        self._state_store = state_store  # 窗口几何信息保存/恢复
        self._user = user_info  # 当前登录用户信息
        self._updates = update_manager  # OTA 更新管理器
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
        self._case_execution_start_times: Dict[int, str] = {}
        self._audio_log_files: List[str] = []
        self._pending_audio_logs: Optional[List[str]] = None
        self._audio_log_dir_hint = str(SETTINGS.log_root / "logs")
        self._recording_requirement_minutes: Optional[float] = None
        self._refresh_in_progress = False
        self._status_bar: Optional[QtWidgets.QStatusBar] = None
        self._pending_update_info: Optional[UpdateInfo] = None
        self._staged_update_path: Optional[Path] = None
        self._download_dialog: Optional[QtWidgets.QProgressDialog] = None
        self._update_check_thread: Optional[threading.Thread] = None
        self._update_download_thread: Optional[threading.Thread] = None

        # OTA 更新
        self._update_prompt_signal.connect(self._prompt_update)
        self._update_progress_signal.connect(self._update_download_progress)
        self._update_ready_signal.connect(self._on_update_ready)
        self._update_error_signal.connect(self._handle_update_error)

        # 记录UI状态
        self._state_file_path = SETTINGS.ui_state_file
        self._restore_department_id: Optional[int] = None
        self._restore_project_id: Optional[int] = None
        self._restore_plan_id: Optional[int] = None
        self._restore_start_clicked = False
        self.restore_state()

        # 窗口参数
        self._update_window_title()
        self.resize(1280, 1024)
        self.setMinimumSize(1024, 640)
        self._build_ui()
        self._apply_pending_audio_logs()
        self._connect_signals()
        self._restore_window_state()

        # 延迟启动后台任务
        QtCore.QTimer.singleShot(100, self._load_departments)
        QtCore.QTimer.singleShot(2000, self._start_update_check)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """ 创建所有控件和布局 """
        # 创建中心 widget + 顶层布局
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(16)

        # ------------------------------------------------------------------
        # 统一的筛选区域
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
        self._directory_filter.addItem("请选择模块目录", None)
        filter_layout.addWidget(self._directory_filter, 1, 3)

        filter_layout.addWidget(QtWidgets.QLabel("结果"), 1, 4)
        self._result_filter = QtWidgets.QComboBox()
        self._result_filter.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self._result_filter.addItem("全部", None)
        for value in ["pass", "fail", "blocked", "pending", "skipped"]:
            self._result_filter.addItem(value, value)
        filter_layout.addWidget(self._result_filter, 1, 5)

        self._refresh_btn = QtWidgets.QPushButton("刷新数据")
        self._refresh_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        self._refresh_btn.clicked.connect(self._refresh_all_data)
        filter_layout.addWidget(self._refresh_btn, 0, 6, 2, 1)

        filter_layout.setColumnStretch(1, 1)
        filter_layout.setColumnStretch(3, 1)
        filter_layout.setColumnStretch(5, 1)
        root_layout.addWidget(filter_box)

        # 计划总览区域
        plan_box = QtWidgets.QGroupBox("计划总览")
        plan_layout = QtWidgets.QHBoxLayout(plan_box)
        plan_layout.setSpacing(16)
        plan_layout.setContentsMargins(12, 10, 12, 10)

        self._plan_period_label = QtWidgets.QLabel("执行时间：—")
        self._plan_period_label.setWordWrap(True)
        plan_layout.addWidget(self._plan_period_label, stretch=2)

        self._plan_tester_label = QtWidgets.QLabel("执行人员：—")
        self._plan_tester_label.setWordWrap(True)
        plan_layout.addWidget(self._plan_tester_label, stretch=1)

        self._plan_progress_label = QtWidgets.QLabel("执行进度：—")
        self._plan_progress_label.setWordWrap(True)
        plan_layout.addWidget(self._plan_progress_label, stretch=2)

        plan_layout.addStretch(1)

        root_layout.addWidget(plan_box)

        # ------------------------------------------------------------------
        # 用例
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # 左侧面板：筛选与用例树
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
                 outline: none; /* 可选：取消整个TreeWidget的焦点轮廓（如果存在） */
            }
            QTreeWidget::item {
                padding: 8px 10px;
                 outline: none; /* 基础状态下默认无轮廓 */
            }
            QTreeWidget::item:selected {
                background-color: #DBEAFE;
                color: #1E3A8A;
                outline: none; /* 选中状态下强制取消轮廓 */
            }

            QTreeWidget::item:hover {
                background-color: #F3F4F6;
                 outline: none; /* 无论焦点与其他状态如何组合，均无轮廓 */
            }
             /* 关键：针对所有item（包括子项目）的焦点状态，强制取消轮廓 */
            QTreeWidget::item:focus,
            QTreeWidget::item:selected:focus,
            QTreeWidget::item:hover:focus {
                outline: none; /* 无论焦点与其他状态如何组合，均无轮廓 */
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

        # 右侧面板：用例详情与监控操作
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
        self._title_label.setStyleSheet("font-size: 23px; font-weight: 600;")
        self._title_label.setWordWrap(True)
        title_row.addWidget(self._title_label, 1)
        title_row.addStretch()
        case_layout.addLayout(title_row)

        self._precondition_label = QtWidgets.QLabel("前置条件：暂无前置条件")
        self._precondition_label.setWordWrap(True)
        self._precondition_label.setStyleSheet("color: #374151;")
        self._precondition_label.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard
        )
        case_layout.addWidget(self._precondition_label)

        detail_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        detail_splitter.setChildrenCollapsible(False)
        detail_splitter.setHandleWidth(8)

        steps_section = QtWidgets.QWidget()
        steps_layout = QtWidgets.QVBoxLayout(steps_section)
        steps_layout.setContentsMargins(0, 0, 0, 0)
        steps_layout.setSpacing(6)
        self._steps_title = QtWidgets.QLabel("执行步骤")
        self._steps_title.setStyleSheet("font-weight: 600;")
        steps_layout.addWidget(self._steps_title)

        self._steps_view = QtWidgets.QPlainTextEdit()
        self._steps_view.setReadOnly(True)
        self._steps_view.setPlaceholderText("暂无执行步骤")
        self._steps_view.setMinimumHeight(200)
        self._steps_view.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        steps_layout.addWidget(self._steps_view)
        detail_splitter.addWidget(steps_section)

        expected_section = QtWidgets.QWidget()
        expected_layout = QtWidgets.QVBoxLayout(expected_section)
        expected_layout.setContentsMargins(0, 0, 0, 0)
        expected_layout.setSpacing(6)
        self._expected_title = QtWidgets.QLabel("预期结果")
        self._expected_title.setStyleSheet("font-weight: 600;")
        expected_layout.addWidget(self._expected_title)

        self._expected_view = QtWidgets.QPlainTextEdit()
        self._expected_view.setReadOnly(True)
        self._expected_view.setPlaceholderText("暂无预期结果")
        self._expected_view.setMinimumHeight(120)
        self._expected_view.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        expected_layout.addWidget(self._expected_view)
        detail_splitter.addWidget(expected_section)
        detail_splitter.setStretchFactor(0, 5)
        detail_splitter.setStretchFactor(1, 3)

        case_layout.addWidget(detail_splitter, stretch=1)

        self._attachment_hint = QtWidgets.QLabel("")
        self._attachment_hint.setStyleSheet("color: #2563eb;")
        case_layout.addWidget(self._attachment_hint)

        case_box.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        right_layout.addWidget(case_box, stretch=3)

        monitor_box = QtWidgets.QGroupBox("监控日志")
        monitor_layout = QtWidgets.QVBoxLayout(monitor_box)
        monitor_layout.setSpacing(12)

        audio_row = QtWidgets.QHBoxLayout()
        audio_row.setSpacing(8)
        audio_row.addWidget(QtWidgets.QLabel("Lab Audio 日志:"), 0, QtCore.Qt.AlignVCenter)
        self._audio_log_status = QtWidgets.QLabel("未选择")
        self._audio_log_status.setStyleSheet("color: #6B7280;")
        self._audio_log_status.setWordWrap(True)
        audio_row.addWidget(self._audio_log_status, 1)

        self._select_audio_logs_btn = QtWidgets.QPushButton("选择日志")
        self._clear_audio_logs_btn = QtWidgets.QPushButton("清除")
        audio_row.addWidget(self._select_audio_logs_btn)
        audio_row.addWidget(self._clear_audio_logs_btn)
        monitor_layout.addLayout(audio_row)

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

        right_layout.addWidget(monitor_box, stretch=2)

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
        root_layout.addWidget(splitter, stretch=1)

        # 状态栏
        status = QtWidgets.QStatusBar()
        self._status_bar = status
        self.setStatusBar(status)
        status.clearMessage()

    def _style_action_button(self, button: QtWidgets.QPushButton, color: str) -> None:
        """ 结果按钮样式 """
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
        """ 结果按钮样式 """
        hex_value = color.lstrip("#")
        if len(hex_value) != 6:
            return color
        r = min(255, int(int(hex_value[0:2], 16) * factor))
        g = min(255, int(int(hex_value[2:4], 16) * factor))
        b = min(255, int(int(hex_value[4:6], 16) * factor))
        return f"#{r:02X}{g:02X}{b:02X}"

    # ------------------------------------------------------------------
    # 执行按钮状态相关
    def _refresh_start_button_state(self) -> None:
        # 开始执行按钮，有监控动作/执行未被锁定 才能使用
        # enabled = bool(self._current_actions) and not self._execution_locked
        enabled = not self._execution_locked
        self._start_monitor_btn.setEnabled(enabled)

    def _set_action_buttons_mode(self, running: bool) -> None:
        # 根据 running 展示 开始执行按钮 或者是 pass,fail,block 按钮
        self._start_monitor_btn.setVisible(not running)
        for button in self._result_buttons:
            button.setVisible(running)
        if running:
            self._fail_btn.setEnabled(True)
            self._block_btn.setEnabled(True)
            self._update_pass_button_state()
        else:
            # 重置状态
            self._awaiting_monitor_completion_for_pass = False
            for button in self._result_buttons:
                button.setEnabled(False)
            self._pass_btn.setToolTip("")
            self._refresh_start_button_state()

    def _update_pass_button_state(self) -> None:
        # 根据监控是否完成来解禁 pass 按钮
        if self._awaiting_monitor_completion_for_pass:
            self._pass_btn.setEnabled(False)
            self._pass_btn.setToolTip("监控进行中，完成所有监控动作后才能标记通过")
        else:
            self._pass_btn.setEnabled(True)
            self._pass_btn.setToolTip("")

    def _set_execution_lock(self, locked: bool) -> None:
        # 禁用/启用 筛选区域、用例树
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
            self._select_audio_logs_btn,
            self._clear_audio_logs_btn,
        ]
        for widget in widgets:
            widget.setEnabled(not locked)
        self._case_tree.setDisabled(locked)
        self._refresh_start_button_state()

    def _set_refresh_ui_state(self, refreshing: bool) -> None:
        """ 刷新按钮与状态栏提示 """
        self._refresh_in_progress = refreshing
        if refreshing:
            self._refresh_btn.setText("刷新中...")
            self._refresh_btn.setEnabled(False)
            if self._status_bar:
                self._status_bar.showMessage("正在刷新数据，请稍候...")
        else:
            self._refresh_btn.setText("刷新数据")
            self._refresh_btn.setEnabled(True)
            if self._status_bar:
                self._status_bar.clearMessage()

    def _apply_pending_audio_logs(self) -> None:
        # 判断 restore_state 是否有运行中的 audio 日志
        if self._pending_audio_logs is not None:
            self._set_audio_log_files(self._pending_audio_logs)
            self._pending_audio_logs = None
        else:
            self._update_audio_log_hint()

    def _set_audio_log_files(self, files: Sequence[str]) -> None:
        deduped: List[str] = []
        seen: set[str] = set()
        for path in files or []:
            if path is None:
                continue
            normalized = os.path.abspath(str(path))
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        self._audio_log_files = deduped
        if deduped:
            directory = os.path.dirname(deduped[-1])
            if directory:
                self._audio_log_dir_hint = directory
        self._update_audio_log_hint()

    def _update_audio_log_hint(self) -> None:
        """ 更新显示 audio 日志文件 label"""
        label = getattr(self, "_audio_log_status", None)
        if label is None:
            return
        if not self._audio_log_files:
            label.setText("未选择")
            label.setStyleSheet("color: #6B7280;")
            label.setToolTip("")
            return
        if len(self._audio_log_files) == 1:
            path = self._audio_log_files[0]
            label.setText(os.path.basename(path) or path)
            label.setStyleSheet("color: #111827;")
            label.setToolTip(path)
        else:
            display_text = " | ".join(self._audio_log_files)
            label.setText(display_text)
            label.setStyleSheet("color: #111827;")
            label.setToolTip(display_text)

    def _select_audio_logs(self) -> None:
        """ 选择audio日志文件 """
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "选择 Lab Audio 日志文件",
            self._audio_log_dir_hint,
            "Log files (*.log *.txt);;All files (*)",
        )

        if not files:
            return
        self._set_audio_log_files(files)
        self.save_state()

    def _clear_audio_logs(self) -> None:
        """ 清除audio日志 """
        if not self._audio_log_files:
            return
        self._audio_log_files = []
        self._update_audio_log_hint()
        self.save_state()

    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        # 绑定UI控件方法
        # 使用整数重载，避免 PyQt 选择字符串信号导致比较时报错
        # 部门
        self._department_combo.currentIndexChanged[int].connect(
            self._on_department_changed
        )
        # 项目
        self._project_combo.currentIndexChanged[int].connect(self._on_project_changed)
        # 计划
        self._plan_combo.currentIndexChanged[int].connect(self._on_plan_changed)
        # 模块目录
        self._directory_filter.currentIndexChanged.connect(self._apply_filters)
        # 设备
        self._device_filter.currentIndexChanged.connect(self._apply_filters)
        # 结果
        self._result_filter.currentIndexChanged.connect(self._apply_filters)
        # 用例树
        self._case_tree.currentItemChanged.connect(self._on_case_selected)
        # 开始执行
        self._start_monitor_btn.clicked.connect(self._start_monitoring)
        # 选择 audio 日志
        self._select_audio_logs_btn.clicked.connect(self._select_audio_logs)
        # 清除 audio 日志
        self._clear_audio_logs_btn.clicked.connect(self._clear_audio_logs)
        # 结果按钮
        self._pass_btn.clicked.connect(lambda: self._submit_result("pass"))
        self._fail_btn.clicked.connect(lambda: self._submit_result("fail"))
        self._block_btn.clicked.connect(lambda: self._submit_result("block"))
        # 监控信号
        self._monitoring.log_generated.connect(self._append_log)
        self._monitoring.monitoring_finished.connect(self._on_monitoring_finished)
        self._monitoring.monitoring_error.connect(self._on_monitoring_error)

    # ------------------------------------------------------------------
    def _restore_window_state(self) -> None:
        """ 窗口恢复 """
        geometry, state = self._state_store.load()
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)

    def _current_user_display_name(self) -> str:
        """ 获取登录用户名 """
        if not isinstance(self._user, dict):
            return "未登录"
        return str(self._user.get("username") or "未登录")

    def _update_window_title(self) -> None:
        """ 客户端标题 """
        base_title = f"TTS测试执行客户端 v{APP_VERSION}"
        user_name = self._current_user_display_name()
        if user_name:
            self.setWindowTitle(f"{base_title} - 当前用户: {user_name}")
        else:
            self.setWindowTitle(base_title)

    def _state_username(self) -> str:
        """ 用户名 """
        if not isinstance(self._user, dict):
            return ""
        for key in ("username", "account", "user_name"):
            value = self._user.get(key)
            if value:
                return str(value)
        return ""

    @staticmethod
    def _int_or_none(value: object) -> Optional[int]:
        """ 数据类型转换辅助 """
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _load_state_payload(self) -> Dict[str, object]:
        """ 读取保存的请求参数，用于窗口回放 """
        username = self._state_username()
        if not username:
            return {}
        try:
            with self._state_file_path.open("r", encoding="utf-8") as state_file:
                payload = json.load(state_file)
        except FileNotFoundError:
            self._logger.error("文件不存在")
            return {}
        except Exception as exc:  # pragma: no cover - 状态文件清理难以覆盖
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
        """ 上一次窗口选项的记录回放"""
        state = self._load_state_payload()
        if not state:
            self._pending_filter_state = None
            self._pending_selection = None
            self._restore_department_id = None
            self._restore_project_id = None
            self._restore_plan_id = None
            self._restore_start_clicked = False
            self._pending_audio_logs = None
            return
        # 上一次的筛选项
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
        # 上一次选中的用例树节点
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
        # 是否在执行中
        self._restore_start_clicked = bool(state.get("start_clicked"))
        # 是否有 audio 日志
        audio_logs = state.get("audio_logs")
        if isinstance(audio_logs, list):
            self._pending_audio_logs = [str(path) for path in audio_logs if path]
        else:
            self._pending_audio_logs = None

    def save_state(self) -> None:
        """ 保存当前用户的所有筛选条件，是否在执行 """
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
        state["audio_logs"] = list(self._audio_log_files)

        selection = self._selection_key(self._current_entry)
        if selection:
            state["selection"] = [selection[0], selection[1], selection[2], selection[3]]

        try:
            self._state_file_path.parent.mkdir(parents=True, exist_ok=True)
            with self._state_file_path.open("w", encoding="utf-8") as state_file:
                json.dump(state, state_file, ensure_ascii=False, indent=2)
        except OSError as exc:  # pragma: no cover - 文件持久化失败不影响核心流程
            self._logger.warning("保存状态失败: %s", exc)

    # ------------------------------------------------------------------
    def _append_log(self, message: str) -> None:
        """ 追加日志信息 """
        self._log_view.appendPlainText(message)

    def _on_monitoring_finished(self) -> None:
        """ 监控完成，解禁pass按钮 """
        self._append_log("监控已结束")
        if self._awaiting_monitor_completion_for_pass:
            self._awaiting_monitor_completion_for_pass = False
            if self._pass_btn.isVisible():
                self._update_pass_button_state()
        self.save_state()

    def _on_monitoring_error(self, message: str) -> None:
        """ 监控错误处理 """
        QtWidgets.QMessageBox.critical(self, "监控失败", message)
        self._set_action_buttons_mode(False)
        self._set_execution_lock(False)
        self.save_state()

    # ------------------------------------------------------------------
    def _clear_project_combo(self) -> None:
        """  清空项目选项 """
        with QtCore.QSignalBlocker(self._project_combo):
            self._project_combo.clear()
            self._project_combo.addItem("请选择项目", None)
            self._project_combo.setCurrentIndex(0)
        self._project_combo.setEnabled(bool(self._projects))

    def _clear_plan_combo(self) -> None:
        """  清空计划选项 """
        with QtCore.QSignalBlocker(self._plan_combo):
            self._plan_combo.clear()
            self._plan_combo.addItem("请选择计划", None)
            self._plan_combo.setCurrentIndex(0)
        self._plan_combo.setEnabled(bool(self._plans))

    def _clear_project_and_plan(self) -> None:
        self._clear_project_combo()
        self._clear_plan_combo()

    def _populate_project_combo(self) -> None:
        """ 选择项目 """
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
        """ 选择计划 """
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
    def _load_departments(self) -> bool:
        """ 获取部门信息 """
        success = False
        try:
            self._departments = self._api.get_departments()
        except AuthenticationError:
            QtWidgets.QMessageBox.critical(self, "未授权", "凭据已失效，请重新登录。")
            self.close()
            return False
        except ClientError as exc:
            QtWidgets.QMessageBox.warning(self, "加载失败", str(exc))
            return False
        with QtCore.QSignalBlocker(self._department_combo):
            self._department_combo.clear()
            self._department_combo.addItem("请选择部门", None)
            for dept in self._departments:
                self._department_combo.addItem(dept.name, dept.id)

        self._department_combo.setEnabled(bool(self._departments))
        target_index = 0
        # 如果有保存部门ID，恢复上一次的选择
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
        success = True
        return success

    def _on_department_changed(self, _index: object) -> None:
        """ 联动筛选框，部门改变时重新获取项目 """
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
        """ 联动筛选框，项目改变时重新获取计划 """
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
        """ 联动筛选框，计划改变时重新获取用例 """
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
        """ 设备过滤筛选 """
        devices: Dict[int, str] = {}
        # 从所有case中提取设备ID和名称
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
        for device_id, label in sorted(devices.items(), key=lambda item: item[1]):
            self._device_filter.addItem(label, device_id)
        self._device_filter.setEnabled(True)
        self._device_filter.blockSignals(False)
        self._device_filter.setCurrentIndex(0)

    def _refresh_directory_filter(self) -> None:
        """ 模块目录过滤筛选 """
        directories: List[str] = []
        seen: set[str] = set()
        # 从所有用例中提取模块目录
        for case in self._cases:
            directory = self._normalize_directory(case.group_path)
            if directory not in seen:
                seen.add(directory)
                directories.append(directory)
        directories.sort()
        self._directory_filter.blockSignals(True)
        self._directory_filter.clear()
        self._directory_filter.addItem("请选择模块目录", None)
        for directory in directories:
            self._directory_filter.addItem(directory, directory)
        self._directory_filter.blockSignals(False)
        self._directory_filter.setCurrentIndex(0)

    def _set_combobox_current_data(
        self, combo: QtWidgets.QComboBox, value: object
    ) -> None:
        """ 工具方法，根据 item 的 itemData 设定当前 index。 """
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
        """ 恢复目录/设备/结果三个组合框的当前值。 """
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
        """ 格式话设备显示 """
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
        """ 获取指定机型最新执行结果 """
        candidates = [
            execution
            for execution in executions
            if (execution.device_model_id or None) == device_id
        ]
        if not candidates:
            return None
        # executed_at最大的就是最新的结果
        return max(candidates, key=lambda item: item.executed_at or "")

    def _build_case_entries(self, case: PlanCase) -> List[CaseDisplayEntry]:
        """
        核心：一个 case 可能对应多个“执行设备”的行（一个 case + 多机型，树里每个 entry 一行）
        逻辑：
        先用 case.device_models 生成 entries（每个设备一条）
        再补充那些虽然不在 device_models，但 execution_results 里出现过的“额外设备”
        如果完全没设备信息，就生成一个 “通用” entry（is_general=True）。
        """
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
        """ 应用筛选：目录、设备、结果过滤用例 """
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
                if device_value is not None:
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
        """ 更新计划进度统计 """
        detail = self._plan_detail
        if not detail:
            self._plan_period_label.setText("执行时间：—")
            self._plan_tester_label.setText("执行人员：—")
            self._plan_progress_label.setText("执行进度：—")
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
        self._plan_period_label.setText(f"执行时间：{period}")
        self._plan_tester_label.setText(f"执行人员：{testers}")

        stats_values = {
            "total": 0,
            "executed": 0,
            "pass": 0,
            "fail": 0,
            "block": 0,
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
                }
            )

        executed = stats_values["executed"]
        total = stats_values["total"]
        pass_count = stats_values["pass"]
        fail_count = stats_values["fail"]
        block_count = stats_values["block"]
        self._plan_progress_label.setText(
            f"执行进度：{executed}/{total} (通过 {pass_count} | 失败 {fail_count} | 阻塞 {block_count})"
        )

    def _refresh_case_tree(self) -> None:
        """ 刷新节点树 """
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
        """ 选择某个节点 """
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
        """ 模块分组筛选 """
        if not path:
            return "未分组"
        # 根目录root不显示
        parts = [part.strip() for part in str(path).split("/") if part and part.lower() != "root"]
        return "/".join(parts) if parts else "未分组"

    def _directory_tokens(self, path: Optional[str]) -> List[str]:
        """ 拆成 tokens 用于构建树的层级 """
        normalized = self._normalize_directory(path)
        if normalized == "未分组":
            return ["未分组"]
        return normalized.split("/")

    def _status_color(self, entry: CaseDisplayEntry) -> Optional[str]:
        """ 用例状态颜色设置 """
        result = entry.result_value()
        if result == "pass":
            return PASS_SYMBOL_COLOR
        if result == "fail":
            return FAIL_SYMBOL_COLOR
        if result in {"blocked", "block"}:
            return BLOCK_SYMBOL_COLOR
        return None

    def _status_icon(self, entry: CaseDisplayEntry) -> Optional[QtGui.QIcon]:
        """ 用例状态图标 """
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
        """ 创建用例状态图标 """
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
        """ 选中用例 key / 展示文本 / 用例选中事件，记录元组 """
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
        """ 展示标题 + 机型 + 关键字 """
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
        # 如果 current 没有 entry 数据,保持 previous 选中，否则清空详情
        if not entry:
            if previous and previous.data(0, QtCore.Qt.UserRole):
                self._case_tree.setCurrentItem(previous)
            else:
                self._update_case_detail(None)
            return
        # 记录选中的ID，并更新用例详情。根据是否点击来决定调用开始执行
        case = entry.case
        self._logger.info("选中用例: %s (ID: %s)", case.title, case.case_id)
        self._update_case_detail(entry)
        self.save_state()
        if self._restore_start_clicked:
            self._restore_start_clicked = False
            self._auto_start_in_progress = True
            QtCore.QTimer.singleShot(0, self._start_monitoring)

    def _update_case_detail(self, entry: Optional[CaseDisplayEntry]) -> None:
        """ 用例详情展示 """
        self._current_entry = entry
        case = entry.case if entry else None
        self._current_case = case
        self._current_actions = []
        self._current_device_id = entry.device_model_id if entry else None
        self._current_plan_device_model_id = entry.plan_device_model_id if entry else None
        self._recording_requirement_minutes = None
        if not self._execution_locked:
            self._set_action_buttons_mode(False)
        if not case:
            self._title_label.setText("请选择一条用例")
            self._title_icon_label.clear()
            self._title_icon_label.setVisible(False)
            self._precondition_label.setText("前置条件: 暂无前置条件")
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

        preconditions = (case.preconditions or "").strip() or "暂无前置条件"
        self._precondition_label.setText(f"前置条件: {preconditions}")

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
            # 解析用例关键字
            actions = parse_keywords(case.keyword_actions())
        except ValidationError as exc:
            self._keyword_error.setText(str(exc))
            self._keyword_error.setVisible(True)
            self._current_actions = []
        else:
            self._keyword_error.setVisible(False)
            self._current_actions = actions
            self._recording_requirement_minutes = recording_requirement_minutes(actions)
            for action in actions:
                self._keyword_list.addItem(f"{action.display_label()} -> {action.amount}")
        self._refresh_start_button_state()
        self._log_view.clear()
        attachment_hints: List[str] = []
        if require_attachment(self._current_actions):
            attachment_hints.append("此用例包含时间监控，提交 PASS/FAIL 必须上传附件")
        if self._recording_requirement_minutes:
            attachment_hints.append(
                f"提交通过需上传录音（时长不少于 {self._recording_requirement_minutes:g} 分钟）"
            )
        self._attachment_hint.setText("\n".join(attachment_hints))

    # ------------------------------------------------------------------
    def _requires_audio_logs(self) -> bool:
        # 判断是否有 audio 动作
        for action in self._current_actions:
            if action.normalized_name in AUDIO_EVENT_KEYWORDS:
                return True
        return False

    # ------------------------------------------------------------------
    def _requires_text_logs(self) ->list:

        for action in self._current_actions:
            if 'log' in action.normalized_name:
                return [True, action.normalized_name]
        return [False,'None']

    def _is_recording_action(self, action: MonitoringAction) -> bool:
        return action.normalized_name == "录音"

    # ------------------------------------------------------------------
    def _start_monitoring(self) -> None:
        """ 开始执行 """
        try:
            if not self._current_case:
                QtWidgets.QMessageBox.information(self, "未选择", "请先选择用例")
                return
            # 需求要求不拦截，先注释掉
            # if not self._current_actions:
            #     QtWidgets.QMessageBox.warning(self, "关键字错误", "关键字无法解析，无法启动监控")
            #     return
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
            monitoring_actions = [
                action for action in self._current_actions if not self._is_recording_action(action)
            ]
            self._awaiting_monitor_completion_for_pass = bool(monitoring_actions)
            start_time = dt.datetime.now(dt.timezone.utc).isoformat()
            if self._current_case and self._current_case.id:
                self._case_execution_start_times[int(self._current_case.id)] = start_time
            require_audio_logs = self._requires_audio_logs()
            if require_audio_logs and not self._audio_log_files:
                QtWidgets.QMessageBox.warning(
                    self,
                    "缺少日志文件",
                    "该用例包含 Lab Audio 监控，请先选择至少一个串口日志文件。",
                )
                return
            require_text_logs,log_name = self._requires_text_logs()
            if require_text_logs and not self._audio_log_files:
                QtWidgets.QMessageBox.warning(
                    self,
                    "缺少日志文件",
                    f"该用例包含 {log_name} 监控，请先选择至少一个串口日志文件。",
                )
                return
            if monitoring_actions:
                self._monitoring.start(
                    self._current_case.case_id,
                    monitoring_actions,
                    start_time,
                    audio_log_files=self._audio_log_files,
                )
                self._append_log("监控已启动")
                self._logger.info("已启动监控: 用例 %s", self._current_case.case_id)
            else:
                self._append_log("当前用例没有匹配到任何监控动作，可以直接记录结果。")
            self._set_action_buttons_mode(True)
            self._set_execution_lock(True)
            self.save_state()
        finally:
            self._auto_start_in_progress = False

    def _existing_result_label(self, entry: CaseDisplayEntry) -> Optional[str]:
        """ 判断用例是否已有结果 """
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
        """ 提交设备 """
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

    def _validate_recording_attachments(
        self,
        attachments: Sequence[Dict[str, str]],
        required_minutes: Optional[float],
    ) -> bool:
        """Ensure at least one attachment meets the recording duration requirement."""

        if required_minutes is None or required_minutes <= 0:
            return True
        if not attachments:
            QtWidgets.QMessageBox.warning(
                self,
                "缺少录音",
                f"提交通过需要上传时长不少于 {required_minutes:g} 分钟的录音文件。",
            )
            return False

        required_seconds = required_minutes * 60
        errors: List[str] = []
        for payload in attachments:
            path = payload.get("local_path")
            if not path:
                continue
            try:
                duration = get_audio_duration_seconds(path)
            except ValueError as exc:
                errors.append(f"{os.path.basename(path)}: {exc}")
                continue
            if duration >= required_seconds:
                return True
            errors.append(
                f"{os.path.basename(path)} 时长 {duration / 60:.1f} 分钟，不足 {required_minutes:g} 分钟"
            )

        message = "\n".join(errors) if errors else "请上传可识别的录音文件。"
        QtWidgets.QMessageBox.warning(self, "录音不符合要求", message)
        return False

    def _submit_result(self, result: str) -> None:
        """ 更新结果 """
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
        recording_minutes = recording_requirement_minutes(actions)
        recording_required_for_result = (
            result == "pass" and recording_minutes is not None and recording_minutes > 0
        )
        need_attachment = (
            (result in {"pass", "fail"} and require_attachment(actions))
            or recording_required_for_result
        )
        device_model_id, plan_device_model_id, device_hint = self._resolve_submission_device(
            self._current_entry
        )
        dialog = ResultDialog(
            self,
            {"pass": "通过", "fail": "失败", "blocked": "阻塞"}.get(result, result.upper()),
            self._case_display_text(self._current_entry),
            device_hint,
            need_attachment,
            recording_requirement=recording_minutes if recording_required_for_result else None,
        )
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        plan_id = self._int_or_none(self._plan_combo.currentData())
        plan_case_id = self._current_case.id
        if plan_id is None or plan_case_id is None:
            QtWidgets.QMessageBox.warning(self, "提交失败", "当前计划信息缺失，请刷新后重试。")
            return
        plan_case_key = int(plan_case_id)
        remark = dialog.remark()
        failure_reason = dialog.failure_reason()
        bug_ref = dialog.bug_ref()
        attachments_with_local = dialog.attachments()
        if recording_required_for_result:
            if not self._validate_recording_attachments(attachments_with_local, recording_minutes):
                return
        attachments = [
            {k: v for k, v in payload.items() if k != "local_path"}
            for payload in attachments_with_local
        ]
        if self._monitoring.is_running():
            self._monitoring.stop()
            self._append_log("监控停止请求已发送")
        self._awaiting_monitor_completion_for_pass = False
        execution_start_time = self._case_execution_start_times.get(plan_case_key)
        execution_end_time = dt.datetime.now(dt.timezone.utc).isoformat()
        if not execution_start_time:
            execution_start_time = execution_end_time
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
                execution_start_time=execution_start_time,
                execution_end_time=execution_end_time,
            )
        except (ClientError, ValueError) as exc:
            QtWidgets.QMessageBox.warning(self, "提交失败", str(exc))
            return
        self._case_execution_start_times.pop(plan_case_key, None)
        self._monitoring.discard_session_state()
        self._logger.info(
            "提交结果: 用例 %s (结果=%s, 设备=%s, 计划设备=%s)",
            self._current_case.case_id,
            result,
            device_model_id,
            plan_device_model_id,
        )
        QtWidgets.QMessageBox.information(self, "成功", "结果已提交")
        self._set_execution_lock(False)
        self.save_state()
        self._reload_current_plan()
        # 强制等待保证稳定性
        time.sleep(0.2)
        self._set_action_buttons_mode(False)

    def _reload_current_plan(self) -> None:
        """ 计划重载 """
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

    def _refresh_all_data(self) -> None:
        """ 手动刷新部门/项目/计划及用例数据 """
        if self._refresh_in_progress:
            return
        self._set_refresh_ui_state(True)
        refreshed = False
        self._pending_selection = self._selection_key(self._current_entry)
        self._pending_filter_state = {
            "directory": self._directory_filter.currentData(),
            "device": self._device_filter.currentData(),
            "result": self._result_filter.currentData(),
        }
        self._restore_department_id = self._int_or_none(self._department_combo.currentData())
        self._restore_project_id = self._int_or_none(self._project_combo.currentData())
        self._restore_plan_id = self._int_or_none(self._plan_combo.currentData())
        try:
            refreshed = bool(self._load_departments())
        finally:
            self._set_refresh_ui_state(False)
        if refreshed:
            if self._status_bar:
                self._status_bar.showMessage("数据已刷新", 5000)
            QtWidgets.QMessageBox.information(self, "刷新完成", "最新的部门、项目、计划及用例数据已更新。")
        else:
            if self._status_bar:
                self._status_bar.showMessage("刷新失败，请稍后重试", 5000)

    # ------------------------------------------------------------------
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """ 关闭窗口并记录状态 """
        # noqa: N802 - Qt 事件钩子名称固定
        self.save_state()
        geometry = self.saveGeometry()
        state = self.saveState()
        self._state_store.save(geometry, state)
        if self._monitoring.is_running():
            self._monitoring.stop()
        if self._download_dialog:
            self._download_dialog.close()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # OTA 更新流程
    def _start_update_check(self) -> None:
        if self._update_check_thread and self._update_check_thread.is_alive():
            return
        thread = threading.Thread(
            target=self._run_update_check,
            name="UpdateCheck",
            daemon=True,
        )
        self._update_check_thread = thread
        thread.start()

    def _run_update_check(self) -> None:
        try:
            info = self._updates.check_for_updates()
        except NetworkError as exc:
            self._logger.info("OTA 检查失败: %s", exc)
            return
        if not info or not info.version:
            return
        if not self._updates.is_update_newer(info.version):
            return
        self._update_prompt_signal.emit(info)

    def _prompt_update(self, info: UpdateInfo) -> None:
        if self._pending_update_info and self._pending_update_info.version == info.version:
            return
        notes = info.release_notes.strip() if info.release_notes else "检测到新版本，建议立即升级。"
        message = f"检测到新版本 {info.version}。\n\n{notes}\n\n是否立即下载并安装？"
        reply = QtWidgets.QMessageBox.question(
            self,
            "发现新版本",
            message,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            self._logger.info("用户暂缓升级到版本 %s", info.version)
            return
        self._begin_update_download(info)

    def _begin_update_download(self, info: UpdateInfo) -> None:
        self._pending_update_info = info
        dialog = QtWidgets.QProgressDialog("正在下载更新...", None, 0, 100, self)
        dialog.setWindowTitle("下载更新")
        dialog.setCancelButton(None)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setModal(True)
        dialog.setValue(0)
        dialog.show()
        self._download_dialog = dialog

        thread = threading.Thread(
            target=self._download_update_worker,
            args=(info,),
            name="UpdateDownload",
            daemon=True,
        )
        self._update_download_thread = thread
        thread.start()

    def _download_update_worker(self, info: UpdateInfo) -> None:
        def report_progress(downloaded: int, total: Optional[int]) -> None:
            self._update_progress_signal.emit(downloaded, total)

        try:
            staged_path = self._updates.stage_update(info, report_progress)
        except (NetworkError, UpdateError) as exc:
            self._update_error_signal.emit(str(exc))
            return
        self._update_ready_signal.emit(info, staged_path)

    def _update_download_progress(self, downloaded: int, total: Optional[int]) -> None:
        dialog = self._download_dialog
        if dialog is None:
            return
        if not total or total <= 0:
            dialog.setRange(0, 0)
            dialog.setLabelText(f"正在下载更新（已接收 {self._format_size(downloaded)}）...")
            return
        dialog.setRange(0, 100)
        percent = max(0, min(100, int(downloaded * 100 / total)))
        dialog.setValue(percent)
        dialog.setLabelText(f"正在下载更新（{percent}%）")

    def _on_update_ready(self, info: UpdateInfo, staged_path: Path) -> None:
        if self._download_dialog:
            self._download_dialog.close()
            self._download_dialog = None
        self._staged_update_path = staged_path
        if not self._updates.supports_in_place_update:
            QtWidgets.QMessageBox.information(
                self,
                "更新已下载",
                f"版本 {info.version} 已下载至:\n{staged_path}\n\n当前运行于开发环境，请手动替换目录完成升级。",
            )
            return
        reply = QtWidgets.QMessageBox.question(
            self,
            "安装更新",
            f"版本 {info.version} 已准备好安装，客户端需要重启以完成升级。是否现在重启？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            self._logger.info("用户推迟安装版本 %s", info.version)
            return
        self._perform_update_installation(staged_path)

    def _perform_update_installation(self, staged_path: Path) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "即将重启",
            "客户端将退出并自动完成升级，稍后请重新登录继续执行。",
        )
        self._launch_installer_and_close(staged_path)

    def _launch_installer_and_close(self, staged_path: Path) -> None:
        try:
            self._updates.launch_installer(staged_path, os.getpid())
        except UpdateError as exc:
            self._handle_update_error(str(exc))
            return
        self._logger.info("已启动更新安装，将关闭客户端以释放文件锁")
        self.close()

    def _handle_update_error(self, message: str) -> None:
        if self._download_dialog:
            self._download_dialog.close()
            self._download_dialog = None
        self._pending_update_info = None
        self._staged_update_path = None
        QtWidgets.QMessageBox.warning(self, "更新失败", message)

    def _format_size(self, value: int) -> str:
        units = ["B", "KB", "MB", "GB"]
        size = float(max(value, 0))
        for unit in units:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}TB"
