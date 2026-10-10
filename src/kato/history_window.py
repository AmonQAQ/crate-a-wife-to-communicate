"""聊天记录浏览窗口：按时间查看历史消息，支持搜索与模式筛选。"""
from datetime import datetime

from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout,
)


class HistoryWindow(QDialog):
    def __init__(self, db, personas=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.personas = personas or []
        self._pid_name = {p["id"]: p.get("short", p["name"]) for p in self.personas}
        self._loaded = 0
        self._batch = 200
        self.setWindowTitle("聊天记录")
        self.resize(560, 640)
        self._build()
        self._refresh()

    def _build(self):
        self.setStyleSheet("""
            QWidget { background: #fff5f7; font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
                      color: #4a2b32; }
            QListWidget { background: #ffffff; border: 1px solid #ffd9e0; border-radius: 8px; padding: 4px; }
            QListWidget::item { padding: 8px 6px; border-bottom: 1px solid #ffeef2; }
            QListWidget::item:selected { background: #ffe4e9; color: #c2546b; }
            QLineEdit, QComboBox { background: #ffffff; border: 1px solid #ffd9e0;
                                   border-radius: 6px; padding: 5px; }
            QLineEdit:focus, QComboBox:focus { border: 1px solid #ff7d95; }
            QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #ffd9e0;
                                          selection-background-color: #ffe4e9; }
            QPushButton { background: #ff5f7e; color: white; border: none;
                          border-radius: 6px; padding: 6px 14px; }
            QPushButton:hover { background: #f0486b; }
            QPushButton:disabled { background: #f7c9d2; color: #ffffff; }
            QLabel { background: transparent; }
        """)
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索聊天记录…")
        self.search.textChanged.connect(self._refresh)
        top.addWidget(self.search, 1)
        self.mode_box = QComboBox()
        self.mode_box.addItem("全部", None)
        for p in self.personas:
            self.mode_box.addItem(p.get("short", p["name"]), p["id"])
        self.mode_box.currentIndexChanged.connect(self._refresh)
        top.addWidget(self.mode_box)
        root.addLayout(top)

        self.listw = QListWidget()
        root.addWidget(self.listw, 1)

        bottom = QHBoxLayout()
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color:#d99aa6;")
        bottom.addWidget(self.count_label)
        bottom.addStretch()
        self.more_btn = QPushButton("加载更多")
        self.more_btn.clicked.connect(self._load_more)
        bottom.addWidget(self.more_btn)
        root.addLayout(bottom)

    def _refresh(self):
        self._loaded = 0
        self.listw.clear()
        self._load_more()

    def _load_more(self):
        kw = self.search.text().strip()
        mode = self.mode_box.currentData()
        rows = self.db.search_messages(keyword=kw, mode=mode,
                                       offset=self._loaded, limit=self._batch)
        if self._loaded == 0:
            self.count_label.setText(f"共 {self.db.count_messages()} 条" if not kw else f"匹配 {len(rows)} 条")
        if not rows:
            if self._loaded == 0:
                self.listw.addItem(QListWidgetItem("（暂无聊天记录）"))
            self.more_btn.setEnabled(False)
            return
        for r in rows:
            t = datetime.fromtimestamp(r["ts"]).strftime("%m-%d %H:%M")
            role = "我" if r["role"] == "user" else self._pid_name.get(r["mode"], "对方")
            content = (r["content"] or "").replace("\n", " ")
            preview = content[:48] + ("…" if len(content) > 48 else "")
            item = QListWidgetItem(f"{t}  {role}：{preview}")
            item.setToolTip(content)
            self.listw.addItem(item)
        self._loaded += len(rows)
        self.more_btn.setEnabled(len(rows) == self._batch)
