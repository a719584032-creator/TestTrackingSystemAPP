"""Main window hosting the execution workflow."""
from __future__ import annotations

import datetime as dt
import logging
import os
from typing import Dict, List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from ..core.api_client import ApiClient, encode_attachment
from ..core.exceptions import AuthenticationError, ClientError, ValidationError
from ..core.models import Department, PlanCase, PlanDetail, Project, TestPlan
from ..core.monitor_parser import MonitoringAction, parse_keywords, require_attachment
from ..core.settings import WindowStateStore
from ..monitoring.manager import MonitoringManager


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
        self._filtered_cases: List[PlanCase] = []
        self._current_case: Optional[PlanCase] = None
        self._current_actions: List[MonitoringAction] = []
        self._attachments: List[Dict[str, str]] = []
        self._plan_detail: Optional[PlanDetail] = None

        self.setWindowTitle("TTS 测试执行客户端")
        self.resize(1280, 720)
        self._build_ui()
        self._connect_signals()
        self._restore_window_state()

        QtCore.QTimer.singleShot(100, self._load_departments)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        toolbar = QtWidgets.QToolBar()
        toolbar.setIconSize(QtCore.QSize(20, 20))
        toolbar.setMovable(False)
        toolbar.addWidget(QtWidgets.QLabel("部门:"))
        self._department_combo = QtWidgets.QComboBox()
        self._department_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self._department_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self._department_combo.setMinimumContentsLength(8)
        toolbar.addWidget(self._department_combo)
        toolbar.addSeparator()
        toolbar.addWidget(QtWidgets.QLabel("项目:"))
        self._project_combo = QtWidgets.QComboBox()
        self._project_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self._project_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self._project_combo.setMinimumContentsLength(8)
        toolbar.addWidget(self._project_combo)
        toolbar.addSeparator()
        toolbar.addWidget(QtWidgets.QLabel("计划:"))
        self._plan_combo = QtWidgets.QComboBox()
        self._plan_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self._plan_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self._plan_combo.setMinimumContentsLength(8)
        toolbar.addWidget(self._plan_combo)
        toolbar.addSeparator()
        toolbar.addWidget(QtWidgets.QLabel("机型:"))
        self._device_filter = QtWidgets.QComboBox()
        self._device_filter.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self._device_filter.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self._device_filter.setMinimumContentsLength(8)
        toolbar.addWidget(self._device_filter)
        toolbar.addSeparator()
        refresh_action = QtWidgets.QAction("刷新", self)
        refresh_action.triggered.connect(self._reload_current_plan)
        toolbar.addAction(refresh_action)
        self.addToolBar(toolbar)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root_layout = QtWidgets.QHBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        # Left: table and filters
        left_panel = QtWidgets.QVBoxLayout()
        left_panel.setSpacing(10)

        filter_box = QtWidgets.QGroupBox("筛选")
        filter_layout = QtWidgets.QGridLayout(filter_box)
        filter_layout.setHorizontalSpacing(12)
        filter_layout.addWidget(QtWidgets.QLabel("目录"), 0, 0)
        self._directory_filter = QtWidgets.QComboBox()
        self._directory_filter.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self._directory_filter.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self._directory_filter.setMinimumContentsLength(8)
        self._directory_filter.addItem("全部", None)
        filter_layout.addWidget(self._directory_filter, 0, 1)

        filter_layout.addWidget(QtWidgets.QLabel("结果"), 1, 0)
        self._result_filter = QtWidgets.QComboBox()
        self._result_filter.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self._result_filter.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self._result_filter.setMinimumContentsLength(8)
        self._result_filter.addItem("全部", None)
        for value in ["pass", "fail", "blocked", "pending", "skipped"]:
            self._result_filter.addItem(value, value)
        filter_layout.addWidget(self._result_filter, 1, 1)
        filter_layout.setColumnStretch(1, 1)

        left_panel.addWidget(filter_box)

        self._case_tree = QtWidgets.QTreeWidget()
        self._case_tree.setHeaderLabels(["用例标题"])
        self._case_tree.header().setStretchLastSection(True)
        self._case_tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._case_tree.setIndentation(18)
        self._case_tree.setUniformRowHeights(True)
        left_panel.addWidget(self._case_tree, stretch=1)

        root_layout.addLayout(left_panel, stretch=3)

        # Right: detail and monitoring panel
        detail_panel = QtWidgets.QVBoxLayout()
        detail_panel.setSpacing(10)

        plan_box = QtWidgets.QGroupBox("计划概览")
        plan_layout = QtWidgets.QGridLayout(plan_box)
        plan_layout.setVerticalSpacing(6)
        plan_layout.addWidget(QtWidgets.QLabel("状态"), 0, 0)
        self._plan_status_label = QtWidgets.QLabel("-")
        plan_layout.addWidget(self._plan_status_label, 0, 1)
        plan_layout.addWidget(QtWidgets.QLabel("时间周期"), 1, 0)
        self._plan_period_label = QtWidgets.QLabel("-")
        self._plan_period_label.setWordWrap(True)
        plan_layout.addWidget(self._plan_period_label, 1, 1)
        plan_layout.addWidget(QtWidgets.QLabel("测试人员"), 2, 0)
        self._plan_tester_label = QtWidgets.QLabel("-")
        self._plan_tester_label.setWordWrap(True)
        plan_layout.addWidget(self._plan_tester_label, 2, 1)
        plan_layout.addWidget(QtWidgets.QLabel("执行统计"), 3, 0)
        self._plan_stats_label = QtWidgets.QLabel("-")
        self._plan_stats_label.setWordWrap(True)
        plan_layout.addWidget(self._plan_stats_label, 3, 1)
        plan_layout.setColumnStretch(1, 1)
        detail_panel.addWidget(plan_box)

        self._title_label = QtWidgets.QLabel("请选择一条用例")
        self._title_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        detail_panel.addWidget(self._title_label)

        info_layout = QtWidgets.QGridLayout()
        self._priority_label = QtWidgets.QLabel("-")
        self._result_label = QtWidgets.QLabel("-")
        self._directory_label = QtWidgets.QLabel("-")
        info_layout.addWidget(QtWidgets.QLabel("优先级"), 0, 0)
        info_layout.addWidget(self._priority_label, 0, 1)
        info_layout.addWidget(QtWidgets.QLabel("最新结果"), 0, 2)
        info_layout.addWidget(self._result_label, 0, 3)
        info_layout.addWidget(QtWidgets.QLabel("目录"), 1, 0)
        info_layout.addWidget(self._directory_label, 1, 1, 1, 3)
        detail_panel.addLayout(info_layout)

        keyword_box = QtWidgets.QGroupBox("监控动作")
        keyword_layout = QtWidgets.QVBoxLayout(keyword_box)
        self._keyword_list = QtWidgets.QListWidget()
        keyword_layout.addWidget(self._keyword_list)
        self._keyword_error = QtWidgets.QLabel()
        self._keyword_error.setStyleSheet("color: #dc2626;")
        self._keyword_error.setVisible(False)
        keyword_layout.addWidget(self._keyword_error)
        detail_panel.addWidget(keyword_box)

        monitoring_box = QtWidgets.QGroupBox("监控执行")
        monitoring_layout = QtWidgets.QVBoxLayout(monitoring_box)
        monitor_button_row = QtWidgets.QHBoxLayout()
        self._start_monitor_btn = QtWidgets.QPushButton("开始监控")
        self._stop_monitor_btn = QtWidgets.QPushButton("停止")
        self._stop_monitor_btn.setEnabled(False)
        monitor_button_row.addWidget(self._start_monitor_btn)
        monitor_button_row.addWidget(self._stop_monitor_btn)
        monitoring_layout.addLayout(monitor_button_row)

        self._log_view = QtWidgets.QPlainTextEdit()
        self._log_view.setReadOnly(True)
        monitoring_layout.addWidget(self._log_view)
        detail_panel.addWidget(monitoring_box, stretch=1)

        execution_box = QtWidgets.QGroupBox("结果记录")
        execution_layout = QtWidgets.QGridLayout(execution_box)
        execution_layout.addWidget(QtWidgets.QLabel("备注"), 0, 0)
        self._remark_edit = QtWidgets.QPlainTextEdit()
        execution_layout.addWidget(self._remark_edit, 0, 1, 1, 3)

        execution_layout.addWidget(QtWidgets.QLabel("失败原因"), 1, 0)
        self._failure_edit = QtWidgets.QLineEdit()
        execution_layout.addWidget(self._failure_edit, 1, 1, 1, 3)

        execution_layout.addWidget(QtWidgets.QLabel("缺陷编号"), 2, 0)
        self._bug_edit = QtWidgets.QLineEdit()
        execution_layout.addWidget(self._bug_edit, 2, 1)

        execution_layout.addWidget(QtWidgets.QLabel("设备"), 2, 2)
        self._device_combo = QtWidgets.QComboBox()
        execution_layout.addWidget(self._device_combo, 2, 3)

        attachment_row = QtWidgets.QHBoxLayout()
        self._attachment_list = QtWidgets.QListWidget()
        attachment_row.addWidget(self._attachment_list, stretch=1)
        attach_controls = QtWidgets.QVBoxLayout()
        self._add_attachment_btn = QtWidgets.QPushButton("添加图片")
        self._remove_attachment_btn = QtWidgets.QPushButton("移除")
        attach_controls.addWidget(self._add_attachment_btn)
        attach_controls.addWidget(self._remove_attachment_btn)
        attach_controls.addStretch()
        attachment_row.addLayout(attach_controls)
        execution_layout.addLayout(attachment_row, 3, 0, 1, 4)

        button_row = QtWidgets.QHBoxLayout()
        self._pass_btn = QtWidgets.QPushButton("标记通过")
        self._fail_btn = QtWidgets.QPushButton("标记失败")
        self._block_btn = QtWidgets.QPushButton("标记阻塞")
        button_row.addWidget(self._pass_btn)
        button_row.addWidget(self._fail_btn)
        button_row.addWidget(self._block_btn)
        execution_layout.addLayout(button_row, 4, 0, 1, 4)

        self._attachment_hint = QtWidgets.QLabel("")
        self._attachment_hint.setStyleSheet("color: #2563eb;")
        execution_layout.addWidget(self._attachment_hint, 5, 0, 1, 4)

        detail_panel.addWidget(execution_box)
        root_layout.addLayout(detail_panel, stretch=4)

        # Status bar
        status = QtWidgets.QStatusBar()
        self.setStatusBar(status)
        user_name = self._user.get("real_name") or self._user.get("username", "未登录")
        status.showMessage(f"当前用户: {user_name}")

    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        self._department_combo.currentIndexChanged.connect(self._on_department_changed)
        self._project_combo.currentIndexChanged.connect(self._on_project_changed)
        self._plan_combo.currentIndexChanged.connect(self._on_plan_changed)
        self._directory_filter.currentIndexChanged.connect(self._apply_filters)
        self._device_filter.currentIndexChanged.connect(self._apply_filters)
        self._result_filter.currentIndexChanged.connect(self._apply_filters)
        self._case_tree.currentItemChanged.connect(self._on_case_selected)

        self._start_monitor_btn.clicked.connect(self._start_monitoring)
        self._stop_monitor_btn.clicked.connect(self._stop_monitoring)

        self._add_attachment_btn.clicked.connect(self._add_attachment)
        self._remove_attachment_btn.clicked.connect(self._remove_attachment)

        self._pass_btn.clicked.connect(lambda: self._submit_result("pass"))
        self._fail_btn.clicked.connect(lambda: self._submit_result("fail"))
        self._block_btn.clicked.connect(lambda: self._submit_result("blocked"))

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

    # ------------------------------------------------------------------
    def _append_log(self, message: str) -> None:
        self._log_view.appendPlainText(message)

    def _on_monitoring_finished(self) -> None:
        self._append_log("监控已结束")
        self._start_monitor_btn.setEnabled(True)
        self._stop_monitor_btn.setEnabled(False)

    def _on_monitoring_error(self, message: str) -> None:
        QtWidgets.QMessageBox.critical(self, "监控失败", message)
        self._on_monitoring_finished()

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
        self._department_combo.blockSignals(True)
        self._department_combo.clear()
        for dept in self._departments:
            self._department_combo.addItem(dept.name, dept.id)
        self._department_combo.blockSignals(False)
        if self._departments:
            self._department_combo.setCurrentIndex(0)
            self._on_department_changed(0)

    def _on_department_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._departments):
            return
        dept_id = self._department_combo.currentData()
        try:
            self._projects = self._api.get_projects(int(dept_id))
        except ClientError as exc:
            QtWidgets.QMessageBox.warning(self, "加载项目失败", str(exc))
            return
        self._project_combo.blockSignals(True)
        self._project_combo.clear()
        for project in self._projects:
            self._project_combo.addItem(project.name, project.id)
        self._project_combo.blockSignals(False)
        if self._projects:
            self._project_combo.setCurrentIndex(0)
            self._on_project_changed(0)

    def _on_project_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._projects):
            return
        project_id = self._project_combo.currentData()
        dept_id = self._department_combo.currentData()
        try:
            self._plans = self._api.get_test_plans(int(dept_id), int(project_id))
        except ClientError as exc:
            QtWidgets.QMessageBox.warning(self, "加载计划失败", str(exc))
            return
        self._plan_combo.blockSignals(True)
        self._plan_combo.clear()
        for plan in self._plans:
            self._plan_combo.addItem(plan.name, plan.id)
        self._plan_combo.blockSignals(False)
        if self._plans:
            self._plan_combo.setCurrentIndex(0)
            self._on_plan_changed(0)

    def _on_plan_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._plans):
            self._cases = []
            self._plan_detail = None
            self._update_plan_summary()
            self._refresh_directory_filter()
            self._refresh_device_filter()
            self._filtered_cases = []
            self._refresh_case_tree()
            return

        plan = self._plans[index]
        plan_id = int(self._plan_combo.currentData())
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
        self._apply_filters()

    def _refresh_device_filter(self) -> None:
        devices = sorted(
            {
                model.name or model.model_code or str(model.id)
                for case in self._cases
                for model in case.device_models
                if model.name or model.model_code
            }
        )
        self._device_filter.blockSignals(True)
        self._device_filter.clear()
        self._device_filter.addItem("请选择机型", None)
        if devices:
            for name in devices:
                self._device_filter.addItem(name, name)
            self._device_filter.setEnabled(True)
        else:
            self._device_filter.setItemText(0, "暂无可选机型")
            self._device_filter.setEnabled(False)
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

    def _apply_filters(self) -> None:
        directory_value = self._directory_filter.currentData()
        device_value = self._device_filter.currentData()
        result_value = self._result_filter.currentData()

        if device_value is None:
            self._filtered_cases = []
            self._refresh_case_tree()
            return

        def matches(case: PlanCase) -> bool:
            if directory_value and self._normalize_directory(case.group_path) != directory_value:
                return False
            if device_value:
                names = {
                    model.name or model.model_code or str(model.id)
                    for model in case.device_models
                    if model.name or model.model_code or model.id
                }
                if device_value not in names:
                    return False
            if result_value:
                latest = (case.latest_result or "pending").lower()
                if latest != result_value:
                    return False
            return True

        self._filtered_cases = [case for case in self._cases if matches(case)]
        self._logger.info("筛选后用例数量: %d", len(self._filtered_cases))
        self._refresh_case_tree()

    def _update_plan_summary(self) -> None:
        detail = self._plan_detail
        if not detail:
            self._plan_status_label.setText("-")
            self._plan_period_label.setText("-")
            self._plan_tester_label.setText("-")
            self._plan_stats_label.setText("-")
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
        if detail.statistics:
            stats = detail.statistics
            stats_parts = [
                f"总数 {stats.total_results}",
                f"已执行 {stats.executed_results}",
                f"通过 {stats.passed}",
                f"失败 {stats.failed}",
                f"阻塞 {stats.blocked}",
                f"未执行 {stats.not_run}",
            ]
            if stats.skipped:
                stats_parts.append(f"跳过 {stats.skipped}")
            stats_text = " · ".join(stats_parts)
        else:
            stats_text = "暂无统计数据"

        self._plan_status_label.setText(detail.status or "-")
        self._plan_period_label.setText(period)
        self._plan_tester_label.setText(testers)
        self._plan_stats_label.setText(stats_text)

    def _refresh_case_tree(self) -> None:
        self._case_tree.blockSignals(True)
        self._case_tree.clear()
        if not self._filtered_cases:
            self._case_tree.blockSignals(False)
            self._update_case_detail(None)
            return

        parents: dict[tuple[str, ...], QtWidgets.QTreeWidgetItem] = {}
        root = self._case_tree.invisibleRootItem()

        for case in self._filtered_cases:
            tokens = self._directory_tokens(case.group_path)
            parent = root
            key: tuple[str, ...] = ()
            for token in tokens:
                key = key + (token,)
                if key not in parents:
                    node = QtWidgets.QTreeWidgetItem([token])
                    node.setFlags(QtCore.Qt.ItemIsEnabled)
                    parent.addChild(node)
                    parents[key] = node
                parent = parents[key]
            item = QtWidgets.QTreeWidgetItem([case.title])
            item.setData(0, QtCore.Qt.UserRole, case)
            parent.addChild(item)

        self._case_tree.expandAll()
        self._case_tree.blockSignals(False)
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

    def _on_case_selected(
        self,
        current: Optional[QtWidgets.QTreeWidgetItem],
        previous: Optional[QtWidgets.QTreeWidgetItem],
    ) -> None:
        case = current.data(0, QtCore.Qt.UserRole) if current else None
        if not case:
            if previous and previous.data(0, QtCore.Qt.UserRole):
                self._case_tree.setCurrentItem(previous)
            else:
                self._update_case_detail(None)
            return
        self._logger.info("选中用例: %s (ID: %s)", case.title, case.case_id)
        self._update_case_detail(case)

    def _update_case_detail(self, case: Optional[PlanCase]) -> None:
        self._current_case = case
        self._current_actions = []
        self._attachments.clear()
        self._attachment_list.clear()
        if not case:
            self._title_label.setText("请选择一条用例")
            self._priority_label.setText("-")
            self._result_label.setText("-")
            self._directory_label.setText("-")
            self._keyword_list.clear()
            self._keyword_error.setVisible(False)
            self._attachment_hint.clear()
            return

        self._title_label.setText(case.title)
        self._priority_label.setText(case.priority or "-")
        self._result_label.setText(case.latest_result or "pending")
        self._directory_label.setText(self._normalize_directory(case.group_path))
        self._device_combo.clear()
        self._device_combo.addItem("(未指定)", userData=None)
        for model in case.device_models:
            self._device_combo.addItem(model.name or model.model_code or str(model.id), model.id)

        self._keyword_list.clear()
        try:
            actions = parse_keywords(case.keyword_actions())
        except ValidationError as exc:
            self._keyword_error.setText(str(exc))
            self._keyword_error.setVisible(True)
            self._start_monitor_btn.setEnabled(False)
            self._current_actions = []
        else:
            self._keyword_error.setVisible(False)
            self._current_actions = actions
            for action in actions:
                self._keyword_list.addItem(f"{action.name} -> {action.amount}")
            self._start_monitor_btn.setEnabled(bool(actions))
        self._stop_monitor_btn.setEnabled(False)
        self._log_view.clear()
        if require_attachment(self._current_actions):
            self._attachment_hint.setText("此用例包含时间监控，提交 PASS/FAIL 必须上传截图")
        else:
            self._attachment_hint.clear()

    # ------------------------------------------------------------------
    def _start_monitoring(self) -> None:
        if not self._current_case:
            QtWidgets.QMessageBox.information(self, "未选择", "请先选择用例")
            return
        if not self._current_actions:
            QtWidgets.QMessageBox.warning(self, "关键字错误", "关键字无法解析，无法启动监控")
            return
        start_time = dt.datetime.now().isoformat()
        self._monitoring.start(self._current_case.case_id, self._current_actions, start_time)
        self._append_log("监控已启动")
        self._logger.info("已启动监控: 用例 %s", self._current_case.case_id)
        self._start_monitor_btn.setEnabled(False)
        self._stop_monitor_btn.setEnabled(True)

    def _stop_monitoring(self) -> None:
        self._monitoring.stop()
        self._append_log("监控停止请求已发送")
        if self._current_case:
            self._logger.info("已请求停止监控: 用例 %s", self._current_case.case_id)
        self._start_monitor_btn.setEnabled(True)
        self._stop_monitor_btn.setEnabled(False)

    # ------------------------------------------------------------------
    def _add_attachment(self) -> None:
        if not self._current_case:
            return
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "选择图片",
            os.path.expanduser("~"),
            "Images (*.png *.jpg *.jpeg *.bmp)"
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
    def _submit_result(self, result: str) -> None:
        if not self._current_case:
            QtWidgets.QMessageBox.warning(self, "未选择", "请先选择用例")
            return
        try:
            actions = parse_keywords(self._current_case.keyword_actions())
        except ValidationError as exc:
            QtWidgets.QMessageBox.warning(self, "关键字错误", str(exc))
            return
        if result in {"pass", "fail"} and require_attachment(actions) and not self._attachments:
            QtWidgets.QMessageBox.warning(self, "缺少附件", "包含时间监控的用例必须上传截图")
            return
        plan_id = self._plan_combo.currentData()
        plan_case_id = self._current_case.id
        remark = self._remark_edit.toPlainText().strip()
        failure_reason = self._failure_edit.text().strip() or None
        bug_ref = self._bug_edit.text().strip() or None
        device_model_id = self._device_combo.currentData()
        if device_model_id is None:
            device_model_id = None
        attachments = [{k: v for k, v in payload.items() if k != "local_path"} for payload in self._attachments]
        try:
            self._api.submit_result(
                int(plan_id),
                int(plan_case_id),
                result,
                remark=remark,
                failure_reason=failure_reason,
                bug_ref=bug_ref,
                device_model_id=device_model_id,
                attachments=attachments or None,
            )
        except ClientError as exc:
            QtWidgets.QMessageBox.warning(self, "提交失败", str(exc))
            return
        self._logger.info(
            "提交结果: 用例 %s (结果=%s, 设备=%s)",
            self._current_case.case_id,
            result,
            device_model_id,
        )
        QtWidgets.QMessageBox.information(self, "成功", "结果已提交")
        self._remark_edit.clear()
        self._failure_edit.clear()
        self._bug_edit.clear()
        self._attachments.clear()
        self._attachment_list.clear()
        self._reload_current_plan()

    def _reload_current_plan(self) -> None:
        index = self._plan_combo.currentIndex()
        if index >= 0:
            self._on_plan_changed(index)

    # ------------------------------------------------------------------
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        geometry = self.saveGeometry()
        state = self.saveState()
        self._state_store.save(geometry, state)
        if self._monitoring.is_running():
            self._monitoring.stop()
        super().closeEvent(event)
