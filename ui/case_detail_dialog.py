"""Dialog for displaying plan case details and monitoring instructions."""
from __future__ import annotations

from typing import Iterable, Optional

from PyQt5 import QtCore, QtWidgets

from ..models import PlanCase


class CaseDetailDialog(QtWidgets.QDialog):
    def __init__(self, plan_case: PlanCase, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(plan_case.title)
        self.resize(640, 480)
        self._build_ui(plan_case)

    def _build_ui(self, plan_case: PlanCase) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        meta_widget = QtWidgets.QWidget()
        meta_layout = QtWidgets.QFormLayout(meta_widget)
        meta_layout.addRow("用例编号", QtWidgets.QLabel(str(plan_case.case_id)))
        meta_layout.addRow("优先级", QtWidgets.QLabel(plan_case.priority))
        meta_layout.addRow("目录", QtWidgets.QLabel(plan_case.group_path))
        meta_layout.addRow("关键字", QtWidgets.QLabel(", ".join(plan_case.keywords)))
        layout.addWidget(meta_widget)

        if plan_case.preconditions:
            pre_label = QtWidgets.QLabel(plan_case.preconditions)
            pre_label.setWordWrap(True)
            pre_group = QtWidgets.QGroupBox("前置条件")
            pre_layout = QtWidgets.QVBoxLayout(pre_group)
            pre_layout.addWidget(pre_label)
            layout.addWidget(pre_group)

        steps_group = QtWidgets.QGroupBox("测试步骤")
        steps_layout = QtWidgets.QVBoxLayout(steps_group)
        for step in plan_case.steps:
            text = f"步骤 {step.no}: {step.action}\n期望: {step.expected}"
            if step.note:
                text += f"\n备注: {step.note}"
            step_label = QtWidgets.QLabel(text)
            step_label.setWordWrap(True)
            step_label.setStyleSheet("padding: 4px")
            steps_layout.addWidget(step_label)
        layout.addWidget(steps_group)

        if plan_case.expected_result:
            result_group = QtWidgets.QGroupBox("预期结果")
            result_layout = QtWidgets.QVBoxLayout(result_group)
            result_label = QtWidgets.QLabel(plan_case.expected_result)
            result_label.setWordWrap(True)
            result_layout.addWidget(result_label)
            layout.addWidget(result_group)

        close_button = QtWidgets.QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=QtCore.Qt.AlignRight)
