# -*- coding: utf-8 -*-
"""
Windows 客户端 - 用例管理界面（前端原型 / 更新版）
- 变化：
  1) 用例目录改为下拉框
  2) 计划总览优化，状态从“后端返回”（此处用假数据模拟），选择计划后自动刷新
  3) 补充假数据，便于查看效果
"""
import sys
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QSplitter, QTreeWidget, QTreeWidgetItem, QGroupBox,
    QFormLayout, QTextEdit, QPlainTextEdit, QListWidget, QListWidgetItem, QGridLayout,
    QFrame
)

# ---------------- 演示用“后端返回”数据（仅模拟） ----------------
PLAN_DATA = {
    "10月回归-第一期": {
        "status": "进行中",      # 可能值：未开始、进行中、挂起、已完成
        "period": "2025-10-15 ~ 2025-10-31",
        "testers": ["Alice", "Bob", "李雷"],
        "stats": {"total": 128, "executed": 76, "pass": 62, "fail": 9, "block": 5, "notrun": 52}
    },
    "10月回归-第二期": {
        "status": "未开始",
        "period": "2025-10-22 ~ 2025-11-05",
        "testers": ["王芳", "Tom"],
        "stats": {"total": 84, "executed": 0, "pass": 0, "fail": 0, "block": 0, "notrun": 84}
    },
    "稳定性专项-夜测A": {
        "status": "挂起",
        "period": "2025-10-10 ~ 2025-10-25",
        "testers": ["Chen", "Han"],
        "stats": {"total": 60, "executed": 41, "pass": 30, "fail": 6, "block": 5, "notrun": 19}
    },
    "版本验收-RC1": {
        "status": "已完成",
        "period": "2025-09-28 ~ 2025-10-08",
        "testers": ["QA-Team"],
        "stats": {"total": 150, "executed": 150, "pass": 142, "fail": 5, "block": 3, "notrun": 0}
    },
}

# 目录 -> 用例树假数据
DIR_CASES = {
    "全部目录": {
        "Bluetooth": [
            ("[S3+5] BT Pairing multi devices", "通过"),
            ("[S4+6] BT Reconnect after reboot", "失败"),
            ("[S5+3] BLE Scan Stability", "未执行"),
        ],
        "Wi-Fi": [
            ("[W2+10] 2.4G roaming handover", "通过"),
            ("[W3+2]  5G throughput stress", "阻塞"),
        ],
        "Audio": [
            ("[A1+4] Playback latency under load", "通过"),
            ("[A2+7] Mic noise suppression", "未执行"),
        ]
    },
    "Bluetooth": {
        "Bluetooth": [
            ("[S3+5] BT Pairing multi devices", "通过"),
            ("[S4+6] BT Reconnect after reboot", "失败"),
            ("[S5+3] BLE Scan Stability", "未执行"),
        ]
    },
    "Wi-Fi": {
        "Wi-Fi": [
            ("[W2+10] 2.4G roaming handover", "通过"),
            ("[W3+2]  5G throughput stress", "阻塞"),
        ]
    },
    "Audio": {
        "Audio": [
            ("[A1+4] Playback latency under load", "通过"),
            ("[A2+7] Mic noise suppression", "未执行"),
        ]
    }
}

# 计划状态 -> 颜色
STATUS_COLOR = {
    "未开始": "#6B7280",
    "进行中": "#10B981",
    "挂起":   "#F59E0B",
    "已完成": "#2563EB",
}

