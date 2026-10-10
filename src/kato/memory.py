"""记忆与提醒：自然语言时间解析、每日上下文构建。"""
import re
import time
from datetime import datetime, timedelta


def parse_reminder(text):
    """从自然语言解析提醒时间。返回 (remind_at_epoch|None, on_startup_bool)。
    无具体时间 -> on_startup=True（当天程序启动时提醒）。"""
    now = datetime.now()
    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?\s*(?:(\d{1,2})[:：点](\d{1,2})?分?)?", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        hour = int(m.group(3)) if m.group(3) else None
        minute = int(m.group(4)) if m.group(4) else 0
        year = now.year
        if month < now.month or (month == now.month and day < now.day):
            year += 1
        if hour is None:
            return None, True
        try:
            return datetime(year, month, day, hour, minute).timestamp(), False
        except ValueError:
            return None, True
    m = re.search(r"(\d+)\s*(分钟|小时)\s*后", text)
    if m:
        n = int(m.group(1))
        delta = timedelta(minutes=n) if "分钟" in m.group(2) else timedelta(hours=n)
        return (now + delta).timestamp(), False
    if "明天" in text:
        return (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0).timestamp(), False
    if "后天" in text:
        return (now + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0).timestamp(), False
    return None, True


def is_reminder_request(text):
    return any(k in text for k in ("提醒", "记得叫我", "到点", "别忘"))


def is_memory_request(text):
    return any(k in text for k in ("记住", "记下", "记着", "帮我记"))


def build_today_context(db, config):
    now = datetime.now()
    wd = "一二三四五六日"[now.weekday()]
    lines = [f"今天是{now.month}月{now.day}日，星期{wd}，当前时间 {now.hour:02d}:{now.minute:02d}"]
    schedule = db.get_memory("课表")
    if schedule:
        lines.append(f"用户的课表（按星期）如下：\n{schedule}")
    due = db.due_reminders()
    if due:
        lines.append("现在待办/到期的提醒：")
        for d in due:
            if d["remind_at"] is None:
                t = "启动时提醒"
            else:
                t = datetime.fromtimestamp(d["remind_at"]).strftime("%m月%d日 %H:%M")
            lines.append(f"- {d['text']}（{t}）")
    mems = db.list_memories()
    if mems:
        lines.append("用户告诉过你的长期记忆：")
        for mm in mems:
            if mm["key"] != "课表":
                lines.append(f"- {mm['key']}：{mm['value']}")
    return "\n".join(lines)
