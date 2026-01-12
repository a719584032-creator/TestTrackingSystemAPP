"""Tree-based combo box for selecting case group paths."""
from __future__ import annotations

from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from models import GroupTreeNode


class DirectoryTreeCombo(QtWidgets.QWidget):
    """Tree dropdown selector with single-click expand and double-click select."""

    currentDataChanged = QtCore.pyqtSignal(object)

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        all_label: str = "All Groups",
        ungrouped_label: str = "Ungrouped",
    ) -> None:
        super().__init__(parent)
        self._all_label = all_label
        self._ungrouped_label = ungrouped_label
        self._ungrouped_value = "__ungrouped__"
        self._current_data: Optional[str] = None

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._display = QtWidgets.QLineEdit(self)
        self._display.setReadOnly(True)
        self._display.setFocusPolicy(QtCore.Qt.NoFocus)
        self._display.setCursor(QtCore.Qt.ArrowCursor)
        self._display.setText(self._all_label)

        self._button = QtWidgets.QToolButton(self)
        self._button.setArrowType(QtCore.Qt.DownArrow)
        self._button.setCursor(QtCore.Qt.PointingHandCursor)
        self._button.clicked.connect(self._toggle_popup)

        layout.addWidget(self._display, stretch=1)
        layout.addWidget(self._button)

        self._popup = QtWidgets.QFrame(self, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        popup_layout = QtWidgets.QVBoxLayout(self._popup)
        popup_layout.setContentsMargins(0, 0, 0, 0)
        popup_layout.setSpacing(0)

        self._tree = QtWidgets.QTreeWidget(self._popup)
        self._tree.setHeaderHidden(True)
        self._tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._tree.setUniformRowHeights(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(18)
        self._tree.setExpandsOnDoubleClick(False)
        popup_layout.addWidget(self._tree)

        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._display.installEventFilter(self)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if obj is self._display and event.type() == QtCore.QEvent.MouseButtonPress:
            if self.isEnabled():
                self._show_popup()
            return True
        return super().eventFilter(obj, event)

    def currentData(self) -> Optional[str]:
        return self._current_data

    def currentText(self) -> str:
        return self._display.text()

    def currentToolTip(self) -> str:
        return self._display.toolTip()

    def clear(self) -> None:
        self._tree.clear()
        self._set_current(self._all_label, None, "")

    def set_group_tree(self, root: Optional[GroupTreeNode]) -> None:
        self._tree.clear()
        all_item = QtWidgets.QTreeWidgetItem([self._all_label])
        all_item.setData(0, QtCore.Qt.UserRole, None)
        all_item.setData(0, QtCore.Qt.UserRole + 1, self._all_label)
        self._tree.addTopLevelItem(all_item)

        nodes = []
        if root:
            if str(root.name).strip().lower() == "root" and root.children:
                nodes = root.children
            else:
                nodes = [root]
        for node in nodes:
            self._append_group_node(node, parent_item=None, parent_path="")

        self._tree.expandToDepth(1)
        self._set_current(self._all_label, None, "")

    def setCurrentData(self, value: Optional[str]) -> None:
        if value is None:
            self._set_current(self._all_label, None, "")
            self._tree.setCurrentItem(self._tree.topLevelItem(0))
            if not self.signalsBlocked():
                self.currentDataChanged.emit(self._current_data)
            return
        item = self._find_item_by_data(value)
        if item is None:
            self._set_current(self._all_label, None, "")
            if not self.signalsBlocked():
                self.currentDataChanged.emit(self._current_data)
            return
        display_label = item.data(0, QtCore.Qt.UserRole + 1) or item.text(0)
        tooltip = item.toolTip(0)
        self._set_current(display_label, value, tooltip)
        self._tree.setCurrentItem(item)
        if not self.signalsBlocked():
            self.currentDataChanged.emit(self._current_data)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._popup.isVisible():
            self._popup.setFixedWidth(self.width())

    def _toggle_popup(self) -> None:
        if self._popup.isVisible():
            self._popup.hide()
        else:
            self._show_popup()

    def _show_popup(self) -> None:
        if self._popup.isVisible():
            return
        popup_height = 320
        self._popup.setFixedWidth(self.width())
        self._popup.resize(self.width(), popup_height)
        position = self.mapToGlobal(QtCore.QPoint(0, self.height()))
        self._popup.move(position)
        self._popup.show()
        self._popup.raise_()

    def _on_item_clicked(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        if item.childCount() > 0:
            item.setExpanded(not item.isExpanded())

    def _on_item_double_clicked(
        self, item: QtWidgets.QTreeWidgetItem, _column: int
    ) -> None:
        value = item.data(0, QtCore.Qt.UserRole)
        display_label = item.data(0, QtCore.Qt.UserRole + 1) or item.text(0)
        tooltip = item.toolTip(0)
        self._set_current(display_label, value, tooltip)
        self._popup.hide()
        if not self.signalsBlocked():
            self.currentDataChanged.emit(self._current_data)

    def _set_current(self, label: str, value: Optional[str], tooltip: str) -> None:
        self._current_data = value
        self._display.setText(label)
        self._display.setToolTip(tooltip)
        self.setToolTip(tooltip)

    def _append_group_node(
        self,
        node: GroupTreeNode,
        *,
        parent_item: Optional[QtWidgets.QTreeWidgetItem],
        parent_path: str,
    ) -> None:
        label, value = self._normalize_node(node)
        if not label:
            return
        display_path = f"{parent_path}/{label}" if parent_path else label
        display_label = self._compact_label(display_path)

        item = QtWidgets.QTreeWidgetItem([label])
        item.setData(0, QtCore.Qt.UserRole, value)
        item.setData(0, QtCore.Qt.UserRole + 1, display_label)
        item.setToolTip(0, display_path)

        if parent_item is None:
            self._tree.addTopLevelItem(item)
        else:
            parent_item.addChild(item)

        for child in node.children:
            self._append_group_node(child, parent_item=item, parent_path=display_path)

    def _normalize_node(self, node: GroupTreeNode) -> tuple[str, Optional[str]]:
        name = str(node.name or "").strip()
        path = str(node.path or "").strip()
        normalized_name = self._map_ungrouped_label(name)
        normalized_path = self._map_ungrouped_value(path)
        if normalized_name == self._ungrouped_label:
            return normalized_name, self._ungrouped_value
        if normalized_path == self._ungrouped_value:
            return self._ungrouped_label, self._ungrouped_value
        label = normalized_name or path
        value = normalized_path or path or normalized_name
        return label, value

    def _map_ungrouped_label(self, value: str) -> str:
        if self._is_ungrouped_value(value):
            return self._ungrouped_label
        return value

    def _map_ungrouped_value(self, value: str) -> str:
        if self._is_ungrouped_value(value):
            return self._ungrouped_value
        return value

    def _is_ungrouped_value(self, value: str) -> bool:
        normalized = value.strip().lower()
        return normalized in {"__ungrouped__", "ungrouped", "__none__", "none", self._ungrouped_label}

    def _find_item_by_data(
        self, value: Optional[str]
    ) -> Optional[QtWidgets.QTreeWidgetItem]:
        if value is None:
            return None

        def walk(item: QtWidgets.QTreeWidgetItem) -> Optional[QtWidgets.QTreeWidgetItem]:
            if item.data(0, QtCore.Qt.UserRole) == value:
                return item
            if item.toolTip(0) == value:
                return item
            if item.data(0, QtCore.Qt.UserRole + 1) == value:
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None

        for index in range(self._tree.topLevelItemCount()):
            found_item = walk(self._tree.topLevelItem(index))
            if found_item is not None:
                return found_item
        return None

    def _compact_label(self, value: str) -> str:
        if not value or value == self._ungrouped_label:
            return value
        max_length = 48
        if len(value) <= max_length:
            return value
        parts = value.split("/")
        if len(parts) <= 2:
            return f"{value[: max_length - 3]}..."
        tail = "/".join(parts[-2:])
        label = f".../{tail}"
        if len(label) <= max_length:
            return label
        return f".../{tail[-(max_length - 4):]}"
