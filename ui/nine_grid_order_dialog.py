"""Nine-grid ordering dialog."""
from __future__ import annotations

from typing import Iterable, List

from PyQt5 import QtCore, QtWidgets

from monitoring.nine_grid import NineGridAction


class NineGridOrderDialog(QtWidgets.QDialog):
    """Allow users to reorder nine-grid actions before execution."""

    def __init__(
        self,
        actions: Iterable[NineGridAction],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._actions: List[NineGridAction] = list(actions)
        self._list_widget: QtWidgets.QListWidget | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("九宫格动作排序")
        self.setModal(True)
        self.setMinimumSize(600, 500)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hint = QtWidgets.QLabel("拖动或使用按钮调整动作执行顺序")
        hint.setStyleSheet("color: #475569;")
        layout.addWidget(hint)

        body = QtWidgets.QHBoxLayout()
        layout.addLayout(body, stretch=1)

        self._list_widget = QtWidgets.QListWidget()
        self._list_widget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self._list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._list_widget.setAlternatingRowColors(True)
        self._list_widget.setStyleSheet(
            "QListWidget { background: #ffffff; color: #111827; }"
        )
        self._list_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )
        self._list_widget.setMinimumHeight(260)
        body.addWidget(self._list_widget, stretch=1)

        controls = QtWidgets.QVBoxLayout()
        body.addLayout(controls)

        move_up = QtWidgets.QPushButton("上移")
        move_down = QtWidgets.QPushButton("下移")
        move_up.clicked.connect(lambda: self._move_item(-1))
        move_down.clicked.connect(lambda: self._move_item(1))
        controls.addWidget(move_up)
        controls.addWidget(move_down)
        controls.addStretch(1)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._populate()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override naming
        super().showEvent(event)
        self._populate()

    def _populate(self) -> None:
        if self._list_widget is None:
            return
        self._list_widget.clear()
        for index, action in enumerate(self._actions):
            item = QtWidgets.QListWidgetItem(
                f"{action.label}  ->  {action.count:g}"
            )
            item.setData(QtCore.Qt.UserRole, index)
            self._list_widget.addItem(item)
        if self._list_widget.count():
            self._list_widget.setCurrentRow(0)

    def set_actions(self, actions: Iterable[NineGridAction]) -> None:
        self._actions = list(actions)
        self._populate()

    def _move_item(self, offset: int) -> None:
        if self._list_widget is None:
            return
        row = self._list_widget.currentRow()
        if row < 0:
            return
        new_row = row + offset
        if new_row < 0 or new_row >= self._list_widget.count():
            return
        item = self._list_widget.takeItem(row)
        self._list_widget.insertItem(new_row, item)
        self._list_widget.setCurrentRow(new_row)

    def ordered_actions(self) -> List[NineGridAction]:
        if self._list_widget is None:
            return list(self._actions)
        actions: List[NineGridAction] = []
        for index in range(self._list_widget.count()):
            item = self._list_widget.item(index)
            action_index = item.data(QtCore.Qt.UserRole)
            if isinstance(action_index, int) and 0 <= action_index < len(self._actions):
                actions.append(self._actions[action_index])
        return actions
