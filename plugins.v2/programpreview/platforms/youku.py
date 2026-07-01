# -*- coding: utf-8 -*-
"""优酷节目预告解析。"""

import asyncio
import json
import re
import urllib.request

from ..constants import UA
from ..date_utils import normalize_date_text, schedule_calendar_key, sort_platform_items
from ..text_utils import dedupe


YOUKU_CHANNELS = [
    ('main', 'https://www.youku.com/ku/webhome'),
    ('tv', 'https://tv.youku.com/'),
    ('comic', 'https://comic.youku.com/'),
    ('movie', 'https://movie.youku.com/'),
    ('zy', 'https://zy.youku.com/'),
]


def _youku_walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _youku_walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _youku_walk(v)

def _youku_tag_titles(item):
    tags = []
    for obj in _youku_walk(item):
        if isinstance(obj, dict) and isinstance(obj.get('title'), str):
            t = obj.get('title').strip()
            if t:
                tags.append(t)
    return tags

def _youku_initial_data_from_html(html):
    """从优酷 SSR HTML 中解析 window.__INITIAL_DATA__。"""
    text = str(html or '')
    marker = 'window.__INITIAL_DATA__'
    pos = text.find(marker)
    if pos < 0:
        return None
    eq = text.find('=', pos)
    if eq < 0:
        return None
    start = eq + 1
    end = text.find('</script>', start)
    raw = text[start:end if end >= 0 else len(text)].strip().rstrip(';')
    if not raw:
        return None
    # 优酷 SSR 数据偶尔把缺省图片字段写成 JS undefined，转成 JSON null 后再解析。
    raw = re.sub(r'(?<=[:\[,])\s*undefined\b', 'null', raw)
    try:
        return json.loads(raw)
    except Exception:
        return None

async def youku_initial_data(url):
    data = None
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = await browser.new_page(user_agent=UA)
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(1800)
            data = await page.evaluate('window.__INITIAL_DATA__ || null')
            await browser.close()
            if data:
                return data
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read().decode('utf-8', 'ignore')
        return _youku_initial_data_from_html(html)
    except Exception:
        return None

async def youku_all_initial_data():
    """优酷主频道 + 电视剧/动漫/电影/综艺频道。"""
    async def one(ch, url):
        return (ch, url, await youku_initial_data(url))
    return await asyncio.gather(*(one(ch, url) for ch, url in YOUKU_CHANNELS))

def _youku_text_title(obj):
    try:
        return obj.get('text', {}).get('title', '') or ''
    except Exception:
        return ''

def _youku_item_reason(item):
    try:
        return item.get('reason', {}).get('text', {}).get('title', '') or ''
    except Exception:
        return ''

def _youku_reserve_desc(item):
    reserve = item.get('reserve')
    if isinstance(reserve, dict):
        desc = reserve.get('desc') or ''
        if desc:
            return re.sub(r'已预约$', '预约', desc)
        cnt = reserve.get('count')
        if isinstance(cnt, (int, float)) and cnt > 0:
            return f'{cnt/10000:.1f}万人预约' if cnt >= 10000 else f'{int(cnt)}人预约'
    return ''

def _youku_normalize_date(date):
    date = re.sub(r'\s+', ' ', str(date or '')).strip()
    date = re.sub(r'^(剧・|影・|综・|漫・|少儿・|纪・)', '', date)
    return normalize_date_text(date)

def _youku_has_fixed_date(date):
    # 用户偏好：优酷只显示已定档内容，不显示“敬请期待”等未定档预约。
    date = _youku_normalize_date(date)
    return bool(re.search(r'(?:\d{1,2}月\d{1,2}日|\d{1,2}-\d{1,2}|今天|明天|后天).*?(?:上线|开播|首播|\d{1,2}:\d{2})', date))

def _youku_sort_key(item):
    return schedule_calendar_key(item)

def _youku_normalize_title(title):
    title = re.sub(r'\s+', ' ', str(title or '')).strip()
    title = re.sub(r'\s*(?:第[一二三四五六七八九十百千万\d]+季|第[一二三四五六七八九十百千万\d]+期|[1234567890]+)$', '', title).strip()
    return title

def _dedupe_youku_items(items, limit=50):
    best = {}
    order = []
    for raw in items:
        left, sep, right = str(raw).partition('｜')
        if not sep or not _youku_has_fixed_date(left):
            continue
        title_key = re.sub(r'（[^）]*预约）$', '', right)
        key = (_youku_normalize_date(left), _youku_normalize_title(title_key))
        item = f'{key[0]}｜{right}'
        if key not in best:
            order.append(key); best[key] = item
        elif '预约）' in item and '预约）' not in best[key]:
            best[key] = item
    return [best[k] for k in order[:limit]]

