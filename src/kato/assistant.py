"""助手调度：意图识别（系统命令）+ 大模型回复。"""
import re

from . import llm, memory, persona, system_ops


def _extract_song(text):
    """从'播放XX的歌'之类文本提取歌名。"""
    t = re.sub(r"(请|帮我|给我|一下|播放|放|搜索|搜|来一首|来首|首歌|的歌|歌曲|音乐|qq音乐)", "", text)
    return t.strip().strip("的。！!，, ")


class Assistant:
    def __init__(self, config, db):
        self.config = config
        self.db = db
        self.llm = llm.LLM(config, db)

    # ---------------- 对外入口 ----------------
    def handle(self, text, mode):
        """返回 dict(cn, jp, think_ms)。mode = 人格 id。"""
        text = (text or "").strip()
        act = self._try_action(text)
        if act is not None:
            return act
        ctx = memory.build_today_context(self.db, self.config)
        p = persona.get_persona(self.config, mode)
        return self.llm.reply(text, mode, today_context=ctx, persona=p)

    def proactive_line(self, p):
        """用指定人格生成一句主动搭话（20 字内自然短句）。"""
        prompt = ("（你正在主动找对方说话：他忙着别的事、很久没理你了。请说一句 20 字以内的"
                  "自然搭话——关心他、催他休息、或者分享一件小事。用你平时的语气，"
                  "不要问太多、不要客套，也不要提到自己是在主动搭话。）")
        ctx = memory.build_today_context(self.db, self.config)
        return self.llm.reply(prompt, p["id"], today_context=ctx, persona=p)

    # ---------------- 意图识别 ----------------
    def _try_action(self, text):
        """命中系统命令时返回完整结果 dict；否则返回 None。"""

        def done(cn, jp="", action=None):
            return {"cn": cn, "jp": jp, "think_ms": 0.0, "action": action}

        # 提醒
        if memory.is_reminder_request(text):
            remind_at, on_startup = memory.parse_reminder(text)
            self.db.add_reminder(text, remind_at=remind_at, on_startup=on_startup)
            if on_startup:
                return done(f"好，我记下啦：「{text}」。等那天我启动的时候会提醒阿蒙君的。")
            return done(f"好，我记下啦：「{text}」。到时间我会提醒阿蒙君的。")

        # 长期记忆 / 课表
        if memory.is_memory_request(text):
            content = re.sub(r"(请|帮我|给我)?(记住|记下|记着)", "", text).strip()
            if "课表" in text or "课程" in text or "上课" in text:
                self.db.set_memory("课表", text, category="schedule")
                return done("课表我记好啦，以后对应星期的时候我会提醒阿蒙君今天上什么课的。")
            key = content[:12] if content else "备注"
            self.db.set_memory(key, text, category="general")
            return done("嗯，我记住了。以后会记着这件事的。")

        # 清理记录
        if any(k in text for k in ("清理记录", "清空对话", "删除记录", "清空聊天")):
            self.db.cleanup_messages(keep=0)
            return done("我已经把旧对话清理干净啦，这样就不会被拖慢啦。")

        # 播放歌曲（QQ音乐）
        if re.search(r"(播放|放|搜|来一首|来首).{0,20}(歌|歌曲|音乐)", text) and "qq" in text.lower() or \
                re.search(r"(播放|放|搜|来一首|来首)", text) and "歌" in text:
            song = _extract_song(text)
            if song:
                ok = system_ops.play_song_qqmusic(song)
                if ok:
                    return done(f"我试着在 QQ音乐 里帮你找「{song}」啦，看看有没有播出来～")
                return done(f"我试着去开 QQ音乐 找「{song}」了，不过好像没成功，阿蒙君看看 QQ音乐 有没有打开？")
        elif any(k in text for k in ("播放", "放歌", "听歌")) and re.search(r"(周杰伦|晴天|稻香|歌)", text):
            song = _extract_song(text)
            if song:
                system_ops.play_song_qqmusic(song)
                return done(f"我试着在 QQ音乐 里帮你找「{song}」啦。")

        # 记事本 / 便签 / 日历
        if any(k in text for k in ("记事本", "记个笔记", "打开便签", "便利贴")):
            system_ops.open_notepad() if "记事本" in text or "笔记" in text else system_ops.open_sticky_notes()
            return done("记事本打开啦。")
        if any(k in text for k in ("日历", "打开日程", "看下日历")):
            system_ops.open_calendar()
            return done("日历打开啦。")

        # 搜索
        m = re.search(r"(搜索|搜一下|查一下|查查)(.+)", text)
        if m:
            q = m.group(2).strip()
            system_ops.open_search(q)
            return done(f"我帮你搜了「{q}」，浏览器里应该已经打开了。")

        return None
