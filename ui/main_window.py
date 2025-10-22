"""Main application window for the PATVS client."""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional, Tuple

from PyQt5 import QtCore, QtWidgets

from ..api.client import ApiClient, ApiError
from ..models import Plan, PlanCase, PlanDeviceModel
from ..monitoring.controller import MonitoringController
from ..monitoring.keymaps import normalize_keyword
from ..settings import SettingsStore
from .execution_result_dialog import ExecutionResultDialog


class MainWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        api_client: ApiClient,
        monitoring: MonitoringController,
        settings: SettingsStore,
        user_info: dict,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self.monitoring = monitoring
        self.settings = settings
        self.user_info = user_info

        self.current_department_id: Optional[int] = None
        self.current_project_id: Optional[int] = None
        self.current_plan: Optional[Plan] = None
        self.available_plans: List[Plan] = []
        self.plan_cases: List[PlanCase] = []
        self.plan_device_models: List[PlanDeviceModel] = []
        self.current_device_model: Optional[PlanDeviceModel] = None

        self.setWindowTitle("PATVS 桌面客户端")
        self.resize(1280, 800)
        self._build_ui()
        self._connect_signals()
        self._load_departments()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QVBoxLayout(central_widget)

        filter_group = QtWidgets.QGroupBox("计划筛选")
        filter_layout = QtWidgets.QGridLayout(filter_group)

        self.department_combo = QtWidgets.QComboBox()
        self.project_combo = QtWidgets.QComboBox()
        self.plan_combo = QtWidgets.QComboBox()
        self.device_combo = QtWidgets.QComboBox()

        for combo in (
            self.department_combo,
            self.project_combo,
            self.plan_combo,
            self.device_combo,
        ):
            combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)

        self.department_combo.addItem("请选择部门", None)
        self.project_combo.addItem("请选择项目", None)
        self.project_combo.setEnabled(False)
        self.plan_combo.addItem("请选择计划", None)
        self.plan_combo.setEnabled(False)
        self.device_combo.addItem("请选择机型", None)
        self.device_combo.setEnabled(False)

        filter_layout.addWidget(QtWidgets.QLabel("部门"), 0, 0)
        filter_layout.addWidget(self.department_combo, 0, 1)
        filter_layout.addWidget(QtWidgets.QLabel("项目"), 0, 2)
        filter_layout.addWidget(self.project_combo, 0, 3)
        filter_layout.addWidget(QtWidgets.QLabel("计划"), 0, 4)
        filter_layout.addWidget(self.plan_combo, 0, 5)
        filter_layout.addWidget(QtWidgets.QLabel("机型"), 0, 6)
        filter_layout.addWidget(self.device_combo, 0, 7)
        filter_layout.setColumnStretch(1, 1)
        filter_layout.setColumnStretch(3, 1)
        filter_layout.setColumnStretch(5, 1)
        filter_layout.setColumnStretch(7, 1)

        layout.addWidget(filter_group)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(splitter, stretch=1)

        # Left panel with case list and monitoring controls
        left_container = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.case_table = QtWidgets.QTableWidget(0, 6)
        self.case_table.setHorizontalHeaderLabels(
            ["用例ID", "标题", "优先级", "目录", "最新结果", "关键字"]
        )
        self.case_table.horizontalHeader().setStretchLastSection(True)
        self.case_table.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
        self.case_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.case_table.setAlternatingRowColors(True)
        left_layout.addWidget(self.case_table, stretch=1)

        action_layout = QtWidgets.QHBoxLayout()
        self.start_monitor_button = QtWidgets.QPushButton("开始监控")
        self.stop_monitor_button = QtWidgets.QPushButton("停止监控")
        action_layout.addWidget(self.start_monitor_button)
        action_layout.addWidget(self.stop_monitor_button)
        action_layout.addStretch()
        left_layout.addLayout(action_layout)

        log_group = QtWidgets.QGroupBox("监控日志")
        log_layout = QtWidgets.QVBoxLayout(log_group)
        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        log_layout.addWidget(self.log_view)
        left_layout.addWidget(log_group, stretch=1)

        splitter.addWidget(left_container)

        # Right panel with case details and result actions
        right_container = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        detail_group = QtWidgets.QGroupBox("用例详情")
        detail_layout = QtWidgets.QVBoxLayout(detail_group)

        self.case_title_label = QtWidgets.QLabel("请选择一个用例")
        self.case_title_label.setWordWrap(True)
        self.case_title_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        detail_layout.addWidget(self.case_title_label)

        info_grid = QtWidgets.QGridLayout()
        info_grid.addWidget(QtWidgets.QLabel("优先级"), 0, 0)
        self.case_priority_label = QtWidgets.QLabel("-")
        info_grid.addWidget(self.case_priority_label, 0, 1)
        info_grid.addWidget(QtWidgets.QLabel("最新结果"), 0, 2)
        self.case_result_label = QtWidgets.QLabel("-")
        info_grid.addWidget(self.case_result_label, 0, 3)
        info_grid.addWidget(QtWidgets.QLabel("目录"), 1, 0)
        self.case_directory_label = QtWidgets.QLabel("-")
        self.case_directory_label.setWordWrap(True)
        info_grid.addWidget(self.case_directory_label, 1, 1, 1, 3)
        info_grid.addWidget(QtWidgets.QLabel("关键字"), 2, 0)
        self.case_keywords_label = QtWidgets.QLabel("-")
        self.case_keywords_label.setWordWrap(True)
        info_grid.addWidget(self.case_keywords_label, 2, 1, 1, 3)
        detail_layout.addLayout(info_grid)

        detail_layout.addWidget(QtWidgets.QLabel("前置条件"))
        self.case_preconditions_view = QtWidgets.QPlainTextEdit()
        self.case_preconditions_view.setReadOnly(True)
        self.case_preconditions_view.setMaximumHeight(100)
        detail_layout.addWidget(self.case_preconditions_view)

        detail_layout.addWidget(QtWidgets.QLabel("预期结果"))
        self.case_expected_view = QtWidgets.QPlainTextEdit()
        self.case_expected_view.setReadOnly(True)
        self.case_expected_view.setMaximumHeight(120)
        detail_layout.addWidget(self.case_expected_view)

        self.case_steps_table = QtWidgets.QTableWidget(0, 3)
        self.case_steps_table.setHorizontalHeaderLabels(["序号", "操作步骤", "预期结果"])
        self.case_steps_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.case_steps_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.case_steps_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.case_steps_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.case_steps_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        detail_layout.addWidget(self.case_steps_table, stretch=1)

        right_layout.addWidget(detail_group, stretch=1)

        result_group = QtWidgets.QGroupBox("记录结果")
        result_layout = QtWidgets.QVBoxLayout(result_group)
        button_row = QtWidgets.QHBoxLayout()
        self.pass_button = QtWidgets.QPushButton("标记通过")
        self.fail_button = QtWidgets.QPushButton("标记失败")
        self.block_button = QtWidgets.QPushButton("标记阻塞")
        button_row.addWidget(self.pass_button)
        button_row.addWidget(self.fail_button)
        button_row.addWidget(self.block_button)
        button_row.addStretch()
        result_layout.addLayout(button_row)
        hint_label = QtWidgets.QLabel("点击按钮后将在弹窗中填写详细结果")
        hint_label.setStyleSheet("color: #555555;")
        result_layout.addWidget(hint_label)
        right_layout.addWidget(result_group)
        right_layout.addStretch(1)

        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        status_bar = self.statusBar()
        status_bar.showMessage(
            f"当前用户: {self.user_info.get('real_name') or self.user_info.get('username')}"
        )

    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        self.department_combo.currentIndexChanged.connect(self._on_department_changed)
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        self.plan_combo.currentIndexChanged.connect(self._on_plan_changed)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        self.case_table.itemSelectionChanged.connect(self._update_case_detail)
        self.start_monitor_button.clicked.connect(self._start_monitoring)
        self.stop_monitor_button.clicked.connect(self.monitoring.stop)
        self.pass_button.clicked.connect(lambda: self._record_result("pass"))
        self.fail_button.clicked.connect(lambda: self._record_result("fail"))
        self.block_button.clicked.connect(lambda: self._record_result("blocked"))
        self.monitoring.log_generated.connect(self._append_log)
        self.monitoring.monitoring_finished.connect(lambda: self._append_log("监控任务已完成"))
        self.monitoring.monitoring_error.connect(self._handle_monitor_error)

    # ------------------------------------------------------------------
    def _reset_project_combo(self) -> None:
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItem("请选择项目", None)
        self.project_combo.blockSignals(False)
        self.project_combo.setEnabled(False)
        self.current_project_id = None

    def _reset_plan_combo(self) -> None:
        self.plan_combo.blockSignals(True)
        self.plan_combo.clear()
        self.plan_combo.addItem("请选择计划", None)
        self.plan_combo.blockSignals(False)
        self.plan_combo.setEnabled(False)
        self.current_plan = None
        self.available_plans = []

    def _reset_device_combo(self) -> None:
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_combo.addItem("请选择机型", None)
        self.device_combo.blockSignals(False)
        self.device_combo.setEnabled(False)
        self.plan_device_models = []
        self.current_device_model = None

    def _clear_cases(self) -> None:
        self.plan_cases = []
        self.case_table.setRowCount(0)
        self._clear_case_detail()

    # ------------------------------------------------------------------
    def _load_departments(self) -> None:
        self.department_combo.blockSignals(True)
        self.department_combo.clear()
        self.department_combo.addItem("请选择部门", None)
        self.department_combo.blockSignals(False)
        self.department_combo.setEnabled(False)
        self._reset_project_combo()
        self._reset_plan_combo()
        self._reset_device_combo()
        self._clear_cases()
        try:
            departments = self.api_client.get_departments()
        except ApiError as exc:
            self._show_error(str(exc))
            return
        self.department_combo.blockSignals(True)
        for dept in departments:
            self.department_combo.addItem(dept.name, dept.id)
        self.department_combo.blockSignals(False)
        self.department_combo.setEnabled(bool(departments))

    def _on_department_changed(self, index: int) -> None:
        dept_id = self.department_combo.itemData(index)
        if not dept_id:
            self.current_department_id = None
            self._reset_project_combo()
            self._reset_plan_combo()
            self._reset_device_combo()
            self._clear_cases()
            return
        self.current_department_id = dept_id
        self._load_projects()

    def _load_projects(self) -> None:
        self._reset_project_combo()
        self._reset_plan_combo()
        self._reset_device_combo()
        self._clear_cases()
        if not self.current_department_id:
            return
        try:
            projects = self.api_client.get_projects(self.current_department_id)
        except ApiError as exc:
            self._show_error(str(exc))
            return
        self.project_combo.blockSignals(True)
        for project in projects:
            self.project_combo.addItem(project.name, project.id)
        self.project_combo.blockSignals(False)
        self.project_combo.setEnabled(bool(projects))

    def _on_project_changed(self, index: int) -> None:
        project_id = self.project_combo.itemData(index)
        if not project_id:
            self.current_project_id = None
            self._reset_plan_combo()
            self._reset_device_combo()
            self._clear_cases()
            return
        self.current_project_id = project_id
        self._load_plans()

    def _load_plans(self) -> None:
        self._reset_plan_combo()
        self._reset_device_combo()
        self._clear_cases()
        if not self.current_department_id or not self.current_project_id:
            return
        try:
            plans = self.api_client.get_plans(
                self.current_department_id, self.current_project_id
            )
        except ApiError as exc:
            self._show_error(str(exc))
            return
        self.available_plans = plans
        self.plan_combo.blockSignals(True)
        for plan in plans:
            self.plan_combo.addItem(plan.name, plan.id)
        self.plan_combo.blockSignals(False)
        self.plan_combo.setEnabled(bool(plans))

    def _on_plan_changed(self, index: int) -> None:
        if index <= 0 or index - 1 >= len(self.available_plans):
            plan_id = self.plan_combo.itemData(index)
            if plan_id is None:
                self.current_plan = None
                self._reset_device_combo()
                self._clear_cases()
                return
            self.current_plan = Plan(
                id=plan_id,
                name=self.plan_combo.itemText(index),
                department_id=self.current_department_id or 0,
                project_id=self.current_project_id or 0,
                status="unknown",
            )
        else:
            self.current_plan = self.available_plans[index - 1]
        self._load_plan_devices()

    def _load_plan_devices(self) -> None:
        self._reset_device_combo()
        self._clear_cases()
        if not self.current_plan:
            return
        try:
            devices = self.api_client.get_plan_device_models(self.current_plan.id)
        except ApiError as exc:
            self._show_error(str(exc))
            return
        self.plan_device_models = devices
        self.device_combo.blockSignals(True)
        for model in devices:
            display = model.name or model.model_code or f"设备 {model.device_model_id or ''}"
            self.device_combo.addItem(display, model)
        self.device_combo.blockSignals(False)
        self.device_combo.setEnabled(bool(devices))

    def _on_device_changed(self, index: int) -> None:
        data = self.device_combo.itemData(index)
        if not isinstance(data, PlanDeviceModel):
            self.current_device_model = None
            self._clear_cases()
            return
        self.current_device_model = data
        self._load_cases()

    # ------------------------------------------------------------------
    def _load_cases(self) -> None:
        if not self.current_plan or not self.current_device_model:
            self._clear_cases()
            return
        device_filter = self.current_device_model.name or self.current_device_model.model_code
        try:
            cases = self.api_client.get_plan_cases(
                self.current_plan.id,
                device_model=device_filter,
            )
        except ApiError as exc:
            self._show_error(str(exc))
            return
        self.plan_cases = cases
        self._populate_case_table()

    def _populate_case_table(self) -> None:
        self.case_table.setRowCount(len(self.plan_cases))
        for row, case in enumerate(self.plan_cases):
            self.case_table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(case.case_id)))
            self.case_table.setItem(row, 1, QtWidgets.QTableWidgetItem(case.title))
            self.case_table.setItem(row, 2, QtWidgets.QTableWidgetItem(case.priority))
            self.case_table.setItem(row, 3, QtWidgets.QTableWidgetItem(case.group_path))
            self.case_table.setItem(
                row, 4, QtWidgets.QTableWidgetItem(case.latest_result or "")
            )
            self.case_table.setItem(
                row,
                5,
                QtWidgets.QTableWidgetItem(", ".join(case.keywords) if case.keywords else ""),
            )
        self.case_table.resizeColumnsToContents()
        if self.plan_cases:
            self.case_table.selectRow(0)
        else:
            self._clear_case_detail()

    # ------------------------------------------------------------------
    def _selected_case(self) -> Optional[PlanCase]:
        selected = self.case_table.selectionModel().selectedRows()
        if not selected:
            return None
        index = selected[0].row()
        if index < 0 or index >= len(self.plan_cases):
            return None
        return self.plan_cases[index]

    def _clear_case_detail(self) -> None:
        self.case_title_label.setText("请选择一个用例")
        self.case_priority_label.setText("-")
        self.case_result_label.setText("-")
        self.case_directory_label.setText("-")
        self.case_keywords_label.setText("-")
        self.case_preconditions_view.clear()
        self.case_expected_view.clear()
        self.case_steps_table.setRowCount(0)

    def _update_case_detail(self) -> None:
        case = self._selected_case()
        if not case:
            self._clear_case_detail()
            return
        self.case_title_label.setText(case.title)
        self.case_priority_label.setText(case.priority or "-")
        self.case_result_label.setText(case.latest_result or "-")
        self.case_directory_label.setText(case.group_path or "-")
        keywords = ", ".join(case.keywords) if case.keywords else "-"
        self.case_keywords_label.setText(keywords)
        self.case_preconditions_view.setPlainText(case.preconditions or "无")
        self.case_expected_view.setPlainText(case.expected_result or "无")

        steps = list(case.steps or [])
        self.case_steps_table.setRowCount(len(steps))
        for row, step in enumerate(steps):
            if isinstance(step, dict):
                no = step.get("no") or row + 1
                action = step.get("action", "")
                expected = step.get("expected", "")
            else:
                no = getattr(step, "no", row + 1)
                action = getattr(step, "action", "")
                expected = getattr(step, "expected", "")
            self.case_steps_table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(no)))
            self.case_steps_table.setItem(row, 1, QtWidgets.QTableWidgetItem(action))
            self.case_steps_table.setItem(row, 2, QtWidgets.QTableWidgetItem(expected))

        status = f"选中用例: {case.title}"
        if self.current_device_model:
            model_name = (
                self.current_device_model.name
                or self.current_device_model.model_code
                or str(self.current_device_model.device_model_id or "")
            )
            status += f" | 机型: {model_name}"
        self.statusBar().showMessage(status)

    # ------------------------------------------------------------------
    def _parse_keywords(self, case: PlanCase) -> List[Tuple[str, float]]:
        actions: List[Tuple[str, float]] = []
        for keyword in case.keywords:
            segments = [segment.strip() for segment in re.split(r"[\s,，]+", keyword) if segment.strip()]
            for segment in segments:
                if "+" not in segment:
                    raise ValueError(f"关键字格式错误: {segment}")
                action_part, count_part = segment.split("+", 1)
                action = action_part.strip()
                if not action:
                    raise ValueError(f"关键字缺少动作: {segment}")
                try:
                    count = float(count_part.strip())
                except ValueError as exc:
                    raise ValueError(f"关键字次数必须为数字: {segment}") from exc
                actions.append((action, count))
        if not actions:
            raise ValueError("该用例未配置关键字，无法启动监控")
        return actions

    def _case_requires_attachment(self, case: PlanCase) -> bool:
        for action, _ in self._parse_keywords(case):
            normalized, _ = normalize_keyword(action)
            if "时间" in normalized:
                return True
        return False

    def _start_monitoring(self) -> None:
        case = self._selected_case()
        if not case:
            self._show_error("请先选择一个用例")
            return
        try:
            actions = self._parse_keywords(case)
        except ValueError as exc:
            self._show_error(str(exc))
            return
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.monitoring.start(case.case_id, actions, start_time)
        self._append_log(f"已启动监控: {case.title}")

    # ------------------------------------------------------------------
    def _record_result(self, result: str) -> None:
        case = self._selected_case()
        if not case:
            self._show_error("请先选择一个用例")
            return
        if not self.current_plan:
            self._show_error("请先选择一个测试计划")
            return
        if not self.current_device_model:
            self._show_error("请先选择一个机型")
            return
        try:
            actions = self._parse_keywords(case)
        except ValueError as exc:
            self._show_error(str(exc))
            return
        requires_attachment = any(
            "时间" in normalize_keyword(action)[0] for action, _ in actions
        )
        dialog = ExecutionResultDialog(case, result, requires_attachment, self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        payload = dialog.build_payload(
            device_model_id=self.current_device_model.device_model_id,
            plan_device_model_id=self.current_device_model.plan_device_model_id,
        )
        try:
            response = self.api_client.post_execution_result(self.current_plan.id, payload)
        except ApiError as exc:
            self._show_error(str(exc))
            return
        self._append_log(f"结果提交成功: {response.get('message', 'success')}")
        self._load_cases()

    # ------------------------------------------------------------------
    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{timestamp}] {message}")

    def _handle_monitor_error(self, message: str) -> None:
        self._append_log(f"监控异常: {message}")
        self._show_error(message)

    # ------------------------------------------------------------------
    def _show_error(self, message: str) -> None:
        QtWidgets.QMessageBox.critical(self, "错误", message)