def _youku_extract_reserve_modules(data):
    """只从标题包含“即将上线”的优酷预约模块提取卡片，避免混入热播/推荐流。"""
    items = []
    if not data:
        return items
    for module in _youku_walk(data):
        if not isinstance(module, dict):
            continue
        title = str(module.get('title') or '')
        item_list = module.get('itemList')
        if '即将上线' not in title or not isinstance(item_list, list):
            continue
        for item in item_list:
            if not isinstance(item, dict):
                continue
            name = str(item.get('title') or '').strip()
            if not name or len(name) > 60 or re.search(r'上线|预约榜|TOP$', name):
                continue
            reason = _youku_item_reason(item)
            lb = item.get('lbTexts') or ''
            tags = _youku_tag_titles(item)
            tag_date = next((t for t in tags if '上线' in t and t != '预约榜'), '')
            date = tag_date or (lb if '上线' in str(lb) else '') or reason or ''
            date = _youku_normalize_date(date)
            if not _youku_has_fixed_date(date):
                continue
            reserve = _youku_reserve_desc(item)
            suffix = f'（{reserve}）' if reserve else ''
            items.append(f'{date}｜{name}{suffix}')
    return sorted(_dedupe_youku_items(items, 50), key=_youku_sort_key)

def extract_youku_from_data(data):
    """从优酷 __INITIAL_DATA__ 提取预约/即将上线条目，优先限定在“即将上线”模块。"""
    module_items = _youku_extract_reserve_modules(data)
    if module_items:
        return module_items
    items = []
    if not data:
        return items
    for item in _youku_walk(data):
        if not isinstance(item, dict) or not isinstance(item.get('title'), str):
            continue
        if not (item.get('action_type') or item.get('action_value') or item.get('img') or item.get('hImg')):
            continue
        title = item.get('title', '').strip()
        if not title or len(title) > 50 or re.search(r'上线|预约榜|新剧预约|TOP$', title):
            continue
        lb = item.get('lbTexts', '') or ''
        reason = _youku_item_reason(item)
        top = ''
        try:
            top = item.get('topLeftMark', {}).get('text', {}).get('title', '') or ''
        except Exception:
            pass
        tags = _youku_tag_titles(item)
        up_tags = [t for t in tags if re.search(r'上线|预约', t)]
        marker = ' '.join([lb, reason, top] + up_tags)
        if re.search(r'上线|预约榜|新剧预约|即将上线', marker):
            date = next((t for t in up_tags if '上线' in t and t != '预约榜'), '')
            if not date and '上线' in lb:
                date = lb
            if not date:
                date = reason or top or ''
            date = _youku_normalize_date(date)
            if not _youku_has_fixed_date(date):
                continue
            reserve = _youku_reserve_desc(item)
            suffix = f'（{reserve}）' if reserve else ''
            items.append(f'{date}｜{title}{suffix}')
    return sorted(_dedupe_youku_items(items, 50), key=_youku_sort_key)

def _youku_text_title_candidate(line, meta):
    title = re.sub(r'\s+', ' ', str(line or '')).strip(' -｜|')
    if not title or len(title) > 60:
        return ''
    if meta.search(title) or _youku_has_fixed_date(title):
        return ''
    if re.fullmatch(r'\d+(?:\.\d+)?万?', title):
        return ''
    if re.search(r'预约|上线|热度榜|预约榜|更新至\d+', title):
        return ''
    return title

def _youku_inline_text_parts(line, meta):
    text = re.sub(r'\s+', ' ', str(line or '')).strip()
    patterns = (
        r'(?:^|\s)(?:剧・|综・|影・|漫・|少儿・|纪・)?'
        r'((?:\d{1,2}[./-]\d{1,2}|\d{1,2}月\d{1,2}日|今天|明天|后天)'
        r'(?:\s*\d{1,2}:\d{2})?\s*(?:上线|开播|首播))\s+(.+)$',
    )
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            date = _youku_normalize_date(m.group(1))
            title = _youku_text_title_candidate(m.group(2), meta)
            if _youku_has_fixed_date(date) and title:
                return date, title
    return '', ''

def _youku_nearby_text_title(lines, index, meta):
    for step in range(1, 5):
        pos = index + step
        if pos < len(lines):
            title = _youku_text_title_candidate(lines[pos], meta)
            if title:
                return title
    for step in range(1, 4):
        pos = index - step
        if pos >= 0:
            title = _youku_text_title_candidate(lines[pos], meta)
            if title:
                return title
    return ''

def extract_youku(lines):
    """文本兜底：尽量把日期与相邻片名配对，避免只输出日期。"""
    items = []
    meta = re.compile(r'^(TOP|VIP|剧・|综・|影|漫・|少儿・|纪・|预告|预约榜|热度榜|独播|首播|限免中|预约破)$')
    for index, line in enumerate(lines):
        if re.search(r'(\d{2}-\d{2}\s*)?上线|即将上线|预约', line):
            inline_date, inline_title = _youku_inline_text_parts(line, meta)
            date = inline_date or _youku_normalize_date(line)
            if not meta.search(date) and _youku_has_fixed_date(date):
                title = inline_title or _youku_nearby_text_title(lines, index, meta)
                items.append(f'{date}｜{title}' if title else date)
    return dedupe(items, 12)

dedupe_youku_items = _dedupe_youku_items
