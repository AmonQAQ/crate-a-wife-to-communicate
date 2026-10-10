"""系统面板：调整所有可配置项。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from . import startup, persona


class PanelWindow(QDialog):
    saved = Signal()

    def __init__(self, config, db, parent=None):
        super().__init__(parent)
        self.config = config
        self.db = db
        self.setWindowTitle("系统面板 · 加藤惠")
        self.resize(640, 620)
        self._edits = {}
        self._build()
        self._load()

    # ---------------- 控件助手 ----------------
    def _line(self, lay, section, key, label, placeholder="", password=False):
        e = QLineEdit()
        e.setPlaceholderText(placeholder)
        if password:
            e.setEchoMode(QLineEdit.Password)
        lay.addRow(label, e)
        self._edits[(section, key)] = e
        return e

    def _combo(self, lay, section, key, label, items):
        c = QComboBox()
        for it in items:
            if isinstance(it, tuple):
                c.addItem(it[0], it[1])
            else:
                c.addItem(it)
        lay.addRow(label, c)
        self._edits[(section, key)] = c
        return c

    def _check(self, lay, section, key, label):
        c = QCheckBox(label)
        lay.addRow("", c)
        self._edits[(section, key)] = c
        return c

    def _spin(self, lay, section, key, label, lo=1, hi=100000):
        s = QSpinBox()
        s.setRange(lo, hi)
        lay.addRow(label, s)
        self._edits[(section, key)] = s
        return s

    def _dspin(self, lay, section, key, label, lo=0.0, hi=2.0, step=0.05):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setSingleStep(step)
        s.setDecimals(2)
        lay.addRow(label, s)
        self._edits[(section, key)] = s
        return s

    def _file(self, lay, section, key, label):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        e = QLineEdit()
        b = QPushButton("浏览")
        h.addWidget(e, 1)
        h.addWidget(b)
        lay.addRow(label, row)
        self._edits[(section, key)] = e
        b.clicked.connect(lambda _=False, edit=e: self._pick(edit))
        return e

    def _pick(self, edit):
        f, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if f:
            edit.setText(f)

    def _dir(self, lay, section, key, label):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        e = QLineEdit()
        b = QPushButton("浏览")
        h.addWidget(e, 1)
        h.addWidget(b)
        lay.addRow(label, row)
        self._edits[(section, key)] = e
        b.clicked.connect(lambda _=False, edit=e: self._pick_dir(edit))
        return e

    def _pick_dir(self, edit):
        d = QFileDialog.getExistingDirectory(self, "选择头像文件夹")
        if d:
            edit.setText(d)

    # ---------------- 构建 ----------------
    def _build(self):
        self.setStyleSheet("""
            QWidget { background: #fff5f7; font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
                      color: #4a2b32; font-size: 13px; }
            QTabWidget::pane { background: #ffffff; border: 1px solid #ffd9e0; border-radius: 8px; }
            QTabBar::tab { background: #ffe4e9; color: #c9858f; padding: 7px 16px;
                           border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }
            QTabBar::tab:selected { background: #ff5f7e; color: white; }
            QLineEdit, QComboBox, QSpinBox { background: #ffffff; border: 1px solid #ffd9e0;
                                             border-radius: 6px; padding: 4px 6px; }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #ff7d95; }
            QPushButton { background: #ff5f7e; color: white; border: none;
                          border-radius: 6px; padding: 6px 16px; }
            QPushButton:hover { background: #f0486b; }
            QCheckBox { background: transparent; }
            QListWidget { background: #ffffff; border: 1px solid #ffd9e0; border-radius: 6px; }
        """)
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # 大模型
        t1 = QWidget()
        f1 = QFormLayout(t1)
        self._check(f1, "api", "enabled", "高性能模式（调用个人 API，关闭则不消耗 API）")
        self._line(f1, "api", "base_url", "API 地址", "https://api.deepseek.com")
        self._line(f1, "api", "api_key", "API Key", "", password=True)
        self._line(f1, "api", "model", "模型", "deepseek-chat")
        self._dspin(f1, "api", "temperature", "温度（越高越有性格，0.85~1.0 最佳）", lo=0.0, hi=1.5, step=0.05)
        self._dspin(f1, "api", "presence_penalty", "话题多样性（抑制死板）", lo=0.0, hi=2.0, step=0.1)
        self._dspin(f1, "api", "frequency_penalty", "重复用词惩罚", lo=0.0, hi=2.0, step=0.1)
        tabs.addTab(t1, "大模型")

        # 人格
        t2 = QWidget()
        f2 = QFormLayout(t2)
        self._line(f2, "persona", "user_name", "你的称呼", "Amon君")
        self._line(f2, "persona", "nicknames", "昵称（逗号分隔）", "Amon君,阿蒙,亲爱的")
        self._persona_txt = {}
        for p in persona.load_personas(self.config):
            g = QGroupBox(p["name"])
            gl = QFormLayout(g)
            e_name = QLineEdit(p.get("name", ""))
            e_short = QLineEdit(p.get("short", ""))
            e_short.setPlaceholderText("聊天框按钮上显示的名字")
            e_person = QPlainTextEdit(p.get("personality", ""))
            e_person.setFixedHeight(72)
            e_person.setPlaceholderText("这个角色的性格、说话风格（会写进系统提示词）")
            gl.addRow("名字", e_name)
            gl.addRow("按钮短名", e_short)
            gl.addRow("性格描述", e_person)
            f2.addRow(g)
            self._persona_txt[p["id"]] = {"name": e_name, "short": e_short,
                                          "personality": e_person}
        tabs.addTab(t2, "人格")

        # 外观 / 提示音
        t4 = QWidget()
        f4 = QFormLayout(t4)
        self._file(f4, "icons", "avatar", "全局头像兜底（角色未单独设置时用）")
        self._spin(f4, "icons", "opacity", "悬浮图标不透明度(%)", lo=10, hi=100)
        self._check(f4, "sounds", "enabled", "启用提示音")
        self._file(f4, "sounds", "notification", "提示音")
        self._file(f4, "sounds", "quick", "快捷音（主动对话）")

        # 各人格外观设置
        self._persona_edits = {}
        for p in persona.load_personas(self.config):
            g = QGroupBox(p["name"])
            gl = QFormLayout(g)
            e_icon = QLineEdit(p.get("icon", ""))
            e_icon.setPlaceholderText("留空则用程序默认图标")
            b1 = QPushButton("浏览")
            b1.clicked.connect(lambda _=False, e=e_icon: self._pick(e))
            e_avatar = QLineEdit(p.get("avatar", ""))
            e_avatar.setPlaceholderText("留空则用全局头像兜底/首字头像")
            b2 = QPushButton("浏览")
            b2.clicked.connect(lambda _=False, e=e_avatar: self._pick(e))
            e_accent = QLineEdit(p.get("accent", ""))
            e_accent.setPlaceholderText("#ff5f7e")
            icon_row = QWidget(); ih = QHBoxLayout(icon_row)
            ih.setContentsMargins(0, 0, 0, 0); ih.addWidget(e_icon, 1); ih.addWidget(b1)
            ava_row = QWidget(); ah = QHBoxLayout(ava_row)
            ah.setContentsMargins(0, 0, 0, 0); ah.addWidget(e_avatar, 1); ah.addWidget(b2)
            gl.addRow("悬浮图标", icon_row)
            gl.addRow("聊天头像", ava_row)
            gl.addRow("主题色", e_accent)
            f4.addRow(g)
            self._persona_edits[p["id"]] = {"icon": e_icon,
                                            "avatar": e_avatar, "accent": e_accent}
        tabs.addTab(t4, "外观 / 提示音")

        # 热键 / 启动
        t5 = QWidget()
        f5 = QFormLayout(t5)
        self._line(f5, "hotkeys", "toggle_show", "显示/隐藏快捷键", "ctrl+alt+k")
        self._line(f5, "hotkeys", "hide", "隐藏快捷键", "ctrl+alt+h")
        self._combo(f5, "app", "float_click_mode", "悬浮图标打开方式",
                    [("单击打开", "single"), ("双击打开", "double")])
        self._check(f5, "app", "autostart", "开机自动启动")
        self._check(f5, "app", "always_on_top", "聊天窗口始终置顶")
        self._spin(f5, "app", "opacity", "聊天窗口不透明度(%)", lo=10, hi=100)
        tabs.addTab(t5, "热键 / 启动")

        # 主动搭话
        t6 = QWidget()
        f6 = QFormLayout(t6)
        self._check(f6, "proactive", "enabled", "启用主动搭话")
        self._spin(f6, "proactive", "idle_minutes", "活跃多久后搭话（分钟）", 5, 180)
        tabs.addTab(t6, "主动搭话")

        # 存储 / 规则
        t7 = QWidget()
        f7 = QFormLayout(t7)
        self._spin(f7, "app", "max_history", "上下文最近消息数", 1, 200)
        self._spin(f7, "app", "auto_clean_count", "自动清理阈值（条）", 10, 100000)
        btn_clean = QPushButton("立即清理全部对话记录")
        btn_clean.clicked.connect(self._clean_all)
        f7.addRow("", btn_clean)

        rule_row = QWidget()
        rh = QHBoxLayout(rule_row)
        rh.setContentsMargins(0, 0, 0, 0)
        self.rule_name = QLineEdit()
        self.rule_name.setPlaceholderText("规则名")
        self.rule_pattern = QLineEdit()
        self.rule_pattern.setPlaceholderText("正则 pattern")
        self.rule_repl = QLineEdit()
        self.rule_repl.setPlaceholderText("替换为")
        btn_add = QPushButton("添加规则")
        btn_add.clicked.connect(self._add_rule)
        rh.addWidget(self.rule_name)
        rh.addWidget(self.rule_pattern)
        rh.addWidget(self.rule_repl)
        rh.addWidget(btn_add)
        f7.addRow("文本规则", rule_row)
        self.rule_list = QListWidget()
        f7.addRow("已有规则", self.rule_list)
        btn_del = QPushButton("删除选中规则")
        btn_del.clicked.connect(self._del_rule)
        f7.addRow("", btn_del)
        tabs.addTab(t7, "存储 / 规则")

        # 底部按钮
        btns = QHBoxLayout()
        btns.addStretch()
        save = QPushButton("保存")
        save.clicked.connect(self._save)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        btns.addWidget(save)
        btns.addWidget(cancel)
        root.addLayout(btns)

    # ---------------- 载入 / 保存 ----------------
    def _load(self):
        def val(section, key):
            v = self.config.get(section, key, "")
            if isinstance(v, list):
                return ", ".join(v)
            return v

        for (section, key), w in self._edits.items():
            v = val(section, key)
            if isinstance(w, QLineEdit):
                w.setText(str(v) if v is not None else "")
            elif isinstance(w, QComboBox):
                idx = w.findData(str(v))
                if idx < 0:
                    idx = w.findText(str(v))
                w.setCurrentIndex(idx if idx >= 0 else 0)
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(v))
            elif isinstance(w, QDoubleSpinBox):
                w.setValue(float(v or 0.0))
            elif isinstance(w, QSpinBox):
                w.setValue(int(v or 0))
        self._refresh_rules()

    def _save(self):
        for (section, key), w in self._edits.items():
            if isinstance(w, QLineEdit):
                v = w.text().strip()
                if key == "nicknames":
                    v = [x.strip() for x in v.replace("，", ",").split(",") if x.strip()]
            elif isinstance(w, QComboBox):
                v = w.currentData()
                if v is None:
                    v = w.currentText()
            elif isinstance(w, QCheckBox):
                v = w.isChecked()
            elif isinstance(w, QDoubleSpinBox):
                v = w.value()
            elif isinstance(w, QSpinBox):
                v = w.value()
            else:
                continue
            self.config.set(section, key, v, save=False)
        # 保存人格设置（人格页：名字/短名/性格；外观页：图标/头像/主题色）
        cur = {p["id"]: p for p in persona.load_personas(self.config)}
        new_list = []
        for pid, p in cur.items():
            p = dict(p)
            p["id"] = pid
            txt = getattr(self, "_persona_txt", {}).get(pid)
            if txt:
                p["name"] = txt["name"].text().strip() or p.get("name", pid)
                p["short"] = txt["short"].text().strip() or p.get("short", p["name"])
                p["personality"] = txt["personality"].toPlainText().strip()
            eds = getattr(self, "_persona_edits", {}).get(pid)
            if eds:
                p["icon"] = eds["icon"].text().strip()
                p["avatar"] = eds["avatar"].text().strip()
                acc = eds["accent"].text().strip()
                if acc:
                    p["accent"] = acc
            new_list.append(p)
        self.config.set("personas", "list", new_list, save=False)
        self.config.save()

        # 应用开机自启
        if self.config.get("app", "autostart", False):
            startup.enable()
        else:
            startup.disable()

        self.saved.emit()
        self.accept()

    # ---------------- 清理 / 规则 ----------------
    def _clean_all(self):
        if QMessageBox.question(self, "确认", "确定清空全部对话记录吗？") == QMessageBox.Yes:
            self.db.clear_messages()
            QMessageBox.information(self, "完成", "对话记录已清空。")

    def _add_rule(self):
        name = self.rule_name.text().strip() or "未命名"
        pat = self.rule_pattern.text().strip()
        repl = self.rule_repl.text()
        if not pat:
            return
        self.db.add_rule(name, pat, repl)
        self.rule_name.clear()
        self.rule_pattern.clear()
        self.rule_repl.clear()
        self._refresh_rules()

    def _del_rule(self):
        it = self.rule_list.currentRow()
        if it < 0:
            return
        rules = self.db.list_rules()
        if 0 <= it < len(rules):
            self.db.del_rule(rules[it]["id"])
        self._refresh_rules()

    def _refresh_rules(self):
        self.rule_list.clear()
        for r in self.db.list_rules():
            self.rule_list.addItem(f"{r['name']}: {r['pattern']} → {r['replacement']}")