class Pill(QLabel):
    """统计胶囊"""
    def __init__(self, title: str, value: str, bg="#EEF2FF", fg="#1E3A8A"):
        super().__init__(f"{title}\n{value}")
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border-radius: 12px;
                padding: 8px 12px;
                font-weight: 600;
            }}
        """)

class Tag(QLabel):
    """状态标签（颜色由后端状态映射）"""
    def __init__(self, text="未选择", color="#6B7280"):
        super().__init__(text)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(22)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color}22;
                color: {color};
                border: 1px solid {color};
                border-radius: 11px;
                padding: 0 8px;
                font-size: 11px;
            }}
        """)

    def set_color(self, hex_color: str):
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {hex_color}22;
                color: {hex_color};
                border: 1px solid {hex_color};
                border-radius: 11px;
                padding: 0 8px;
                font-size: 11px;
            }}
        """)

class CaseDetail(QWidget):
    """右侧详情面板"""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        # 用例详情
        box = QGroupBox("用例详情")
        form = QFormLayout()
        self.titleEdit = QLineEdit(); self.titleEdit.setReadOnly(True)
        self.preEdit = QTextEdit(); self.preEdit.setReadOnly(True); self.preEdit.setFixedHeight(70)
        self.stepEdit = QTextEdit(); self.stepEdit.setReadOnly(True); self.stepEdit.setFixedHeight(160)
        self.expectEdit = QTextEdit(); self.expectEdit.setReadOnly(True); self.expectEdit.setFixedHeight(100)
        form.addRow("用例标题：", self.titleEdit)
        form.addRow("前置条件：", self.preEdit)
        form.addRow("执行步骤：", self.stepEdit)
        form.addRow("预期结果：", self.expectEdit)
        box.setLayout(form)

        # 下方：监控动作 + 日志输出
        lower = QSplitter(Qt.Horizontal)
        monBox = QGroupBox("监控动作（预留）")
        monLayout = QVBoxLayout()
        self.monitorList = QListWidget()
        for t in ["启动进程监控", "抓取性能指标", "截取关键帧", "抓取异常弹窗"]:
            QListWidgetItem(QIcon(), t, self.monitorList)
        monLayout.addWidget(self.monitorList)
        monBox.setLayout(monLayout)

        logBox = QGroupBox("日志输出（预留）")
        logLayout = QVBoxLayout()
        self.logEdit = QPlainTextEdit(); self.logEdit.setReadOnly(True)
        self.logEdit.setPlaceholderText("这里显示执行时采集的日志 / 关键步骤输出 ...")
        logLayout.addWidget(self.logEdit)
        logBox.setLayout(logLayout)

        lower.addWidget(monBox)
        lower.addWidget(logBox)
        lower.setStretchFactor(0, 3)
        lower.setStretchFactor(1, 5)

        layout.addWidget(box)
        layout.addWidget(lower)

class PlanOverview(QWidget):
    """计划总览：状态(后端返回)、周期、测试人员、执行统计"""
    def __init__(self):
        super().__init__()
        wrap = QGroupBox("计划总览")
        grid = QGridLayout()

        # 行1：状态 / 周期 / 人员
        self.statusTag = Tag("未选择", STATUS_COLOR["未开始"])
        self.periodVal = QLabel("—")
        self.testerVal = QLabel("—")
        grid.addWidget(QLabel("计划状态："), 0, 0)
        grid.addWidget(self.statusTag, 0, 1)
        grid.addWidget(QLabel("时间周期："), 0, 2)
        grid.addWidget(self.periodVal, 0, 3)
        grid.addWidget(QLabel("测试人员："), 0, 4)
        grid.addWidget(self.testerVal, 0, 5)

        # 行2：统计胶囊
        self.pill_total = Pill("总数", "0")
        self.pill_exec  = Pill("已执行", "0", "#ECFEFF", "#155E75")
        self.pill_pass  = Pill("通过", "0", "#ECFDF5", "#065F46")
        self.pill_fail  = Pill("失败", "0", "#FEF2F2", "#7F1D1D")
        self.pill_block = Pill("阻塞", "0", "#FFF7ED", "#7C2D12")
        self.pill_not   = Pill("未执行", "0", "#F5F3FF", "#5B21B6")

        statRow = QHBoxLayout()
        for w in [self.pill_total, self.pill_exec, self.pill_pass, self.pill_fail, self.pill_block, self.pill_not]:
            w.setFixedHeight(54); w.setFixedWidth(110)
            statRow.addWidget(w)
        statRow.addStretch(1)
        grid.addLayout(statRow, 1, 0, 1, 6)

        wrap.setLayout(grid)
        lay = QVBoxLayout(self)
        lay.addWidget(wrap)

    def apply_backend_data(self, plan_name: str):
        """模拟后端：根据选择的计划刷新总览"""
        data = PLAN_DATA.get(plan_name)
        if not data:
            self.statusTag.setText("未选择")
            self.statusTag.set_color(STATUS_COLOR["未开始"])
            self.periodVal.setText("—")
            self.testerVal.setText("—")
            for w in [self.pill_total, self.pill_exec, self.pill_pass, self.pill_fail, self.pill_block, self.pill_not]:
                title = w.text().split("\n")[0]
                w.setText(f"{title}\n0")
            return

        status = data["status"]
        color = STATUS_COLOR.get(status, "#6B7280")
        self.statusTag.setText(status)
        self.statusTag.set_color(color)
        self.periodVal.setText(data["period"])
        self.testerVal.setText(" / ".join(data["testers"]))

        st = data["stats"]
        self.pill_total.setText(f"总数\n{st['total']}")
        self.pill_exec.setText(f"已执行\n{st['executed']}")
        self.pill_pass.setText(f"通过\n{st['pass']}")
        self.pill_fail.setText(f"失败\n{st['fail']}")
        self.pill_block.setText(f"阻塞\n{st['block']}")
        self.pill_not.setText(f"未执行\n{st['notrun']}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("用例管理客户端 - 原型（PyQt5/更新版）")
        self.resize(1320, 820)
        self.setWindowIcon(QIcon())

        # ---- 全局样式 ----
        self.setStyleSheet("""
            QMainWindow { background: #FBFBFD; }
            QLabel { color: #111827; font-size: 13px; }
            QGroupBox {
                font-weight: 600; border: 1px solid #E5E7EB; border-radius: 10px;
                margin-top: 10px; padding: 12px; background: #FFFFFF;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
            QComboBox, QLineEdit, QTextEdit, QPlainTextEdit, QTreeWidget {
                border: 1px solid #E5E7EB; border-radius: 8px; background: #FFFFFF;
            }
            QTreeWidget::item { height: 26px; }
            QPushButton {
                background: #111827; color: white; border-radius: 10px; padding: 8px 16px; font-weight: 600;
            }
            QPushButton:hover { background: #374151; }
            QPushButton#ghost { background: #F3F4F6; color: #111827; border: 1px solid #E5E7EB; }
            QFrame#line { background: #E5E7EB; max-height: 1px; }
        """)

        central = QWidget()
        root = QVBoxLayout(central)

        # ---- 顶部筛选条 ----
        filterBar = QGroupBox("筛选")
        f = QHBoxLayout()
        self.depCmb   = self._cmb(["— 请选择部门 —", "QA", "研发", "运维"])
        self.projCmb  = self._cmb(["— 请选择项目 —", "Apollo", "Hermes", "Taurus"])
        self.planCmb  = self._cmb(["— 请选择计划 —"] + list(PLAN_DATA.keys()))
        self.modelCmb = self._cmb(["— 请选择机型 —", "Model-A", "Model-B", "Model-C"])
        self.dirCmb   = self._cmb(["全部目录"] + [d for d in DIR_CASES.keys() if d != "全部目录"])
        self.resultCmb= self._cmb(["全部结果", "通过", "失败", "阻塞", "未执行"])
        self.searchEdit = QLineEdit(); self.searchEdit.setPlaceholderText("标题关键字（可选）")

        def add(label, w, wfix):
            f.addWidget(QLabel(label)); w.setFixedWidth(wfix); f.addWidget(w)
        add("部门", self.depCmb, 160)
        add("项目", self.projCmb, 160)
        add("计划", self.planCmb, 200)
        add("机型", self.modelCmb, 140)
        add("目录", self.dirCmb, 140)
        add("结果", self.resultCmb, 120)
        f.addWidget(self.searchEdit)
        f.addStretch(1)

        self.applyBtn = QPushButton("应用筛选"); self.applyBtn.setObjectName("ghost")
        self.applyBtn.clicked.connect(self.on_apply_filters)
        f.addWidget(self.applyBtn)
        filterBar.setLayout(f)

        # ---- 计划总览（状态由“后端返回”） ----
        self.planOverview = PlanOverview()

        # ---- 中部：左树右详情 ----
        splitMain = QSplitter(Qt.Horizontal)
        # 左：用例树
        leftBox = QGroupBox("用例目录 / 标题")
        leftLay = QVBoxLayout()
        self.caseTree = QTreeWidget()
        self.caseTree.setHeaderLabels(["标题", "结果"])
        self.caseTree.header().setStretchLastSection(False)
        self.caseTree.header().setSectionResizeMode(0, self.caseTree.header().Stretch)
        self.caseTree.header().setSectionResizeMode(1, self.caseTree.header().ResizeToContents)
        self.caseTree.itemSelectionChanged.connect(self.on_case_selected)
        leftLay.addWidget(self.caseTree)
        leftBox.setLayout(leftLay)

        # 右：详情
        self.detailPanel = CaseDetail()

        splitMain.addWidget(leftBox)
        splitMain.addWidget(self.detailPanel)
        splitMain.setStretchFactor(0, 4)
        splitMain.setStretchFactor(1, 6)

        # ---- 底部操作按钮 ----
        line = QFrame(); line.setObjectName("line"); line.setFrameShape(QFrame.HLine)
        actionBar = QHBoxLayout()
        self.startBtn = QPushButton("开始执行")
        self.passBtn  = QPushButton("通过")
        self.failBtn  = QPushButton("失败")
        self.blockBtn = QPushButton("阻塞")
        for b in [self.startBtn, self.passBtn, self.failBtn, self.blockBtn]:
            b.setFixedHeight(40); b.setFixedWidth(120)
        actionBar.addStretch(1)
        actionBar.addWidget(self.startBtn)
        actionBar.addWidget(self.passBtn)
        actionBar.addWidget(self.failBtn)
        actionBar.addWidget(self.blockBtn)

        # ---- 组装 ----
        root.addWidget(filterBar)
        root.addWidget(self.planOverview)
        root.addWidget(splitMain, 1)
        root.addWidget(line)
        root.addLayout(actionBar)
        self.setCentralWidget(central)

        # 初始占位：引导选择
        self._set_placeholder_tree()

        # 绑定：四个联动 + 目录变化时刷新用例；计划变化时刷新“后端状态”
        self.depCmb.currentIndexChanged.connect(self.on_filters_changed)
        self.projCmb.currentIndexChanged.connect(self.on_filters_changed)
        self.planCmb.currentIndexChanged.connect(self.on_filters_changed)
        self.modelCmb.currentIndexChanged.connect(self.on_filters_changed)
        self.dirCmb.currentIndexChanged.connect(self.on_filters_changed)

    # ---------------- 辅助方法 ----------------
    def _cmb(self, items):
        cmb = QComboBox(); cmb.addItems(items); return cmb

    def _set_placeholder_tree(self):
        self.caseTree.clear()
        root = QTreeWidgetItem(["（请选择：部门 / 项目 / 计划 / 机型 后展示用例）", ""])
        self.caseTree.addTopLevelItem(root)
        self.caseTree.expandAll()

    def _populate_cases_from_dir(self, dir_name: str, result_filter: str, keyword: str):
        """根据目录/结果/关键字展示树"""
        self.caseTree.clear()
        data = DIR_CASES.get(dir_name, {})
        if dir_name == "全部目录":
            data = DIR_CASES["全部目录"]

        total_items = 0
        for folder, cases in data.items():
            parent = QTreeWidgetItem([folder, ""])
            children = []
            for title, res in cases:
                if result_filter != "全部结果" and res != result_filter:
                    continue
                if keyword and keyword.lower() not in title.lower():
                    continue
                children.append(QTreeWidgetItem([title, res]))
            if children:
                parent.addChildren(children)
                self.caseTree.addTopLevelItem(parent)
                total_items += len(children)

        if total_items == 0:
            self.caseTree.addTopLevelItem(QTreeWidgetItem(["（无匹配用例）", ""]))

        self.caseTree.expandAll()

    # ---------------- 事件处理 ----------------
    def on_filters_changed(self):
        """四个必选项都选择后，展示用例；计划更改时刷新总览（状态来自后端）"""
        # 计划总览：由“后端返回” -> 根据当前计划刷新
        plan_name = self.planCmb.currentText()
        if plan_name in PLAN_DATA:
            self.planOverview.apply_backend_data(plan_name)
        else:
            self.planOverview.apply_backend_data(None)

        # 用例树：前四个都已选择才展示
        ready = all([
            self.depCmb.currentIndex() > 0,
            self.projCmb.currentIndex() > 0,
            self.planCmb.currentIndex() > 0,
            self.modelCmb.currentIndex() > 0
        ])
        if ready:
            self._populate_cases_from_dir(
                self.dirCmb.currentText(),
                self.resultCmb.currentText(),
                self.searchEdit.text().strip()
            )
        else:
            self._set_placeholder_tree()

    def on_apply_filters(self):
        self.on_filters_changed()

    def on_case_selected(self):
        items = self.caseTree.selectedItems()
        if not items: return
        item = items[0]
        if item.childCount() > 0:  # 目录节点
            return

        title = item.text(0); result = item.text(1)
        # 填充右侧详情（示例内容）
        self.detailPanel.titleEdit.setText(title)
        self.detailPanel.preEdit.setPlainText("1) 蓝牙已开启；2) 设备可发现；3) 清空历史配对记录。")
        self.detailPanel.stepEdit.setPlainText(
            "步骤：\n"
            "1. 在设置中打开蓝牙\n"
            "2. 扫描附近设备并选择目标\n"
            "3. 输入配对码或确认指纹\n"
            "4. 验证连接并进行简单传输测试"
        )
        self.detailPanel.expectEdit.setPlainText(
            "期望：\n"
            "- 设备在 10 秒内发现并显示目标\n"
            "- 配对成功且连接稳定，文件传输成功\n"
            "- 重启后自动重连"
        )
        self.detailPanel.logEdit.setPlainText(
            f"[INFO] Selected: {title} | Result: {result}\n"
            "[INFO] Logs will appear here while executing..."
        )

def main():
    app = QApplication(sys.argv)
    font = QFont("Microsoft YaHei UI", 9)
    app.setFont(font)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
