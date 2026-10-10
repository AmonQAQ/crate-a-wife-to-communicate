"""大模型接入：DeepSeek（高性能模式）+ 规则兜底。"""
import json
import re
import time

import requests

from .persona import build_system_prompt


def _extract_json(text):
    """从模型输出中提取 {cn, jp}，尽量健壮；缺失 jp 时返回空串。"""
    if not text:
        return None
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            obj = json.loads(m.group(0))
            if "cn" in obj:
                return {"cn": str(obj["cn"]), "jp": str(obj.get("jp", "") or "")}
        except Exception:
            pass
    cn = re.search(r"(?:中文|cn)\s*[:：]\s*(.+?)(?=(?:日语|jp)\s*[:：]|$)", text, re.S | re.I)
    jp = re.search(r"(?:日语|jp)\s*[:：]\s*(.+)", text, re.S | re.I)
    if cn:
        return {"cn": cn.group(1).strip(), "jp": (jp.group(1).strip() if jp else "")}
    return {"cn": text, "jp": ""}


class LLM:
    def __init__(self, config, db):
        self.config = config
        self.db = db

    def reply(self, user_text, mode, memory_context="", today_context="", persona=None):
        """返回 dict(cn, jp, think_ms)。mode = 人格 id。"""
        history = self.db.recent_messages(
            limit=self.config.get("app", "max_history", 20), mode=mode)
        msgs = [{"role": "system",
                 "content": build_system_prompt(self.config, memory_context, today_context,
                                                persona=persona)}]
        for h in history:
            msgs.append({"role": "user" if h["role"] == "user" else "assistant",
                         "content": h["content"]})
        msgs.append({"role": "user", "content": user_text})

        if self.config.get("api", "enabled", False) and self.config.get("api", "api_key", ""):
            r = self._call_api(msgs)
            if r:
                return r
        return self._fallback(user_text, mode)

    # ---------------- DeepSeek ----------------
    def _call_api(self, msgs):
        cfg = self.config["api"]
        t0 = time.time()
        try:
            resp = requests.post(
                cfg["base_url"].rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {cfg['api_key']}",
                         "Content-Type": "application/json"},
                json={"model": cfg["model"], "messages": msgs,
                      "temperature": cfg.get("temperature", 0.9),
                      "top_p": cfg.get("top_p", 0.95),
                      "presence_penalty": cfg.get("presence_penalty", 0.4),
                      "frequency_penalty": cfg.get("frequency_penalty", 0.3)},
                timeout=120,
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            think = (time.time() - t0) * 1000
            obj = _extract_json(content)
            return {"cn": obj["cn"], "jp": obj.get("jp", ""), "think_ms": think}
        except Exception:
            return None

    # ---------------- 规则兜底（API 不可用时） ----------------
    def _fallback(self, user_text, mode):
        t = (user_text or "").strip()
        low = t.lower()
        if any(k in low for k in ("你好", "在吗", "早上好", "早安", "晚上好", "hi", "hello")):
            cn = "我在的。你不忙的时候，我们就聊聊天吧。"
        elif "天气" in t:
            cn = "天气我这边暂时查不到……出门前看一眼窗外，记得带伞。"
        elif any(k in t for k in ("谢谢", "辛苦", "多谢")):
            cn = "不用谢，能帮上你的忙就好。"
        elif any(k in t for k in ("睡", "晚安")):
            cn = "晚安，早点休息，明天见。"
        elif any(k in t for k in ("课", "上课", "课表")):
            cn = "课表我一直记着的，今天也加油。"
        elif any(k in t for k in ("作业", "写作业")):
            cn = "作业我会提醒你的，别拖到太晚。"
        else:
            cn = "嗯……网络好像有点不通畅，等一会儿再和我说一次好吗？"
        return {"cn": cn, "jp": "", "think_ms": 0.0}
