# -*- coding: utf-8 -*-
"""节目预告日期归一化与排序工具。"""

import re
from datetime import datetime, timedelta

from .categories import short_category_label, split_category_prefix


def normalize_date_text(date):
    date = re.sub(r'\s+', ' ', str(date or '')).strip()
    date = re.sub(r'^(今日)', '今天', date)
    date = re.sub(r'^(明日)', '明天', date)
    date = re.sub(r'^(后日)', '后天', date)
    date = re.sub(r'^(今天|明天|后天)\s+(\d{1,2}:\d{2})', r'\1\2', date)

    week_order = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '日': 7, '天': 7}
    m = re.fullmatch(r'(本周|下周)(?:周)?([一二三四五六日天])\s*(?:(\d{1,2}):(\d{2})|(\d{1,2})点)?\s*(上线|上映|开播|首播)?', date)
    if m:
        now = datetime.now()
        offset = (week_order[m.group(2)] - now.isoweekday()) % 7
        if m.group(1) == '下周':
            offset += 7
        target = now + timedelta(days=offset)
        if m.group(3) and m.group(4):
            time_part = f'{int(m.group(3))}:{m.group(4)}'
        elif m.group(5):
            time_part = f'{int(m.group(5))}:00'
        else:
            time_part = ''
        suffix = m.group(6) or ''
        return f'{target.month}月{target.day}日{time_part}{suffix}'

    suffixes = r'(上线|上映|开播|首播)?'
    patterns = (
        rf'(?:\d{{4}}[./-])?0?(\d{{1,2}})[./-]0?(\d{{1,2}})\s*(?:(\d{{1,2}}:\d{{2}}))?\s*{suffixes}',
        rf'0?(\d{{1,2}})月0?(\d{{1,2}})日\s*(?:(\d{{1,2}}:\d{{2}}))?\s*{suffixes}',
    )
    for pattern in patterns:
        m = re.fullmatch(pattern, date)
        if m:
            time_part = f' {m.group(3)}' if m.group(3) else ''
            suffix = m.group(4) or ''
            return f'{int(m.group(1))}月{int(m.group(2))}日{time_part}{suffix}'
    return date

def schedule_time_parts(text):
    """解析上线时间文本中的具体分钟，缺失时间时排到当天具体时间之后。"""
    tm = re.search(r'(\d{1,2}):(\d{2})', str(text or ''))
    if tm:
        return 0, int(tm.group(1)) * 60 + int(tm.group(2))
    tm = re.search(r'(\d{1,2})点', str(text or ''))
    if tm:
        return 0, int(tm.group(1)) * 60
    return 1, 23 * 60 + 59

def schedule_calendar_key(item, now=None):
    """统一四个平台的上线时间排序键。"""
    raw = str(item or '')
    date = calendar_date_text(raw.split('｜', 1)[0])
    now = datetime.now()
    timed_rank, minute = schedule_time_parts(date)

    def calendar_key(mon, day):
        year = now.year
        mon = int(mon)
        day = int(day)
        if (mon, day) < (now.month, now.day):
            year += 1
        return (0, year, mon, day, timed_rank, minute, raw)

    m = re.search(r'(?:\d{4}[./-])?(\d{1,2})[./-](\d{1,2})', date)
    if m:
        return calendar_key(m.group(1), m.group(2))
    m = re.search(r'(\d{1,2})月(\d{1,2})日', date)
    if m:
        return calendar_key(m.group(1), m.group(2))

    week_order = {'周一': 1, '周二': 2, '周三': 3, '周四': 4, '周五': 5, '周六': 6, '周日': 7, '周天': 7}
    m = re.search(r'(本周|下周)(?:周)?([一二三四五六日天])', date)
    if m:
        target_weekday = week_order.get('周' + m.group(2), 9)
        offset = (target_weekday - now.isoweekday()) % 7
        if m.group(1) == '下周':
            offset += 7
        target = now + timedelta(days=offset)
        return (0, target.year, target.month, target.day, timed_rank, minute, raw)

    return (9, now.year, 99, 99, 1, 23 * 60 + 59, raw)

def preview_target_date(text, now=None):
    """解析预告条目的目标上线月日，返回 date；无法解析返回 None。"""
    now = now or datetime.now()
    raw = str(text or '')
    date_text = calendar_date_text(raw.split('｜', 1)[0], now=now)
    m = re.search(r'(?:\d{4}[./-])?(\d{1,2})[./-](\d{1,2})', date_text)
    if not m:
        m = re.search(r'(\d{1,2})月(\d{1,2})日', date_text)
    if not m:
        return None
    try:
        return datetime(now.year, int(m.group(1)), int(m.group(2))).date()
    except ValueError:
        return None


def is_past_preview_item(item, now=None):
    """判断预告条目是否为已过上线日期的过期残留。

    仅剔除“今年已过且距今 60 天以内”的近期残留项。无法解析日期时保留；
    过线超过 60 天的早月份日期（如 7 月出现的 1月2日）视为次年新片而保留，
    与排序键里 year += 1 的跨年处理保持一致，避免误删年底的次年年初新片。
    """
    now = now or datetime.now()
    today = now.date()
    target = preview_target_date(item, now=now)
    if target is None or target >= today:
        return False
    gap = (today - target).days
    return 0 < gap <= 60


def drop_past_items(items, now=None):
    """剔除已过上线日期的过期预告条目。"""
    return [it for it in (items or []) if not is_past_preview_item(it, now=now)]


def sort_platform_items(items):
    """按统一上线时间轴排序平台预告条目。"""
    return sorted(items or [], key=schedule_calendar_key)

def format_preview_item(platform, item):
    """写入通知前统一把相对日期展开成具体日期。"""
    item = str(item)
    if platform == '爱奇艺':
        item = item.replace('即将上线｜', '节目预告｜', 1)
    if '｜' not in item:
        return item
    left, right = item.split('｜', 1)
    category, clean_right = split_category_prefix(right)
    date = calendar_date_text(left)
    if category:
        return f'[{short_category_label(category)}] {date}｜{clean_right}'
    return f'{date}｜{right}'

def calendar_date_text(text, now=None):
    """把今天、明天、后天展开成具体月日文本。"""
    now = now or datetime.now()
    date = normalize_date_text(text)
    rel = {'今天': 0, '明天': 1, '后天': 2}
    for label, offset in rel.items():
        if date.startswith(label):
            target = now + timedelta(days=offset)
            return f'{target.month}月{target.day}日{date[len(label):]}'
    return date

_normalize_date_text = normalize_date_text
_schedule_time_parts = schedule_time_parts
_schedule_calendar_key = schedule_calendar_key
_sort_platform_items = sort_platform_items
_format_preview_item = format_preview_item
_calendar_date_text = calendar_date_text
_preview_target_date = preview_target_date
_is_past_preview_item = is_past_preview_item
_drop_past_items = drop_past_items
