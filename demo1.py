# -*- coding: utf-8 -*-
import sys
from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QModelIndex
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QLineEdit, QMenu, QWidgetAction, QTreeWidget, QTreeWidgetItem,
    QFrame, QStyle, QStyleOptionViewItem
)


class PopupTreeWidget(QTreeWidget):
    """
    弹出用目录树（稳定版）：
    - 点击“文本区域”：确认（textClicked）
    - 点击“文本左侧区域”（含三角/缩进空白）：仅展开/收起，不确认
    """
    textClicked = pyqtSignal(QTreeWidgetItem)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setIndentation(20)
        self.setExpandsOnDoubleClick(False)
        self.setItemsExpandable(True)
        self.setRootIsDecorated(True)
        self.setSelectionBehavior(self.SelectRows)

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if item is None:
            return super().mousePressEvent(event)

        index = self.indexFromItem(item, 0)
        if not index.isValid():
            return super().mousePressEvent(event)

        # 只用“文本矩形”来判定：左侧=展开区，右侧=文本确认区
        text_left = self._text_rect_left(index)

        # 点击在文本左边（含三角/缩进）：只展开/收起
        if event.pos().x() < text_left and self.model().hasChildren(index):
            item.setExpanded(not item.isExpanded())
            event.accept()
            return

        # 否则：当作点击文本/右侧区域 -> 确认
        super().mousePressEvent(event)
        self.textClicked.emit(item)

    def _text_rect_left(self, index: QModelIndex) -> int:
        """
        计算该 item “文本区域”的左边界 x（viewport 坐标）。
        这是 Qt style 最可靠的区域之一，比 disclosure 三角区域稳定得多。
        """
        opt = self.viewOptions()
        opt.rect = self.visualRect(index)

        text_rect = self.style().subElementRect(QStyle.SE_ItemViewItemText, opt, self.viewport())

        # 有些主题下 text_rect 可能非常靠左或宽度异常，这里加个兜底：
        # 至少保证阈值不会小于行矩形 left
        row_rect = opt.rect
        return max(text_rect.left(), row_rect.left() + 4)




class TreeFilterComboLike(QWidget):
    """
    一个“像下拉筛选框”的控件：QLineEdit + QMenu(QWidgetAction + QTreeWidget)
    """
    selected = pyqtSignal(str, object)  # path_text, user_data

    def __init__(self, placeholder="全部目录", parent=None):
        super().__init__(parent)

        self.line = QLineEdit(self)
        self.line.setReadOnly(True)
        self.line.setPlaceholderText(placeholder)

        # 弹层菜单
        self.menu = QMenu(self.line)
        self.menu.setFocusPolicy(Qt.NoFocus)

        # 容器面板
        self.panel = QWidget(self.menu)
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(8, 8, 8, 8)

        # 树控件
        self.tree = PopupTreeWidget(self.panel)
        layout.addWidget(self.tree)

        act = QWidgetAction(self.menu)
        act.setDefaultWidget(self.panel)
        self.menu.addAction(act)

        # 事件：点输入框任意位置弹出
        self.line.installEventFilter(self)

        # 事件：点文字确认
        self.tree.textClicked.connect(self._confirm_item)

        # 默认大小
        self.panel.setMinimumHeight(260)

    def eventFilter(self, obj, event):
        if obj is self.line and event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self.showPopup()
            return True
        return super().eventFilter(obj, event)

    def showPopup(self):
        # 默认全部收缩
        self.tree.collapseAll()

        # 宽度跟随输入框
        self.panel.setMinimumWidth(self.line.width())

        # 弹出在输入框下方
        p = self.line.mapToGlobal(self.line.rect().bottomLeft())
        self.menu.popup(p)

    def clearTree(self):
        self.tree.clear()

    def setTreeFromNestedDict(self, nested: dict):
        """
        nested 例子：
        {
          "Cleansheet keyboard": {},
          "测试": {
             "Cleansheet keyboard": {
                "01 Keyboard Test information": {
                   "Preparation": {},
                   "dongle开机检查": {}
                }
             }
          }
        }
        """
        self.clearTree()

        def add_children(parent_item, d, parent_path=""):
            for name, child in d.items():
                item = QTreeWidgetItem([name])
                # 你可以在这里存业务 value（比如 group_path、id 等）
                # 演示存完整路径（不含 root 前缀，你也可以自己改）
                cur_path = f"{parent_path}/{name}" if parent_path else name
                item.setData(0, Qt.UserRole, {"value": cur_path, "label": name})
                if parent_item is None:
                    self.tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)

                if isinstance(child, dict) and child:
                    add_children(item, child, cur_path)

        add_children(None, nested)
        self.tree.collapseAll()  # 默认收缩

    def _confirm_item(self, item: QTreeWidgetItem):
        path_text = self._build_path(item)
        data = item.data(0, Qt.UserRole)

        self.line.setText(path_text)
        self.selected.emit(path_text, data)
        self.menu.close()

    def _build_path(self, item: QTreeWidgetItem) -> str:
        parts = []
        cur = item
        while cur is not None:
            parts.append(cur.text(0))
            cur = cur.parent()
        return " / ".join(reversed(parts))


# ---------------- Demo ----------------
class Demo(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("目录筛选框（QTreeWidget）Demo")

        layout = QVBoxLayout(self)
        self.label = QLabel("当前筛选：全部目录")
        layout.addWidget(self.label)

        self.tree_select = TreeFilterComboLike("全部目录", self)
        layout.addWidget(self.tree_select.line)

        data = {
            "Cleansheet keyboard": {},
            "测试": {
                "Cleansheet keyboard": {
                    "01 Keyboard Test information": {
                        "Preparation": {},
                        "dongle开机检查": {},
                        "系统信息检查": {},
                        "蓝牙开机检查": {},
                    }
                },
                "测试2": {
                    "Cleansheet keyboard": {}
                }
            }
        }
        self.tree_select.setTreeFromNestedDict(data)
        self.tree_select.selected.connect(self.on_selected)

    def on_selected(self, path, data):
        self.label.setText(f"当前筛选：{path}   |   data={data}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Demo()
    w.resize(620, 220)
    w.show()
    sys.exit(app.exec_())
