"""路径解析：所有路径相对于项目根目录 D:\\Lao_Po。"""
from pathlib import Path

# 本文件位于 D:\Lao_Po\src\kato\paths.py
# parents: kato(0) -> src(1) -> Lao_Po(2)
BASE_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = BASE_DIR / "src"
ASSETS_DIR = BASE_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
SOUNDS_DIR = ASSETS_DIR / "sounds"
VOICE_DIR = ASSETS_DIR / "voice"
DATASET_DIR = ASSETS_DIR / "dataset"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
SCRIPTS_DIR = BASE_DIR / "scripts"

CONFIG_PATH = DATA_DIR / "config.json"
DB_PATH = DATA_DIR / "kato.db"
LOG_PATH = LOGS_DIR / "kato.log"


def ensure_dirs() -> None:
    for d in (DATA_DIR, LOGS_DIR, ICONS_DIR, SOUNDS_DIR, VOICE_DIR, DATASET_DIR):
        d.mkdir(parents=True, exist_ok=True)
