"""程序入口：装配所有组件。"""
import logging
import random
import sys
import threading

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication

from . import (
    assistant, audio, chat_window, config, db, floating, hotkey, panel_window,
    paths, persona, screen_monitor, startup,
)

# 主动搭话兜底台词（按人格 id；API 不可用时使用）
PROACTIVE_FALLBACK = {
    "kato": [
        "阿蒙君，你忙了好一会儿啦，要不要休息一下？",
        "阿蒙君，有好好喝水吗？别太累着自己。",
        "盯了这么久屏幕，眼睛会不会酸？",
        "阿蒙君，我有点想你了。",
    ],
    "rem": [
        "阿蒙大人，请稍微休息一下吧。",
        "雷姆给您泡了茶……要喝一点吗？",
        "您已经工作很久了，雷姆有些担心。",
        "阿蒙大人，请不要忘记吃饭。",
    ],
    "elaina": [
        "哎呀，你还在忙啊？",
        "休息一下啦，不然我可要自己出去旅行了哦。",
        "旅人先生，要不要听我讲个旅途见闻？",
        "真是的，这么久都不理我。",
    ],
    "_default": [
        "你已经忙了很久了，要不要休息一下？",
        "记得喝口水，别太累了。",
    ],
}


class Signals(QObject):
    proactive_alert = Signal()
    proactive_show = Signal(str, object)
    reminder_show = Signal(str, str)
    hotkey_toggle = Signal()
    hotkey_hide = Signal()


class Controller(QObject):
    def __init__(self):
        super().__init__()
        paths.ensure_dirs()
        self._setup_logging()
        self.config = config.Config()
        self.db = db.Database()
        self.db.migrate_persona_modes()
        self.audio = audio.AudioPlayer()
        self.assistant = assistant.Assistant(self.config, self.db)
        self._pending_persona = None

        self.signals = Signals()
        self.signals.proactive_alert.connect(self._on_proactive_alert)
        self.signals.proactive_show.connect(self._on_proactive_show)
        self.signals.reminder_show.connect(self._on_reminder_show)
        self.win = chat_window.ChatWindow(self.config, self.db, self.assistant, self.audio)
        self.float_icon = floating.FloatingIcon(self.config)
        self.cloud = floating.CloudBubble()
        self.tray = floating.TrayIcon(self.config)
        self.panel = panel_window.PanelWindow(self.config, self.db)
        self.float_icon.set_persona(self.win.persona)
        self.tray.set_persona(self.win.persona)

        # 快捷键回调在后台线程触发，必须经信号切回主线程再操作界面
        self.signals.hotkey_toggle.connect(self.toggle_chat)
        self.signals.hotkey_hide.connect(self.win.hide)

        self.hotkeys = hotkey.HotkeyManager()
        self.monitor = screen_monitor.ProactiveMonitor(self.config, self._on_proactive_trigger)

        self._wire()
        self._apply_autostart()

    def _setup_logging(self):
        logging.basicConfig(
            filename=str(paths.LOG_PATH), level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")

    def _wire(self):
        self.win.request_panel.connect(self.show_panel)
        self.float_icon.clicked.connect(self.show_chat)
        self.float_icon.show_panel.connect(self.show_panel)
        self.float_icon.quit_app.connect(self.quit)
        self.float_icon.persona_select.connect(self.switch_persona)
        self.win.persona_changed.connect(self._on_persona_changed)
        self.cloud.clicked.connect(self._on_cloud_click)
        self.tray.toggle.connect(self.toggle_chat)
        self.tray.show_panel.connect(self.show_panel)
        self.tray.quit_app.connect(self.quit)
        self.panel.saved.connect(self._on_config_saved)
        self.win.hide_floating.connect(self.float_icon.hide)
        self.win.show_floating.connect(self.float_icon.show)

        # 快捷键回调运行在热键线程：只发信号，由 Qt 排队到主线程执行界面操作
        self.hotkeys.register(self.config.get("hotkeys", "toggle_show", "ctrl+alt+k"),
                              lambda: self.signals.hotkey_toggle.emit())
        self.hotkeys.register(self.config.get("hotkeys", "hide", "ctrl+alt+h"),
                              lambda: self.signals.hotkey_hide.emit())
        self.hotkeys.start()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_reminders)
        self.timer.start(60000)

        QTimer.singleShot(1500, self.check_startup_reminders)
        self.monitor.start()

    def _apply_autostart(self):
        try:
            if self.config.get("app", "autostart", False):
                startup.enable()
            else:
                startup.disable()
        except Exception:
            pass

    # ---------------- 显示/隐藏 ----------------
    def _gui_thread_ok(self):
        """界面操作必须在主线程执行（否则 Qt 可能崩溃）。"""
        try:
            from PySide6.QtCore import QThread
            return QThread.currentThread() is self.thread()
        except Exception:
            return True

    def show_chat(self):
        if not self._gui_thread_ok():
            self.signals.hotkey_toggle.emit()
            return
        self.cloud.hide()
        pid = getattr(self, "_pending_persona", None)
        if pid:
            self._pending_persona = None
            try:
                self.win.set_persona(pid)
            except Exception:
                pass
        self.win.show()
        self.win.raise_()
        self.win.activateWindow()

    def toggle_chat(self):
        if not self._gui_thread_ok():
            self.signals.hotkey_toggle.emit()
            return
        if self.win.isVisible():
            self.win.hide()
        else:
            self.show_chat()

    def show_panel(self):
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    # ---------------- 人格切换 ----------------
    def switch_persona(self, pid):
        self.win.set_persona(pid)

    def _on_persona_changed(self, pid):
        p = persona.get_persona(self.config, pid)
        self.float_icon.set_persona(p)
        self.tray.set_persona(p)
        try:
            self.config.set("app", "default_persona", pid)
            self.config.save()
        except Exception:
            pass

    def quit(self):
        try:
            self.float_icon.save_position()
            self.monitor.stop()
            self.hotkeys.stop()
        except Exception:
            pass
        QApplication.quit()

    def _on_cloud_click(self):
        self.cloud.hide()
        self.show_chat()
        self._play_sound("quick")

    # ---------------- 提示音 ----------------
    def _sound_path(self, kind, default_name):
        p = self.config.get("sounds", kind, "")
        if p:
            return p
        return str(paths.SOUNDS_DIR / default_name)

    def _play_sound(self, kind, default_name="notification.wav"):
        if not self.config.get("sounds", "enabled", True):
            return
        self.audio.play(self._sound_path(kind, default_name))

    # ---------------- 提醒 ----------------
    def check_startup_reminders(self):
        for r in self.db.due_reminders():
            self.db.mark_reminder_done(r["id"])
            self.signals.reminder_show.emit(f"阿蒙君，提醒你一下：{r['text']}", "")

    def check_reminders(self):
        for r in self.db.due_reminders():
            self.db.mark_reminder_done(r["id"])
            self.signals.reminder_show.emit(f"阿蒙君，提醒你一下：{r['text']}", "")

    def _on_reminder_show(self, cn, jp):
        try:
            self.db.add_message("bot", "qa", cn, jp="", think_ms=0.0)
        except Exception:
            pass
        self.win.show_proactive(cn)
        self._play_sound("notification")

    # ---------------- 主动搭话（每次随机一个人格） ----------------
    def _on_proactive_trigger(self):
        p = random.choice(persona.load_personas(self.config))
        self.signals.proactive_alert.emit()
        threading.Thread(target=self._proactive_worker, args=(p,), daemon=True).start()

    def _proactive_worker(self, p):
        text = ""
        try:
            r = self.assistant.proactive_line(p)
            text = (r or {}).get("cn", "")
        except Exception:
            text = ""
        if not text:
            pool = PROACTIVE_FALLBACK.get(p["id"], PROACTIVE_FALLBACK["_default"])
            text = random.choice(pool)
        self.signals.proactive_show.emit(text, p)

    def _on_proactive_alert(self):
        if not self.win.isVisible():
            g = self.float_icon.frameGeometry()
            self.cloud.move(g.x() - 30, g.y() - 34)
            self.cloud.show()
        self._play_sound("quick", "quick.wav")

    def _on_proactive_show(self, cn, p):
        pid = (p or {}).get("id", "kato")
        try:
            self.db.add_message("bot", pid, cn, jp="", think_ms=0.0)
        except Exception:
            pass
        self._pending_persona = pid
        try:
            if self.win.isVisible():
                self.win.set_persona(pid)
            self.win.show_proactive(cn)
            self.win._build_sidebar()
        except Exception:
            pass

    # ---------------- 配置变更 ----------------
    def _on_config_saved(self):
        try:
            self.win.refresh_personas()
            self.float_icon.set_persona(self.win.persona)
            self.tray.set_persona(self.win.persona)
            self.float_icon.refresh_icon()
            self.win.apply_on_top()
            self.win.apply_opacity()
        except Exception:
            pass


