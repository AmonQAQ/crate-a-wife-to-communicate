"""全局快捷键（win32 RegisterHotKey + 消息循环）。"""
import ctypes
import threading
from ctypes import wintypes

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
WM_HOTKEY = 0x0312

_VK_LETTERS = {c: ord(c.upper()) for c in "abcdefghijklmnopqrstuvwxyz0123456789"}


def parse_combo(combo):
    mods = 0
    parts = [p.strip().lower() for p in combo.split("+")]
    for p in parts:
        if p in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif p == "alt":
            mods |= MOD_ALT
        elif p == "shift":
            mods |= MOD_SHIFT
        elif p in ("win", "meta"):
            mods |= MOD_WIN
    key = parts[-1]
    if key in _VK_LETTERS:
        return mods, _VK_LETTERS[key]
    if key.startswith("f") and key[1:].isdigit():
        return mods, 0x70 + int(key[1:]) - 1
    return mods, None


class HotkeyManager:
    def __init__(self):
        self._bindings = {}
        self._next_id = 1
        self._thread = None
        self._running = False

    def register(self, combo, callback):
        mods, vk = parse_combo(combo)
        if vk is None:
            return False
        hid = self._next_id
        self._next_id += 1
        self._bindings[hid] = (mods, vk, callback)
        return True

    def start(self):
        if self._thread:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        user32 = ctypes.windll.user32
        for hid, (mods, vk, cb) in list(self._bindings.items()):
            user32.RegisterHotKey(None, hid, mods, vk)
        msg = wintypes.MSG()
        while self._running:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0:
                continue
            if msg.message == WM_HOTKEY:
                b = self._bindings.get(msg.wParam)
                if b:
                    try:
                        b[2]()
                    except Exception:
                        pass
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
