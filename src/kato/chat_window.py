"""QQ 风格聊天主窗口。"""
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QTextEdit, QToolButton, QVBoxLayout, QWidget,
)

from . import paths, persona
from .history_window import HistoryWindow


class Bubble(QFrame):
    def __init__(self, text, is_user, think_ms=None, ts=None, text_color="#4a2b32", parent=None):
        super().__init__(parent)
        self.setObjectName("userBubble" if is_user else "botBubble")
        self.setMaximumWidth(480)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 9, 14, 9)
        lay.setSpacing(4)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setStyleSheet(
            "background: transparent; border: none; color: white; font-size: 14px;" if is_user
            else f"background: transparent; border: none; color: {text_color}; font-size: 14px;")
        lay.addWidget(label)
        if ts:
            t = QLabel(datetime.fromtimestamp(ts).strftime("%m-%d %H:%M"))
            t.setStyleSheet("background: transparent; color: #9aa0a6; font-size: 11px;")
            lay.addWidget(t, alignment=Qt.AlignRight)
        if think_ms and think_ms > 0:
            t = QLabel(f"思考 {think_ms / 1000:.1f} 秒")
            t.setStyleSheet("background: transparent; color: #9aa0a6; font-size: 11px;")
            lay.addWidget(t, alignment=Qt.AlignRight)


