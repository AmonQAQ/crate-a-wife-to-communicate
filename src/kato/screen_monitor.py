"""活跃度监控：检测用户长时间连续编辑/使用，触发主动搭话。"""
import ctypes
import threading
import time


class IdleMonitor:
    def idle_seconds(self):
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return millis / 1000.0
        return 0.0


class ProactiveMonitor:
    """每 20 秒采样一次：若用户长时间连续活跃（在编辑/操作），触发一次主动搭话。"""

    def __init__(self, config, on_trigger):
        self.config = config
        self.on_trigger = on_trigger          # callback()
        self.idle = IdleMonitor()
        self._active_seconds = 0.0
        self._thread = None
        self._running = False

    def start(self):
        if self._thread:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def reset(self):
        self._active_seconds = 0.0

    def _run(self):
        interval = 20.0
        while self._running:
            time.sleep(interval)
            if not self.config.get("proactive", "enabled", True):
                continue
            idle = self.idle.idle_seconds()
            if idle < 60.0:   # 用户正在活跃
                self._active_seconds += interval
            else:
                self._active_seconds = 0.0
            threshold = self.config.get("proactive", "idle_minutes", 35) * 60.0
            if self._active_seconds >= threshold:
                self._active_seconds = 0.0
                try:
                    self.on_trigger()
                except Exception:
                    pass
