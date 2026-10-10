"""配置管理：读写 data/config.json，带默认值。"""
import copy
import json

from . import paths

DEFAULTS = {
    "api": {
        "base_url": "https://api.deepseek.com",
        "api_key": "sk-1aa0b7ee8ff54437bb93a91c4a8de991",
        "model": "deepseek-chat",
        "enabled": False,          # True = 高性能模式（调用个人 API）
        "temperature": 0.9,        # 角色扮演建议 0.85~1.0
        "top_p": 0.95,
        "presence_penalty": 0.4,   # 鼓励话题/用词多样
        "frequency_penalty": 0.3,  # 抑制重复用词
    },
    "persona": {
        "bot_name": "加藤惠",
        "bot_jp_name": "加藤恵",
        "user_name": "Amon君",
        "nicknames": ["Amon君", "阿蒙", "亲爱的"],
    },
    "hotkeys": {
        "toggle_show": "ctrl+alt+k",
        "hide": "ctrl+alt+h",
    },
    "sounds": {
        "notification": "",   # 提示音（空=默认）
        "quick": "",          # 快捷音（主动对话时）
        "enabled": True,
    },
    "icons": {
        "avatar": "",    # 全局头像兜底（空=用角色首字头像）
        "opacity": 100,  # 悬浮图标不透明度(%) 10-100
    },
    "app": {
        "autostart": True,
        "always_on_top": False,       # 聊天窗口始终置顶
        "opacity": 100,               # 聊天窗口不透明度(%) 10-100
        "float_click_mode": "single", # 悬浮图标打开方式：single=单击 double=双击
        "float_x": 100,               # 悬浮图标上次位置 X
        "float_y": 100,               # 悬浮图标上次位置 Y
        "default_persona": "kato",    # 默认人格 id
        "sidebar_collapsed": False,   # 左侧角色列表是否收起
        "max_history": 40,           # 参与上下文的最近消息数
        "auto_clean_count": 500,     # 超过则自动清理旧对话
        "show_think_time": True,
    },
    "personas": {
        "list": [],                  # 自定义人格列表；留空用默认三人（惠/英梨梨/诗羽）
    },
    "proactive": {
        "enabled": True,
        "idle_minutes": 35,          # 长时间编辑文本后主动搭话的阈值（分钟）
    },
}


class Config:
    def __init__(self, path=None):
        self.path = path or paths.CONFIG_PATH
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self):
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._merge(self.data, json.load(f))
            except Exception:
                pass

    @staticmethod
    def _merge(base, loaded):
        for k, v in loaded.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                Config._merge(base[k], v)
            else:
                base[k] = v

    def save(self):
        paths.ensure_dirs()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get(self, section, key, default=None):
        return self.data.get(section, {}).get(key, default)

    def set(self, section, key, value, save=True):
        self.data.setdefault(section, {})[key] = value
        if save:
            self.save()

    def __getitem__(self, key):
        return self.data[key]
