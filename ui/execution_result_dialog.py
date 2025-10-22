"""Dialog used to capture execution results for a plan case."""
from __future__ import annotations

import base64
import os
from typing import List, Optional

from PyQt5 import QtCore, QtWidgets

from ..models import ExecutionAttachment, ExecutionPayload, PlanCase
from ..utils.encryption import encode_timestamp


class ExecutionResultDialog(QtWidgets.QDialog):
    """Modal dialog for recording the execution result of a test case."""

    def __init__(
        self,
        case: PlanCase,
        result: str,
        requires_attachment: bool,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.case = case
        self.result = result
        self.requires_attachment = requires_attachment
        self.pending_attachments: List[ExecutionAttachment] = []

        self.setWindowTitle(f"记录结果 - {case.title}")
        self.resize(520, 560)

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        header = QtWidgets.QLabel(f"用例: {self.case.title}")
        header.setWordWrap(True)
        header.setStyleSheet("font-weight: 600;")
        layout.addWidget(header)

        result_label = QtWidgets.QLabel(f"结果: {self._display_result()}")
        layout.addWidget(result_label)

        layout.addWidget(QtWidgets.QLabel("备注 (必填)"))
        self.remark_edit = QtWidgets.QPlainTextEdit()
        self.remark_edit.setPlaceholderText("请输入执行备注")
        layout.addWidget(self.remark_edit)

        layout.addWidget(QtWidgets.QLabel("失败 / 阻塞原因"))
        self.failure_reason_edit = QtWidgets.QPlainTextEdit()
        self.failure_reason_edit.setPlaceholderText("可选填写失败或阻塞原因")
        self.failure_reason_edit.setMaximumHeight(80)
        layout.addWidget(self.failure_reason_edit)

        form_grid = QtWidgets.QGridLayout()
        form_grid.addWidget(QtWidgets.QLabel("缺陷编号"), 0, 0)
        self.bug_ref_edit = QtWidgets.QLineEdit()
        self.bug_ref_edit.setPlaceholderText("可选填写关联缺陷编号")
        form_grid.addWidget(self.bug_ref_edit, 0, 1)

        form_grid.addWidget(QtWidgets.QLabel("开始时间"), 1, 0)
        self.start_time_edit = QtWidgets.QDateTimeEdit(QtCore.QDateTime.currentDateTime())
        self.start_time_edit.setCalendarPopup(True)
        form_grid.addWidget(self.start_time_edit, 1, 1)

        form_grid.addWidget(QtWidgets.QLabel("结束时间"), 2, 0)
        self.end_time_edit = QtWidgets.QDateTimeEdit(QtCore.QDateTime.currentDateTime())
        self.end_time_edit.setCalendarPopup(True)
        form_grid.addWidget(self.end_time_edit, 2, 1)

        layout.addLayout(form_grid)

        attachment_box = QtWidgets.QGroupBox("执行截图")
        attachment_layout = QtWidgets.QVBoxLayout(attachment_box)
        self.attachment_list = QtWidgets.QListWidget()
        attachment_layout.addWidget(self.attachment_list)

        button_row = QtWidgets.QHBoxLayout()
        self.add_attachment_button = QtWidgets.QPushButton("添加图片")
        self.clear_attachment_button = QtWidgets.QPushButton("清空")
        button_row.addWidget(self.add_attachment_button)
        button_row.addWidget(self.clear_attachment_button)
        button_row.addStretch()
        attachment_layout.addLayout(button_row)

        hint_text = (
            "提示: 该用例关键字包含时间，提交前必须上传图片"
            if self.requires_attachment and self.result != "blocked"
            else "可选上传执行截图"
        )
        self.attachment_hint = QtWidgets.QLabel(hint_text)
        if self.requires_attachment and self.result != "blocked":
            self.attachment_hint.setStyleSheet("color: #d97706;")
        else:
            self.attachment_hint.setStyleSheet("color: #6b7280;")
        attachment_layout.addWidget(self.attachment_hint)

        layout.addWidget(attachment_box)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        layout.addWidget(self.button_box)

    def _connect_signals(self) -> None:
        self.add_attachment_button.clicked.connect(self._add_attachment)
        self.clear_attachment_button.clicked.connect(self._clear_attachments)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    # ------------------------------------------------------------------
    def _display_result(self) -> str:
        mapping = {"pass": "通过", "fail": "失败", "blocked": "阻塞"}
        return mapping.get(self.result, self.result)

    def _add_attachment(self) -> None:
        dialog = QtWidgets.QFileDialog(self, "选择图片")
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
        dialog.setNameFilters(["图片文件 (*.png *.jpg *.jpeg *.bmp)"])
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        for path in dialog.selectedFiles():
            try:
                with open(path, "rb") as handle:
                    content = base64.b64encode(handle.read()).decode("utf-8")
            except OSError as exc:
                QtWidgets.QMessageBox.warning(self, "提示", f"读取文件失败: {exc}")
                continue
            attachment = ExecutionAttachment(
                file_name=QtCore.QFileInfo(path).fileName(),
                content=f"data:image/{path.split('.')[-1]};base64,{content}",
                size=os.path.getsize(path),
            )
            self.pending_attachments.append(attachment)
            self.attachment_list.addItem(attachment.file_name)

    def _clear_attachments(self) -> None:
        self.pending_attachments.clear()
        self.attachment_list.clear()

    # ------------------------------------------------------------------
    def accept(self) -> None:  # type: ignore[override]
        remark = self.remark_edit.toPlainText().strip()
        if not remark:
            QtWidgets.QMessageBox.warning(self, "提示", "请填写备注信息")
            return
        if (
            self.requires_attachment
            and self.result != "blocked"
            and not self.pending_attachments
        ):
            QtWidgets.QMessageBox.warning(
                self, "提示", "该用例关键字包含时间，提交前必须上传图片"
            )
            return
        super().accept()

    # ------------------------------------------------------------------
    def build_payload(
        self,
        *,
        device_model_id: Optional[int],
        plan_device_model_id: Optional[int],
    ) -> ExecutionPayload:
        remark = self.remark_edit.toPlainText().strip()
        failure_reason = self.failure_reason_edit.toPlainText().strip() or None
        bug_ref = self.bug_ref_edit.text().strip() or None
        start_time = encode_timestamp(self.start_time_edit.dateTime().toPyDateTime())
        end_time = encode_timestamp(self.end_time_edit.dateTime().toPyDateTime())
        return ExecutionPayload(
            plan_case_id=self.case.id,
            result=self.result,
            remark=remark,
            failure_reason=failure_reason,
            bug_ref=bug_ref,
            execution_start_time=start_time,
            execution_end_time=end_time,
            attachments=list(self.pending_attachments),
            device_model_id=device_model_id,
            plan_device_model_id=plan_device_model_id,
        )
