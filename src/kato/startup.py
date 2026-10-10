"""开机自启（HKCU Run 键）。"""
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "KatoCompanion"


def _command():
    from . import paths
    pythonw = paths.BASE_DIR / "venv" / "Scripts" / "pythonw.exe"
    launcher = paths.BASE_DIR / "run.pyw"
    return f'"{pythonw}" "{launcher}"'


def is_enabled():
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY)
        val, _ = winreg.QueryValueEx(k, APP_NAME)
        winreg.CloseKey(k)
        return bool(val)
    except Exception:
        return False


def enable():
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _command())
        winreg.CloseKey(k)
        return True
    except Exception:
        return False


def disable():
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(k, APP_NAME)
        except Exception:
            pass
        winreg.CloseKey(k)
        return True
    except Exception:
        return False
