"""桌面悬浮图标 + 云朵小气泡 + 系统托盘。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QLabel, QMenu, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from . import paths


class CloudBubble(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(56, 40)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel("…")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            "QLabel { background: white; border: 1px solid #ffd9e0; border-radius: 14px;"
            " color: #c2546b; font-size: 18px; }")
        lay.addWidget(self.label)

    def mousePressEvent(self, e):
        self.clicked.emit()
        super().mousePressEvent(e)


class FloatingIcon(QWidget):
    """桌面悬浮图标：不使用时显示，使用时隐藏。"""
    clicked = Signal()
    show_panel = Signal()
    quit_app = Signal()
    persona_select = Signal(str)

    def __init__(self, config, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.config = config
        self._persona_icon = ""
        self.setFixedSize(76, 76)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setScaledContents(False)
        self.label.setStyleSheet("QLabel { background: transparent; }")
        lay.addWidget(self.label)
        self._drag = None
        self._load_icon()
        self._apply_opacity()

    def set_persona(self, persona):
        """切换人格：更新悬浮图标。"""
        self._persona_icon = (persona or {}).get("icon", "")
        self._load_icon()

    def _apply_opacity(self):
        try:
            op = int(self.config.get("icons", "opacity", 100))
            op = max(10, min(100, op))
            self.setWindowOpacity(op / 100.0)
        except Exception:
            self.setWindowOpacity(1.0)

    def _load_icon(self):
        p = self._persona_icon or str(paths.ICONS_DIR / "default.png")
        try:
            pm = QPixmap(p)
            if pm.isNull():
                raise ValueError("bad image")
            w, h = pm.size().width(), pm.size().height()
            cap = 220   # 超大图按比例缩到不超过 220px，避免占满屏幕
            if max(w, h) > cap:
                k = cap / max(w, h)
                w, h = round(w * k), round(h * k)
                pm = pm.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.label.setPixmap(pm)
            self.label.setScaledContents(False)
            self.label.setFixedSize(w, h)
            self.setFixedSize(w + 12, h + 12)
        except Exception:
            self.label.setText("恵")
            self.label.setStyleSheet("QLabel { font-size: 34px; color: #fff; background: #f08ba8;"
                                     " border-radius: 32px; }")
            self.label.setScaledContents(False)
            self.label.setFixedSize(64, 64)
            self.setFixedSize(76, 76)

    def refresh_icon(self):
        self._load_icon()
        self._apply_opacity()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif e.button() == Qt.RightButton:
            self._menu()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._drag is not None:
            # 单击模式：位移很小才算点击（拖动不会打开）
            if self.config.get("app", "float_click_mode", "single") == "single":
                delta = e.globalPosition().toPoint() - (self.frameGeometry().topLeft() + self._drag)
                if abs(delta.x()) < 12 and abs(delta.y()) < 12:
                    self.clicked.emit()
        self._drag = None
        self.save_position()

    def save_position(self):
        """记住当前位置，下次启动时恢复。"""
        try:
            p = self.pos()
            self.config.set("app", "float_x", p.x())
            self.config.set("app", "float_y", p.y())
            self.config.save()
        except Exception:
            pass

    def mouseDoubleClickEvent(self, e):
        if self.config.get("app", "float_click_mode", "single") == "double":
            self.clicked.emit()

    def _menu(self):
        from . import persona
        m = QMenu()
        m.addAction("打开对话", self.clicked.emit)
        sub = m.addMenu("切换人格")
        try:
            for p in persona.load_personas(self.config):
                sub.addAction(p["short"], lambda _=False, pid=p["id"]: self.persona_select.emit(pid))
        except Exception:
            pass
        m.addAction("系统面板", self.show_panel.emit)
        m.addSeparator()
        m.addAction("退出", self.quit_app.emit)
        m.exec(self.cursor().pos())


class TrayIcon(QSystemTrayIcon):
    toggle = Signal()
    show_panel = Signal()
    quit_app = Signal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        icon = str(paths.ICONS_DIR / "default.png")
        self.setIcon(QIcon(icon) if icon else QIcon())
        self.setToolTip("加藤惠")
        self._menu = QMenu()
        self._menu.addAction("显示/隐藏", self.toggle.emit)
        self._menu.addAction("系统面板", self.show_panel.emit)
        self._menu.addSeparator()
        self._menu.addAction("退出", self.quit_app.emit)
        self.setContextMenu(self._menu)
        self.activated.connect(self._on_activated)

    def set_persona(self, persona):
        """切换人格：更新托盘图标。"""
        try:
            p = (persona or {}).get("icon", "") or str(paths.ICONS_DIR / "default.png")
            if p:
                self.setIcon(QIcon(p))
        except Exception:
            pass

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle.emit()
