"""系统操作：QQ音乐控制、记事本、便签、日历、打开网址/搜索。尽力而为，失败不抛异常。"""
import subprocess
import time

try:
    import pyautogui
    import pygetwindow as gw
    _UI_AVAILABLE = True
except Exception:
    _UI_AVAILABLE = False

_QQMUSIC_PATHS = [
    r"D:\qqmusic\QQMusic.exe",
    r"C:\Program Files (x86)\Tencent\QQMusic\QQMusic.exe",
    r"C:\Program Files\Tencent\QQMusic\QQMusic.exe",
    r"D:\Program Files\Tencent\QQMusic\QQMusic.exe",
]


def _find_window(title_kw):
    if not _UI_AVAILABLE:
        return None
    try:
        wins = gw.getWindowsWithTitle(title_kw)
        return wins[0] if wins else None
    except Exception:
        return None


def _launch_qqmusic():
    for p in _QQMUSIC_PATHS:
        try:
            subprocess.Popen([p])
            return True
        except Exception:
            continue
    return False


def play_song_qqmusic(song_name):
    """搜索并播放 QQ音乐 中的歌曲（尽力而为）。"""
    if not _UI_AVAILABLE:
        return False
    w = _find_window("QQ音乐") or _find_window("QQ Music")
    if w is None:
        _launch_qqmusic()
        time.sleep(5)
        w = _find_window("QQ音乐") or _find_window("QQ Music")
    if w is None:
        return False
    try:
        w.activate()
        time.sleep(0.6)
        pyautogui.hotkey("ctrl", "f")      # 聚焦搜索框
        time.sleep(0.5)
        pyautogui.write(song_name, interval=0.03)
        time.sleep(0.4)
        pyautogui.press("enter")           # 搜索
        time.sleep(1.5)
        pyautogui.press("enter")           # 播放第一个结果
        return True
    except Exception:
        return False


def open_notepad():
    try:
        subprocess.Popen(["notepad.exe"])
        return True
    except Exception:
        return False


def open_sticky_notes():
    try:
        subprocess.Popen(["StikyNot.exe"])
        return True
    except Exception:
        return False


def open_calendar():
    try:
        subprocess.Popen(["start", "outlookcal:"], shell=True)
        return True
    except Exception:
        return False


def open_url(url):
    try:
        subprocess.Popen(["start", "", url], shell=True)
        return True
    except Exception:
        return False


def open_search(query):
    return open_url("https://www.bing.com/search?q=" + query)