def _ensure_logging():
    if not logging.getLogger().handlers:
        logging.basicConfig(
            filename=str(paths.LOG_PATH), level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")


def _install_logging_hooks():
    """把未捕获异常和 Qt 警告都写进 kato.log，便于排查崩溃。"""
    def excepthook(exc_type, exc, tb):
        logging.error("未捕获异常", exc_info=(exc_type, exc, tb))
    sys.excepthook = excepthook
    try:
        def thread_hook(args):
            logging.error("线程异常: %s", args.exc_value)
        threading.excepthook = thread_hook
    except Exception:
        pass
    try:
        from PySide6.QtCore import qInstallMessageHandler

        def qt_handler(mode, context, message):
            try:
                logging.warning("Qt: %s", message)
            except Exception:
                pass
        qInstallMessageHandler(qt_handler)
    except Exception:
        pass


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # 关闭聊天窗不退出，托盘/悬浮图标常驻
    _ensure_logging()
    _install_logging_hooks()
    ctrl = Controller()
    logging.info("加藤惠 已启动")
    # 悬浮图标恢复到上次位置（防止超出屏幕范围）
    try:
        x = int(ctrl.config.get("app", "float_x", 100))
        y = int(ctrl.config.get("app", "float_y", 100))
        scr = app.primaryScreen().availableGeometry()
        x = max(scr.x(), min(x, scr.right() - 70))
        y = max(scr.y(), min(y, scr.bottom() - 70))
    except Exception:
        x, y = 100, 100
    ctrl.float_icon.move(x, y)
    ctrl.float_icon.show()
    ctrl.tray.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
