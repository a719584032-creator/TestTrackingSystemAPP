"""Main application window for the PATVS client."""
from __future__ import annotations

import base64
import os
import re
from datetime import datetime
from typing import List, Optional, Sequence, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

from ..api.client import ApiClient, ApiError
from ..models import ExecutionAttachment, ExecutionPayload, PlanCase, Plan
from ..monitoring.controller import MonitoringController
from ..monitoring.keymaps import normalize_keyword
from ..settings import PlanFilters, SettingsStore
from ..utils.encryption import encode_timestamp


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
        self.pending_attachments: List[ExecutionAttachment] = []

        self.setWindowTitle("PATVS 桌面客户端")
        self.resize(1280, 800)
        self._build_ui()
        self._connect_signals()
        self._load_initial_filters()
        self._load_departments()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QVBoxLayout(central_widget)

        # Filters -------------------------------------------------------
        filter_group = QtWidgets.QGroupBox("计划筛选")
        filter_layout = QtWidgets.QGridLayout(filter_group)

        self.department_combo = QtWidgets.QComboBox()
        self.project_combo = QtWidgets.QComboBox()
        self.plan_combo = QtWidgets.QComboBox()

        filter_layout.addWidget(QtWidgets.QLabel("部门"), 0, 0)
        filter_layout.addWidget(self.department_combo, 0, 1)
        filter_layout.addWidget(QtWidgets.QLabel("项目"), 0, 2)
        filter_layout.addWidget(self.project_combo, 0, 3)
        filter_layout.addWidget(QtWidgets.QLabel("计划"), 0, 4)
        filter_layout.addWidget(self.plan_combo, 0, 5)

        self.directory_edit = QtWidgets.QLineEdit()
        self.directory_edit.setPlaceholderText("目录关键词")
        self.device_model_edit = QtWidgets.QLineEdit()
        self.device_model_edit.setPlaceholderText("机型关键词")
        self.priority_combo = QtWidgets.QComboBox()
        self.priority_combo.addItems(["", "P0", "P1", "P2", "P3"])
        self.result_combo = QtWidgets.QComboBox()
        self.result_combo.addItems(["", "pass", "fail", "blocked", "pending"])

        filter_layout.addWidget(QtWidgets.QLabel("目录"), 1, 0)
        filter_layout.addWidget(self.directory_edit, 1, 1)
        filter_layout.addWidget(QtWidgets.QLabel("机型"), 1, 2)
        filter_layout.addWidget(self.device_model_edit, 1, 3)
        filter_layout.addWidget(QtWidgets.QLabel("优先级"), 1, 4)
        filter_layout.addWidget(self.priority_combo, 1, 5)
        filter_layout.addWidget(QtWidgets.QLabel("结果"), 1, 6)
        filter_layout.addWidget(self.result_combo, 1, 7)

        self.refresh_button = QtWidgets.QPushButton("加载用例")
        filter_layout.addWidget(self.refresh_button, 0, 6, 1, 2)

        layout.addWidget(filter_group)

        # Case table ----------------------------------------------------
        self.case_table = QtWidgets.QTableWidget(0, 6)
        self.case_table.setHorizontalHeaderLabels([
            "用例ID",
            "标题",
            "优先级",
            "目录",
            "最新结果",
            "关键字",
        ])
        self.case_table.horizontalHeader().setStretchLastSection(True)
        self.case_table.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
        self.case_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.case_table)

        # Action buttons ------------------------------------------------
        action_layout = QtWidgets.QHBoxLayout()
        self.view_case_button = QtWidgets.QPushButton("查看详情")
        self.start_monitor_button = QtWidgets.QPushButton("开始监控")
        self.stop_monitor_button = QtWidgets.QPushButton("停止监控")
        action_layout.addWidget(self.view_case_button)
        action_layout.addWidget(self.start_monitor_button)
        action_layout.addWidget(self.stop_monitor_button)
        action_layout.addStretch()
        layout.addLayout(action_layout)

        # Result section ------------------------------------------------
        result_group = QtWidgets.QGroupBox("用例结果记录")
        result_layout = QtWidgets.QGridLayout(result_group)
        self.result_selector = QtWidgets.QComboBox()
        self.result_selector.addItems(["pass", "fail", "blocked", "pending"])
        self.remark_edit = QtWidgets.QPlainTextEdit()
        self.remark_edit.setPlaceholderText("备注 / 评论")
        self.failure_reason_edit = QtWidgets.QPlainTextEdit()
        self.failure_reason_edit.setPlaceholderText("失败或阻塞原因（可选）")
        self.bug_ref_edit = QtWidgets.QLineEdit()
        self.bug_ref_edit.setPlaceholderText("缺陷编号（可选）")

        self.execution_start_edit = QtWidgets.QDateTimeEdit(QtCore.QDateTime.currentDateTime())
        self.execution_start_edit.setCalendarPopup(True)
        self.execution_end_edit = QtWidgets.QDateTimeEdit(QtCore.QDateTime.currentDateTime())
        self.execution_end_edit.setCalendarPopup(True)

        self.device_model_id_edit = QtWidgets.QLineEdit()
        self.device_model_id_edit.setPlaceholderText("设备型号 ID（可选）")
        self.plan_device_model_id_edit = QtWidgets.QLineEdit()
        self.plan_device_model_id_edit.setPlaceholderText("计划设备 ID（可选）")

        self.attachment_list = QtWidgets.QListWidget()
        self.add_attachment_button = QtWidgets.QPushButton("添加图片")
        self.clear_attachment_button = QtWidgets.QPushButton("清空图片")
        self.submit_result_button = QtWidgets.QPushButton("提交结果")

        result_layout.addWidget(QtWidgets.QLabel("结果"), 0, 0)
        result_layout.addWidget(self.result_selector, 0, 1)
        result_layout.addWidget(QtWidgets.QLabel("缺陷编号"), 0, 2)
        result_layout.addWidget(self.bug_ref_edit, 0, 3)
        result_layout.addWidget(QtWidgets.QLabel("开始时间"), 1, 0)
        result_layout.addWidget(self.execution_start_edit, 1, 1)
        result_layout.addWidget(QtWidgets.QLabel("结束时间"), 1, 2)
        result_layout.addWidget(self.execution_end_edit, 1, 3)
        result_layout.addWidget(QtWidgets.QLabel("备注"), 2, 0)
        result_layout.addWidget(self.remark_edit, 2, 1, 1, 3)
        result_layout.addWidget(QtWidgets.QLabel("失败原因"), 3, 0)
        result_layout.addWidget(self.failure_reason_edit, 3, 1, 1, 3)
        result_layout.addWidget(QtWidgets.QLabel("设备 ID"), 4, 0)
        result_layout.addWidget(self.device_model_id_edit, 4, 1)
        result_layout.addWidget(QtWidgets.QLabel("计划设备 ID"), 4, 2)
        result_layout.addWidget(self.plan_device_model_id_edit, 4, 3)
        result_layout.addWidget(QtWidgets.QLabel("图片附件"), 5, 0)
        result_layout.addWidget(self.attachment_list, 5, 1, 2, 2)

        button_column = QtWidgets.QVBoxLayout()
        button_column.addWidget(self.add_attachment_button)
        button_column.addWidget(self.clear_attachment_button)
        button_column.addWidget(self.submit_result_button)
        button_column.addStretch()
        result_layout.addLayout(button_column, 5, 3)

        layout.addWidget(result_group)

        # Log area ------------------------------------------------------
        log_group = QtWidgets.QGroupBox("监控日志")
        log_layout = QtWidgets.QVBoxLayout(log_group)
        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_group)

        status_bar = self.statusBar()
        status_bar.showMessage(f"当前用户: {self.user_info.get('real_name') or self.user_info.get('username')}")

    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        self.department_combo.currentIndexChanged.connect(self._on_department_changed)
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        self.plan_combo.currentIndexChanged.connect(self._on_plan_changed)
        self.refresh_button.clicked.connect(self._load_cases)
        self.case_table.itemSelectionChanged.connect(self._update_execution_form)
        self.view_case_button.clicked.connect(self._open_case_details)
        self.start_monitor_button.clicked.connect(self._start_monitoring)
        self.stop_monitor_button.clicked.connect(self.monitoring.stop)
        self.add_attachment_button.clicked.connect(self._add_attachment)
        self.clear_attachment_button.clicked.connect(self._clear_attachments)
        self.submit_result_button.clicked.connect(self._submit_result)
        self.monitoring.log_generated.connect(self._append_log)
        self.monitoring.monitoring_finished.connect(lambda: self._append_log("监控任务已完成"))
        self.monitoring.monitoring_error.connect(self._handle_monitor_error)

    # ------------------------------------------------------------------
    def _load_initial_filters(self) -> None:
        filters = self.settings.get_filters()
        if filters.directory:
            self.directory_edit.setText(filters.directory)
        if filters.device_model:
            self.device_model_edit.setText(filters.device_model)
        if filters.priority:
            index = self.priority_combo.findText(filters.priority)
            if index >= 0:
                self.priority_combo.setCurrentIndex(index)
        if filters.result:
            index = self.result_combo.findText(filters.result)
            if index >= 0:
                self.result_combo.setCurrentIndex(index)

    # ------------------------------------------------------------------
    def _load_departments(self) -> None:
        self.department_combo.clear()
        try:
            departments = self.api_client.get_departments()
        except ApiError as exc:
            self._show_error(str(exc))
            return
        for dept in departments:
            self.department_combo.addItem(dept.name, dept.id)
        if departments:
            self.current_department_id = departments[0].id

    def _on_department_changed(self, index: int) -> None:
        self.current_department_id = self.department_combo.itemData(index)
        self._load_projects()

    def _load_projects(self) -> None:
        self.project_combo.clear()
        if not self.current_department_id:
            return
        try:
            projects = self.api_client.get_projects(self.current_department_id)
        except ApiError as exc:
            self._show_error(str(exc))
            return
        for project in projects:
            self.project_combo.addItem(project.name, project.id)
        if projects:
            self.current_project_id = projects[0].id
            self._load_plans()

    def _on_project_changed(self, index: int) -> None:
        self.current_project_id = self.project_combo.itemData(index)
        self._load_plans()

    def _load_plans(self) -> None:
        self.plan_combo.clear()
        if not self.current_department_id or not self.current_project_id:
            return
        try:
            plans = self.api_client.get_plans(self.current_department_id, self.current_project_id)
        except ApiError as exc:
            self._show_error(str(exc))
            return
        self.available_plans = plans
        for plan in plans:
            self.plan_combo.addItem(plan.name, plan.id)
        if plans:
            self.current_plan = plans[0]
            self._load_cases()

    def _on_plan_changed(self, index: int) -> None:
        if index < 0 or index >= len(self.available_plans):
            plan_id = self.plan_combo.itemData(index)
            if plan_id is None:
                self.current_plan = None
                return
            self.current_plan = Plan(
                id=plan_id,
                name=self.plan_combo.itemText(index),
                department_id=self.current_department_id or 0,
                project_id=self.current_project_id or 0,
                status="unknown",
            )
        else:
            self.current_plan = self.available_plans[index]
        self._load_cases()

    # ------------------------------------------------------------------
    def _collect_filters(self) -> PlanFilters:
        return PlanFilters(
            directory=self.directory_edit.text().strip() or None,
            device_model=self.device_model_edit.text().strip() or None,
            priority=self.priority_combo.currentText() or None,
            result=self.result_combo.currentText() or None,
        )

    def _load_cases(self) -> None:
        if not self.current_plan:
            return
        filters = self._collect_filters()
        self.settings.save_filters(filters)
        try:
            cases = self.api_client.get_plan_cases(
                self.current_plan.id,
                directory=filters.directory,
                device_model=filters.device_model,
                priority=filters.priority,
                result=filters.result,
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
            self.case_table.setItem(row, 4, QtWidgets.QTableWidgetItem(case.latest_result or ""))
            self.case_table.setItem(row, 5, QtWidgets.QTableWidgetItem(", ".join(case.keywords)))
        self.case_table.resizeColumnsToContents()
        if self.plan_cases:
            self.case_table.selectRow(0)
        else:
            self._clear_execution_form()

    # ------------------------------------------------------------------
    def _selected_case(self) -> Optional[PlanCase]:
        selected = self.case_table.selectionModel().selectedRows()
        if not selected:
            return None
        index = selected[0].row()
        if index < 0 or index >= len(self.plan_cases):
            return None
        return self.plan_cases[index]

    def _update_execution_form(self) -> None:
        self.pending_attachments.clear()
        self.attachment_list.clear()
        case = self._selected_case()
        if not case:
            self._clear_execution_form()
            return
        self.remark_edit.clear()
        self.failure_reason_edit.clear()
        self.bug_ref_edit.clear()
        self.execution_start_edit.setDateTime(QtCore.QDateTime.currentDateTime())
        self.execution_end_edit.setDateTime(QtCore.QDateTime.currentDateTime())
        self.device_model_id_edit.clear()
        self.plan_device_model_id_edit.clear()
        self.statusBar().showMessage(f"选中用例: {case.title}")

    def _clear_execution_form(self) -> None:
        self.remark_edit.clear()
        self.failure_reason_edit.clear()
        self.bug_ref_edit.clear()
        self.attachment_list.clear()
        self.pending_attachments.clear()

    # ------------------------------------------------------------------
    def _open_case_details(self) -> None:
        case = self._selected_case()
        if not case:
            self._show_error("请先选择一个用例")
            return
        if not self.current_plan:
            self._show_error("请先选择一个测试计划")
            return
        from .case_detail_dialog import CaseDetailDialog

        dialog = CaseDetailDialog(case, self)
        dialog.exec_()

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
    def _add_attachment(self) -> None:
        file_dialog = QtWidgets.QFileDialog(self, "选择图片")
        file_dialog.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
        file_dialog.setNameFilters(["图片文件 (*.png *.jpg *.jpeg *.bmp)"])
        if file_dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        for file_path in file_dialog.selectedFiles():
            try:
                with open(file_path, "rb") as fh:
                    content = base64.b64encode(fh.read()).decode("utf-8")
            except OSError as exc:
                self._show_error(f"读取文件失败: {exc}")
                continue
            attachment = ExecutionAttachment(
                file_name=QtCore.QFileInfo(file_path).fileName(),
                content=f"data:image/{file_path.split('.')[-1]};base64,{content}",
                size=os.path.getsize(file_path),
            )
            self.pending_attachments.append(attachment)
            self.attachment_list.addItem(attachment.file_name)

    def _clear_attachments(self) -> None:
        self.pending_attachments.clear()
        self.attachment_list.clear()

    # ------------------------------------------------------------------
    def _build_execution_payload(self, case: PlanCase) -> ExecutionPayload:
        result = self.result_selector.currentText()
        remark = self.remark_edit.toPlainText().strip()
        failure_reason = self.failure_reason_edit.toPlainText().strip() or None
        bug_ref = self.bug_ref_edit.text().strip() or None
        start_time = encode_timestamp(self.execution_start_edit.dateTime().toPyDateTime())
        end_time = encode_timestamp(self.execution_end_edit.dateTime().toPyDateTime())
        device_model_id = self._parse_optional_int(self.device_model_id_edit.text())
        plan_device_model_id = self._parse_optional_int(self.plan_device_model_id_edit.text())
        return ExecutionPayload(
            plan_case_id=case.id,
            result=result,
            remark=remark,
            failure_reason=failure_reason,
            bug_ref=bug_ref,
            execution_start_time=start_time,
            execution_end_time=end_time,
            attachments=list(self.pending_attachments),
            device_model_id=device_model_id,
            plan_device_model_id=plan_device_model_id,
        )

    def _submit_result(self) -> None:
        case = self._selected_case()
        if not case:
            self._show_error("请先选择一个用例")
            return
        requires_attachment = False
        try:
            actions = self._parse_keywords(case)
            requires_attachment = any("时间" in normalize_keyword(action)[0] for action, _ in actions)
        except ValueError as exc:
            self._show_error(str(exc))
            return
        result = self.result_selector.currentText()
        if requires_attachment and result != "blocked" and not self.pending_attachments:
            self._show_error("该用例关键字包含时间，提交结果前必须上传图片")
            return
        payload = self._build_execution_payload(case)
        if not payload.remark:
            self._show_error("请填写备注信息")
            return
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
    def _parse_optional_int(self, value: str) -> Optional[int]:
        value = value.strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            self._show_error(f"请输入有效的数字: {value}")
            return None

    def _show_error(self, message: str) -> None:
        QtWidgets.QMessageBox.critical(self, "错误", message)