class PersonaRow(QFrame):
    """QQ 风格的人格列表项：头像 + 名字 + 最后一句（过长省略号）。"""
    clicked = Signal(str)

    def __init__(self, persona, avatar_pix, preview, active, parent=None):
        super().__init__(parent)
        self.pid = persona["id"]
        self.setObjectName("personaRowActive" if active else "personaRow")
        self.setCursor(Qt.PointingHandCursor)
        h = QHBoxLayout(self)
        h.setContentsMargins(7, 6, 7, 6)
        h.setSpacing(8)
        av = QLabel()
        av.setFixedSize(30, 30)
        av.setScaledContents(True)
        av.setPixmap(avatar_pix)
        av.setStyleSheet("background: transparent;")
        h.addWidget(av, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setContentsMargins(0, 1, 0, 0)
        col.setSpacing(1)
        name = QLabel(persona.get("name", ""))
        name.setStyleSheet(
            f"background: transparent; font-size: 13px; font-weight: bold;"
            f" color: {persona.get('accent', '#ff5f7e')};")
        prev = QLabel()
        prev.setStyleSheet(
            f"background: transparent; font-size: 11px; color: {persona.get('muted', '#99a')};")
        fm = prev.fontMetrics()
        prev.setText(fm.elidedText(preview or "", Qt.ElideRight, 88))
        prev.setToolTip(preview or "")
        col.addWidget(name)
        col.addWidget(prev)
        h.addLayout(col, 1)

    def mousePressEvent(self, e):
        self.clicked.emit(self.pid)
        super().mousePressEvent(e)


class ChatWindow(QWidget):
    persona_changed = Signal(str)
    request_panel = Signal()
    show_floating = Signal()
    hide_floating = Signal()
    _result = Signal(object)

    def __init__(self, config, db, assistant, audio, parent=None):
        super().__init__(parent)
        self.config = config
        self.db = db
        self.assistant = assistant
        self.audio = audio
        self.personas = persona.load_personas(config)
        pid = config.get("app", "default_persona", "kato")
        if not any(p["id"] == pid for p in self.personas):
            pid = self.personas[0]["id"]
        self.persona_id = pid
        self.persona = persona.get_persona(config, pid)
        self._build_ui()
        self.toggle_sidebar(bool(config.get("app", "sidebar_collapsed", False)), save=False)
        self._load_avatar()
        self.apply_on_top()
        self.apply_opacity()
        self._result.connect(self._on_result)
        self.input.installEventFilter(self)

    # ---------------- UI ----------------
    def _build_ui(self):
        self.setWindowTitle(self.persona.get("name", "加藤惠"))
        self.resize(700, 720)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 头部
        header = QWidget()
        header.setObjectName("header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 6, 10, 6)
        self.name_label = QLabel(self.persona.get("name", "加藤惠"))
        hl.addWidget(self.name_label)
        hl.addStretch()
        self.side_btn = QToolButton()
        self.side_btn.setText("◀")
        self.side_btn.setToolTip("收起列表")
        self.side_btn.clicked.connect(lambda: self.toggle_sidebar())
        hl.addWidget(self.side_btn)
        self.pin_btn = QToolButton()
        self.pin_btn.setText("📌")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setToolTip("窗口置顶")
        self.pin_btn.clicked.connect(self._toggle_on_top)
        hl.addWidget(self.pin_btn)
        self.history_btn = QPushButton("聊天记录")
        self.history_btn.clicked.connect(self._open_history)
        hl.addWidget(self.history_btn)
        self.panel_btn = QPushButton("系统面板")
        self.panel_btn.clicked.connect(self.request_panel.emit)
        hl.addWidget(self.panel_btn)
        root.addWidget(header)

        # 主体：左侧人格列表（QQ 风格）+ 右侧聊天区
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        side = QWidget()
        side.setObjectName("sideBar")
        side.setFixedWidth(172)
        self.side = side
        self.sidebar_layout = QVBoxLayout(side)
        self.sidebar_layout.setContentsMargins(6, 8, 6, 8)
        self.sidebar_layout.setSpacing(4)
        self.sidebar_layout.addStretch()
        body.addWidget(side)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        # 聊天区
        self.scroll = QScrollArea()
        self.scroll.setObjectName("chatArea")
        self.scroll.setWidgetResizable(True)
        self.chat_content = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_content)
        self.chat_layout.setContentsMargins(12, 12, 12, 12)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch()
        self.scroll.setWidget(self.chat_content)
        right.addWidget(self.scroll, 1)

        # 滚动条变化时自动贴底（消息多时保证停在最新一条）
        self._stick_bottom = True
        _sb = self.scroll.verticalScrollBar()
        _sb.rangeChanged.connect(self._on_scroll_range)
        _sb.valueChanged.connect(self._on_scroll_value)

        # 输入区
        input_area = QWidget()
        input_area.setObjectName("inputArea")
        il = QHBoxLayout(input_area)
        il.setContentsMargins(10, 8, 10, 10)
        self.input = QTextEdit()
        self.input.setFixedHeight(78)
        self.input.setPlaceholderText("在这里输入想说的话…（Enter 发送，Shift+Enter 换行）")
        il.addWidget(self.input, 1)
        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.clicked.connect(self.on_send)
        il.addWidget(self.send_btn, 0, Qt.AlignBottom)
        right.addWidget(input_area)

        body.addLayout(right, 1)
        root.addLayout(body, 1)

        self.set_persona(self.persona_id)

    # ---------------- 左侧列表收起/展开 ----------------
    def toggle_sidebar(self, collapse=None, save=True):
        collapsed = self.side.isVisible() if collapse is None else bool(collapse)
        self.side.setVisible(not collapsed)
        self.side_btn.setText("▶" if collapsed else "◀")
        self.side_btn.setToolTip("展开角色列表" if collapsed else "收起角色列表")
        if save:
            try:
                self.config.set("app", "sidebar_collapsed", collapsed)
                self.config.save()
            except Exception:
                pass

    # ---------------- 左侧人格列表 ----------------
    def _last_preview(self, pid):
        try:
            rows = self.db.recent_messages(limit=1, mode=pid)
            if rows:
                txt = (rows[-1]["content"] or "").replace("\n", " ").strip()
                if rows[-1]["role"] == "user":
                    txt = "我：" + txt
                return txt
        except Exception:
            pass
        p = persona.get_persona(self.config, pid)
        return p.get("personality", "") or "还没有聊天记录"

    def _build_sidebar(self):
        if not hasattr(self, "sidebar_layout"):
            return
        while self.sidebar_layout.count() > 1:
            item = self.sidebar_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._persona_rows = {}
        for p in self.personas:
            row = PersonaRow(p, self._avatar_pixmap_for(p, 30),
                             self._last_preview(p["id"]),
                             p["id"] == self.persona_id)
            row.clicked.connect(self.set_persona)
            self._persona_rows[p["id"]] = row
            self.sidebar_layout.insertWidget(self.sidebar_layout.count() - 1, row)

    # ---------------- 人格 / 主题 ----------------
    def _apply_theme(self):
        p = self.persona
        acc = p.get("accent", "#ff5f7e")
        accd = p.get("accent_dark", "#f0486b")
        bg = p.get("bg", "#fff5f7")
        soft = p.get("soft", "#ffe4e9")
        stxt = p.get("soft_text", "#c9858f")
        bd = p.get("border", "#ffd9e0")
        txt = p.get("text", "#4a2b32")
        self.setStyleSheet(f"""
            QWidget {{ background: {bg}; font-family: "Microsoft YaHei", "PingFang SC", sans-serif; color: {txt}; font-size: 13px; }}
            #header {{ background: #ffffff; border-bottom: 1px solid {bd}; }}
            #sideBar {{ background: #ffffff; border-right: 1px solid {bd}; }}
            #personaRow {{ background: transparent; border-radius: 8px; }}
            #personaRow:hover {{ background: {soft}; }}
            #personaRowActive {{ background: {soft}; border-left: 3px solid {acc}; border-radius: 8px; }}
            #chatArea {{ background: {bg}; }}
            #inputArea {{ background: #ffffff; border-top: 1px solid {bd}; }}
            #userBubble {{ background: {acc}; border-radius: 12px; }}
            #botBubble {{ background: #ffffff; border-radius: 12px; border: 1px solid {bd}; }}
            QTextEdit {{ background: #ffffff; border: 1px solid {bd}; border-radius: 8px; padding: 6px; font-size: 15px; }}
            QTextEdit:focus {{ border: 1px solid {acc}; }}
            QPushButton#sendBtn {{ background: {acc}; color: white; border: none; border-radius: 8px; padding: 8px 20px; font-size: 15px; }}
            QPushButton#sendBtn:hover {{ background: {accd}; }}
            QPushButton#sendBtn:pressed {{ background: {accd}; }}
            QPushButton {{ padding: 6px 14px; border-radius: 6px; font-size: 13px; background: {soft}; color: {stxt}; border: none; }}
            QPushButton:hover {{ background: {bd}; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {soft}; border-radius: 4px; min-height: 30px; }}
            QScrollBar::handle:vertical:hover {{ background: {bd}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """)
        self.name_label.setStyleSheet(
            f"QLabel {{ font-size: 16px; font-weight: bold; color: {acc}; padding: 0px 8px; }}")

    def set_persona(self, pid):
        if pid == self.persona_id and getattr(self, "_persona_ready", False):
            return
        self.persona_id = pid
        self.persona = persona.get_persona(self.config, pid)
        self._apply_theme()
        self._load_avatar()
        self._build_sidebar()
        self.name_label.setText(self.persona.get("name", "加藤惠"))
        self.setWindowTitle(self.persona.get("name", "加藤惠"))
        self._load_history()
        self._persona_ready = True
        self.persona_changed.emit(pid)

    # ---------------- 头像 ----------------
    def _pick_avatar_path(self):
        """使用当前人格的头像；未设置则用全局头像兜底，再退回首字头像。"""
        single = self.persona.get("avatar", "") or self.config.get("icons", "avatar", "")
        return single if (single and Path(single).exists()) else ""

    def _avatar_pixmap_for(self, p, size=56):
        """按人格生成圆形头像（无图片时用主题色+首字绘制）。"""
        from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
        path = p.get("avatar", "") or self.config.get("icons", "avatar", "")
        raw = QPixmap(path) if (path and Path(path).exists()) else QPixmap()
        if raw.isNull():
            raw = QPixmap(256, 256)
            raw.fill(Qt.transparent)
            painter = QPainter(raw)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor(p.get("accent", "#ff7d95")))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(8, 8, 240, 240)
            painter.setPen(QColor("white"))
            painter.setFont(QFont("Microsoft YaHei", 110))
            painter.drawText(raw.rect(), Qt.AlignCenter,
                             (p.get("short", "惠") or "恵")[0])
            painter.end()
        d = size * 2          # 2 倍超采样，显示更清晰
        out = QPixmap(d, d)
        out.fill(Qt.transparent)
        pnt = QPainter(out)
        pnt.setRenderHint(QPainter.Antialiasing)
        clip = QPainterPath()
        clip.addEllipse(0, 0, d, d)
        pnt.setClipPath(clip)
        pnt.drawPixmap(0, 0, d, d,
                       raw.scaled(d, d, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        pnt.setClipping(False)
        pnt.setPen(QPen(QColor(p.get("border", "#ffd9e0")), 4))
        pnt.setBrush(Qt.NoBrush)
        pnt.drawEllipse(2, 2, d - 4, d - 4)
        pnt.end()
        return out

    def _load_avatar(self):
        self._avatar_pix = self._avatar_pixmap_for(self.persona, 44)

    def reload_avatar(self):
        self._load_avatar()

    def refresh_personas(self):
        """面板保存后重新加载人格定义并刷新界面。"""
        self.personas = persona.load_personas(self.config)
        self.persona = persona.get_persona(self.config, self.persona_id)
        self._apply_theme()
        self._load_avatar()
        self._build_sidebar()
        self.name_label.setText(self.persona.get("name", "加藤惠"))
        self.setWindowTitle(self.persona.get("name", "加藤惠"))

    # ---------------- 置顶 ----------------
    def _pin_style(self, on):
        if on:
            return ("QToolButton { background:#ff5f7e; color:white; border:none;"
                    " border-radius:6px; padding:6px 10px; font-size:14px; }")
        return ("QToolButton { background:#ffe4e9; color:#c9858f; border:none;"
                " border-radius:6px; padding:6px 10px; font-size:14px; }")

    def apply_on_top(self):
        on = bool(self.config.get("app", "always_on_top", False))
        self.pin_btn.setChecked(on)
        self.pin_btn.setStyleSheet(self._pin_style(on))
        self._set_on_top(on)

    def _toggle_on_top(self, checked):
        self.config.set("app", "always_on_top", bool(checked))
        self.config.save()
        self._set_on_top(checked)
        self.pin_btn.setStyleSheet(self._pin_style(checked))

    def _set_on_top(self, on):
        """切换置顶：用 Win32 SetWindowPos 直接改 Z 序，避免重建窗口导致的闪屏。"""
        self._suppress_visibility_signal = True
        ok = False
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.SetWindowPos.argtypes = [
                wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            user32.SetWindowPos.restype = wintypes.BOOL
            mask = (1 << (8 * ctypes.sizeof(ctypes.c_void_p))) - 1
            after = ctypes.c_void_p((-1 if on else -2) & mask)  # HWND_TOPMOST / NOTOPMOST
            flags = 0x0001 | 0x0002 | 0x0010                    # NOSIZE | NOMOVE | NOACTIVATE
            ok = bool(user32.SetWindowPos(wintypes.HWND(int(self.winId())), after,
                                          0, 0, 0, 0, flags))
        except Exception:
            ok = False
        if not ok:
            # 兜底：改用 Qt 原生方式（会有轻微闪屏，但保证功能可用）
            try:
                visible = self.isVisible()
                self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
                if visible:
                    self.show()
            except Exception:
                pass
        self._suppress_visibility_signal = False

    # ---------------- 透明度 ----------------
    def apply_opacity(self):
        try:
            op = int(self.config.get("app", "opacity", 100))
            op = max(10, min(100, op))
            self.setWindowOpacity(op / 100.0)
        except Exception:
            self.setWindowOpacity(1.0)

    # ---------------- 历史记录 ----------------
    def _load_history(self):
        if not hasattr(self, "chat_layout"):
            return
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        try:
            rows = self.db.recent_messages(
                limit=self.config.get("app", "max_history", 40), mode=self.persona_id)
            for r in rows:
                self.add_bubble(r["content"], r["role"] == "user",
                                think_ms=r["think_ms"], ts=r["ts"])
        except Exception:
            pass
        self._scroll_bottom(force=True)

    def _open_history(self):
        if getattr(self, "_history_win", None) is None:
            self._history_win = HistoryWindow(self.db, self.personas, self)
        self._history_win._refresh()
        self._history_win.show()
        self._history_win.raise_()

    # ---------------- 消息 ----------------
    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self.input and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
                self.on_send()
                return True
        return super().eventFilter(obj, event)

    def on_send(self):
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self.add_bubble(text, True)
        self._thinking = self._add_thinking()
        self._set_status("正在思考怎么回复…")
        threading.Thread(target=self._worker, args=(text,), daemon=True).start()

    def _set_status(self, text):
        try:
            self.name_label.setText(text)
        except Exception:
            pass

    def _worker(self, text):
        try:
            r = self.assistant.handle(text, self.persona_id)
        except Exception as e:
            r = {"cn": f"啊……好像出了点小问题（{e}）。阿蒙君再试一次好不好？",
                 "jp": "", "think_ms": 0.0}
        # 持久化
        try:
            self.db.add_message("user", self.persona_id, text)
            self.db.add_message("bot", self.persona_id, r.get("cn", ""),
                                jp=r.get("jp", ""), think_ms=r.get("think_ms", 0.0))
            if self.config.get("app", "auto_clean_count", 500) and \
                    self.db.count_messages() > self.config.get("app", "auto_clean_count", 500):
                self.db.cleanup_messages(keep=self.config.get("app", "max_history", 40) * 2)
        except Exception:
            pass
        self._result.emit(r)

    def _on_result(self, r):
        self._remove_thinking()
        self._set_status(self.persona.get("name", "加藤惠"))
        think = r.get("think_ms") if self.config.get("app", "show_think_time", True) else 0.0
        self.add_bubble(r.get("cn", ""), False, think_ms=think)
        self._build_sidebar()

    def _add_thinking(self):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        b = Bubble("……", False)
        h.addWidget(b)
        h.addStretch()
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, row)
        self._scroll_bottom()
        return row

    def _remove_thinking(self):
        if getattr(self, "_thinking", None):
            try:
                self._thinking.setParent(None)
                self._thinking.deleteLater()
            except Exception:
                pass
            self._thinking = None

    def add_bubble(self, text, is_user, think_ms=None, ts=None):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        b = Bubble(text, is_user, think_ms, ts,
                   text_color=self.persona.get("text", "#4a2b32"))
        if is_user:
            h.addStretch()
            h.addWidget(b)
        else:
            av = QLabel()
            av.setFixedSize(44, 44)
            av.setScaledContents(True)
            av.setPixmap(getattr(self, "_avatar_pix", None))
            av.setToolTip("加藤惠")
            h.addWidget(av, 0, Qt.AlignTop)
            h.addSpacing(6)
            h.addWidget(b)
            h.addStretch()
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, row)
        self._scroll_bottom()

    def _scroll_bottom(self, force=False):
        from PySide6.QtCore import QTimer
        if not (force or getattr(self, "_stick_bottom", True)):
            return
        # 消息多时布局完成较慢：立刻贴底 + 多次补扫，保证停在最新一条
        self._stick_bottom = True
        try:
            self.chat_layout.activate()
            self.chat_content.adjustSize()
        except Exception:
            pass
        for ms in (0, 30, 120, 350, 700):
            QTimer.singleShot(ms, self._do_scroll)

    def _do_scroll(self):
        sb = self.scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_scroll_range(self, _min, _max):
        if getattr(self, "_stick_bottom", True):
            self.scroll.verticalScrollBar().setValue(_max)

    def _on_scroll_value(self, val):
        sb = self.scroll.verticalScrollBar()
        # 用户往上翻看历史时不强行拉回底部
        self._stick_bottom = (sb.maximum() - val) < 60

    # ---------------- 主动对话 ----------------
    def show_proactive(self, cn):
        self.add_bubble(cn, False)

    # ---------------- 显示/隐藏 ----------------
    def showEvent(self, e):
        super().showEvent(e)
        if not getattr(self, "_suppress_visibility_signal", False):
            self.hide_floating.emit()
        # 打开窗口时定位到最新消息
        self._scroll_bottom(force=True)
        # 若开启了置顶，重新确保在最前（不影响其它窗口）
        if self.config.get("app", "always_on_top", False):
            self._set_on_top(True)

    def hideEvent(self, e):
        super().hideEvent(e)
        if not getattr(self, "_suppress_visibility_signal", False):
            self.show_floating.emit()
