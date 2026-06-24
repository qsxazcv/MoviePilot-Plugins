#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四大平台即将上线/预约节目预告抓取。"""
import argparse
import asyncio
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
DATA_DIR = Path('/config/plugins/programpreview')
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = DATA_DIR / 'latest_preview.md'
STATE_FILE = DATA_DIR / 'state.json'
PLATFORM_CACHE_FILE = DATA_DIR / 'platform_cache.json'
OUT_FILE.touch(exist_ok=True)
PLATFORM_CACHE_TTL_HOURS = 72

SITES = [
    ('爱奇艺', 'https://www.iqiyi.com/'),
    ('腾讯视频', 'https://v.qq.com/channel/tv'),
    ('芒果TV', 'https://www.mgtv.com'),
    ('优酷', 'https://www.youku.com/ku/webhome'),
]

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
_IQIYI_SEARCH_RESERVE_CACHE = {}


def _iqiyi_reset_run_caches():
    _IQIYI_SEARCH_RESERVE_CACHE.clear()


def clean_lines(text):
    lines = []
    for line in re.split(r'[\n\r]+', text or ''):
        line = re.sub(r'\s+', ' ', line).strip()
        if not line:
            continue
        if len(line) > 120:
            continue
        lines.append(line)
    return lines


def dedupe(items, limit=12):
    seen = set(); out = []
    for item in items:
        item = re.sub(r'\s+', ' ', str(item)).strip(' -｜|')
        if not item or item in seen:
            continue
        if re.fullmatch(r'[\d\W_]+', item):
            continue
        seen.add(item); out.append(item)
    return out[:limit]


def _normalize_date_text(date):
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

def _schedule_time_parts(text):
    """解析上线时间文本中的具体分钟，缺失时间时排到当天具体时间之后。"""
    tm = re.search(r'(\d{1,2}):(\d{2})', str(text or ''))
    if tm:
        return 0, int(tm.group(1)) * 60 + int(tm.group(2))
    tm = re.search(r'(\d{1,2})点', str(text or ''))
    if tm:
        return 0, int(tm.group(1)) * 60
    return 1, 23 * 60 + 59


def _schedule_calendar_key(item):
    """统一四个平台的上线时间排序键。"""
    raw = str(item or '')
    date = _calendar_date_text(raw.split('｜', 1)[0])
    now = datetime.now()
    timed_rank, minute = _schedule_time_parts(date)

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


def _sort_platform_items(items):
    """按统一上线时间轴排序平台预告条目。"""
    return sorted(items or [], key=_schedule_calendar_key)


def _calendar_date_text(text, now=None):
    """把今天、明天、后天展开成具体月日文本。"""
    now = now or datetime.now()
    date = _normalize_date_text(text)
    rel = {'今天': 0, '明天': 1, '后天': 2}
    for label, offset in rel.items():
        if date.startswith(label):
            target = now + timedelta(days=offset)
            return f'{target.month}月{target.day}日{date[len(label):]}'
    return date

async def page_text(url, wait=5000):
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = await browser.new_page(user_agent=UA)
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(min(wait, 2500))
            text = await page.locator('body').inner_text(timeout=15000)
            await browser.close()
            return text
    except Exception:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read().decode('utf-8', 'ignore')
        return re.sub(r'<[^>]+>', '\n', html)


async def page_html_text(url, wait=5000):
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = await browser.new_page(user_agent=UA)
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(min(wait, 2500))
            text = await page.locator('body').inner_text(timeout=15000)
            html = await page.content()
            await browser.close()
            return html, text
    except Exception:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read().decode('utf-8', 'ignore')
        return html, re.sub(r'<[^>]+>', '\n', html)


async def iqiyi_filtered_page_html_text(url, wait=5000):
    """Load an iQIYI list page and activate the visible upcoming filter."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = await browser.new_page(user_agent=UA, viewport={'width': 1366, 'height': 900})
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(min(wait, 2500))
            for label in ('即将上线', '最热'):
                try:
                    loc = page.get_by_text(label, exact=True).first
                    if await loc.count():
                        await loc.click(timeout=2500)
                        await page.wait_for_timeout(1500)
                except Exception:
                    continue
            text = await page.locator('body').inner_text(timeout=15000)
            html = await page.content()
            await browser.close()
            return html, text
    except Exception:
        return await page_html_text(url, wait=wait)



async def tencent_page_html_text(url):
    # 按用户偏好：腾讯只抓各频道页里的“即将上线”模块，不合并首页或其它推荐流。
    try:
        from playwright.async_api import async_playwright
        channels = ['tv', 'tvdrama', 'cartoon', 'variety', 'movie']
        out = []
        page_jsons = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = await browser.new_page(user_agent=UA, viewport={'width': 1366, 'height': 900})
            async def _capture_response(resp):
                # 腾讯频道新版页面把更完整的频道模块放在 PageService JSON 中；记录下来供解析函数兜底使用。
                if 'PageService/getPage' in resp.url:
                    try:
                        page_jsons.append(await resp.json())
                    except Exception:
                        pass
            page.on('response', lambda resp: asyncio.create_task(_capture_response(resp)))
            for ch in channels:
                # 每个频道只附带自己的 PageService 响应，避免前一频道结构化数据污染后续频道。
                page_jsons.clear()
                page_url = f'https://v.qq.com/channel/{ch}?listpage=2&channel={ch}&itype=1'
                await page.goto(page_url, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_timeout(2500)
                # 频道页“即将上线”Tab 默认不一定被激活；腾讯页面有两个同名 Tab，前一个才是目标模块，
                # 之前点 last() 会落到错误推荐区，导致漏掉《镖人 第2季》《诡秘之主特别篇》。
                html_parts = []
                text_parts = []
                try:
                    loc = page.get_by_text('即将上线', exact=True)
                    n = await loc.count()
                    # 先点第一个“即将上线”，它对应截图里的真实预约排期模块。
                    if n:
                        await loc.nth(0).click(timeout=3000, force=True)
                        await page.wait_for_timeout(1200)
                        html_parts.append(await page.content())
                        text_parts.append(await page.locator('body').inner_text(timeout=15000))
                    # 动漫频道“即将上线”有换一换分页，补点几轮把后续预约卡片也收进来。
                    if ch == 'cartoon':
                        for _ in range(1):
                            swap = page.get_by_text('换一换', exact=True)
                            if await swap.count() <= 0:
                                break
                            await swap.first.click(timeout=3000, force=True)
                            await page.wait_for_timeout(1000)
                            html_parts.append(await page.content())
                            text_parts.append(await page.locator('body').inner_text(timeout=15000))
                except Exception:
                    pass
                if not html_parts:
                    html_parts.append(await page.content())
                if not text_parts:
                    text_parts.append(await page.locator('body').inner_text(timeout=15000))
                html = '\n'.join(html_parts)
                # 解析器会优先取最后一个“即将上线”模块；把首次点击得到的真实排期模块放到最后，
                # 避免后续“换一换”的推荐流覆盖《镖人 第2季》《诡秘之主特别篇》等动漫预约卡片。
                text = '\n'.join((text_parts[1:] + text_parts[:1]) if ch == 'cartoon' and len(text_parts) > 1 else text_parts)
                # 附带 JSON 响应，避免页面文本只显示首屏少量条目时漏掉结构化数据。
                html = html + '\n<script id="__MP_CAPTURED_PAGESERVICE__" type="application/json">' + json.dumps(page_jsons, ensure_ascii=False) + '</script>'
                out.append((ch, html, text))
            await browser.close()
        return out
    except Exception:
        html, text = await page_html_text('https://v.qq.com/channel/tv', wait=5000)
        return [('tv', html, text)]


def _html_unescape(x):
    import html
    return html.unescape(x or '')



def _tencent_parse_text_module(text):
    """解析腾讯频道页已激活的“即将上线”模块文本。"""
    lines = clean_lines(text)
    items = []
    meta = re.compile(r'^(即将上线|今日推荐|推荐|最新|高分|免费|横屏短剧|竖屏短剧|N刷榜|女频榜|男频榜|热搜榜|飙升榜|游戏综艺榜|情感综艺榜|音乐舞台榜|喜剧综艺榜|脱口秀综艺榜|热播榜|换一换|预约)$')
    starts = [i for i, x in enumerate(lines) if x == '即将上线']
    if not starts:
        return []
    i = starts[-1] + 1
    # 跳过同模块 tab、榜单名、换一换等头部文字。
    while i < len(lines) and (meta.search(lines[i]) or re.fullmatch(r'[A-Za-z]+', lines[i])):
        i += 1
    end_mark = re.compile(r'^(为你推荐|电视剧片库|电影片库|动漫片库|综艺片库|周一|周二|周三|周四|今天|周六|周日|广告)$')
    pending_date = ''
    while i < len(lines) and len(items) < 20:
        if end_mark.search(lines[i]) and not re.fullmatch(r'今天|明天|后天', lines[i]):
            break
        date = ''
        # 形如：6月 / 7日 / 37.5万人预约 / 迷墙 / 预约 / 简介
        if re.fullmatch(r'\d{1,2}月', lines[i]) and i + 1 < len(lines) and re.fullmatch(r'\d{1,2}日', lines[i+1]):
            date = lines[i] + lines[i+1]
            pending_date = date
            i += 2
        elif lines[i] in {'今天', '明天', '后天'}:
            date = lines[i]
            if i + 1 < len(lines) and re.fullmatch(r'\d{1,2}:\d{2}', lines[i+1]):
                date += lines[i+1]
                i += 2
            else:
                i += 1
            pending_date = date
        elif i + 1 < len(lines) and lines[i] == '敬请' and lines[i+1] == '期待':
            # 用户偏好：腾讯视频只保留有具体上线日期/时间的预告，跳过“敬请期待”。
            i += 2
            continue
        elif re.fullmatch(r'\d{1,2}月\d{1,2}日(?:上线|开播|首播)?', lines[i]):
            date = lines[i]
            pending_date = date
            i += 1
        else:
            i += 1
            continue
        reserve = ''
        if i < len(lines) and re.fullmatch(r'[\d.]+(?:万)?人预约', lines[i]):
            reserve = lines[i]
            i += 1
        # 腾讯动漫卡片常把日期压在图片左上角，正文解析时可能表现为：6月/20日/预约人数/标题；
        # 也可能因懒加载只剩“预约/6月20日上线/标题”。若当前卡没有独立日期，沿用上一张图片日期。
        if not date and pending_date and reserve:
            date = pending_date
        title = ''
        while i < len(lines):
            cand = lines[i].strip('"')
            # 腾讯页面的排期/星期标签偶尔会紧跟在“今天/明天/后天”后面，不能当作节目名。
            if cand == '预约' or re.fullmatch(r'(?:今天|明天|后天|\d{1,2}:\d{2}|\d{1,2}月|\d{1,2}日|上新|更新至\d+集|周一|周二|周三|周四|周五|周六|周日|周天|星期[一二三四五六日天])', cand) or re.search(r'人预约|即将上线|换一换', cand) or len(cand) < 2 or len(cand) > 45:
                i += 1
                continue
            title = cand
            i += 1
            break
        if title:
            # 标题里偶尔自带“·6月25日首播”，优先把日期归到左侧，标题保持干净。
            mt = re.match(r'(.+?)·(\d{1,2}月\d{1,2}日(?:上线|开播|首播))$', title)
            if mt:
                title, date = mt.group(1), mt.group(2)
            date = re.sub(r'(上线|开播|首播)$', '', date)
            # 用户只要具体节目预告：腾讯侧必须带明确日期/时间；
            # 过滤“今天｜仙逆”这类仅有相对日期、无具体时间/预约数/明确日期的更新状态条目。
            has_specific_date = bool(re.search(r'(?:\d{1,2}月\d{1,2}日|今天\d{1,2}:\d{2}|明天\d{1,2}:\d{2}|后天\d{1,2}:\d{2})', date))
            if not has_specific_date or not _tencent_date_is_future(date):
                continue
            suffix = f'（{reserve}）' if reserve else ''
            items.append(f'{date}｜{title}{suffix}')
    return items


def _tencent_sort_key(item):
    return _schedule_calendar_key(item)


def _sort_tencent_items(items):
    return _sort_platform_items(items)


def _tencent_date_is_future(date, now=None):
    """Return True only when a Tencent preview date is still upcoming."""
    now = now or datetime.now()
    date = _normalize_date_text(date)
    rel = {'今天': 0, '明天': 1, '后天': 2}
    for label, offset in rel.items():
        if date.startswith(label):
            target = now + timedelta(days=offset)
            date = f'{target.month}月{target.day}日{date[len(label):]}'
            break
    tm = re.search(r'(\d{1,2}):(\d{2})', date)
    rel = {'今天': 0, '明天': 1, '后天': 2}
    for label, offset in rel.items():
        if date.startswith(label):
            if offset > 0:
                return True
            if not tm:
                return False
            minutes = int(tm.group(1)) * 60 + int(tm.group(2))
            return minutes > now.hour * 60 + now.minute
    m = re.search(r'(\d{1,2})月(\d{1,2})日', date)
    if not m:
        return False
    mo, day = int(m.group(1)), int(m.group(2))
    year = now.year
    if (mo, day) < (now.month, now.day) and now.month >= 11 and mo <= 2:
        year += 1
    if tm:
        target = datetime(year, mo, day, int(tm.group(1)), int(tm.group(2)))
        return target > now
    return (year, mo, day) > (now.year, now.month, now.day)


def _filter_future_tencent_items(items, now=None):
    return [item for item in items or [] if _tencent_date_is_future(str(item).split('｜', 1)[0], now=now)]


def _merge_tencent_items_with_cache(items, cache_name='腾讯视频'):
    """腾讯动态页偶发漏卡时，用同日缓存做保底合并。

    只回填缓存中仍未到上线时间的条目，避免当天已上线节目继续显示。
    """
    merged = _filter_future_tencent_items(items)
    try:
        cache = load_platform_cache()
        old = cache.get(cache_name, {}) if isinstance(cache, dict) else {}
        old_items = old.get('items') or []
        now = datetime.now()
        def _keep(item):
            return _tencent_date_is_future(str(item).split('｜', 1)[0], now=now)
        for item in old_items:
            if _keep(item):
                merged.append(item)
    except Exception:
        pass
    return _sort_tencent_items(_dedupe_tencent_items(merged, 50))


def _normalize_tencent_title(title):
    original = str(title or '').strip()
    title = re.sub(r'[·・\s]*\d{1,2}月\d{1,2}日(?:上线|开播|首播)?$', '', original).strip()
    # 去掉平台常见季/期后缀，便于把“半熟恋人”和“半熟恋人 第5季”归并为同一节目。
    title = re.sub(r'\s*(?:第[一二三四五六七八九十百千万\d]+季|第[一二三四五六七八九十百千万\d]+期|第[一二三四五六七八九十百千万\d]+部)$', '', title).strip()
    # 腾讯动漫有时同一作品会出现短名/长名两种卡片，归并显示为短名，避免“斩神”和“斩神之凡尘神域”重复。
    if title.startswith('斩神'):
        title = '斩神'
    return title or original


def _normalize_tencent_item(item):
    left, sep, right = str(item).partition('｜')
    if not sep:
        return str(item)
    left = _normalize_date_text(left)
    title = right
    suffix = ''
    m = re.search(r'(（[^）]*预约）)$', title)
    if m:
        suffix = m.group(1)
        title = title[:m.start()]
    return f'{left}｜{_normalize_tencent_title(title)}{suffix}'


def _tencent_date_specificity(date):
    """日期越具体分越高：后天12:00 > 6月1日 > 敬请期待。"""
    date = str(date or '')
    score = 0
    if re.search(r'(今天|明天|后天|\d{1,2}月\d{1,2}日)', date):
        score += 10
    if re.search(r'\d{1,2}:\d{2}', date):
        score += 10
    if '敬请期待' in date or '即将上线' in date:
        score -= 10
    return score


def _tencent_item_score(item):
    left, _, right = str(item).partition('｜')
    score = _tencent_date_specificity(left)
    if re.search(r'（[^）]*预约）$', right):
        score += 5
    # 同名重复时，优先保留页面可见模块里带具体时间/预约人数的版本。
    return score


def _dedupe_tencent_items(items, limit=30):
    """腾讯条目按归一化标题去重；同一节目优先保留日期更具体、带预约人数的版本。"""
    best = {}
    order = []
    for raw in items:
        item = _normalize_tencent_item(raw)
        left, sep, right = item.partition('｜')
        if not sep:
            continue
        title_key = re.sub(r'（[^）]*预约）$', '', right)
        title_key = re.sub(r'\s+', '', title_key)
        # 去掉季数后如果标题太短则仍保留原标题，避免误合并完全不同节目。
        key = title_key
        if key not in best:
            order.append(key)
            best[key] = item
        elif _tencent_item_score(item) > _tencent_item_score(best[key]):
            best[key] = item
    return [best[k] for k in order if k in best][:limit]


def _tencent_extract_json_items(html):
    """从腾讯 PageService/SSR JSON 中提取带明确上线日期且仍处于预约态的“即将上线”条目。

    这样可补齐频道页文本首屏只露出 1-2 条时遗漏的动漫/综艺等条目，同时继续遵守：
    只保留有具体日期，过滤“敬请期待”和已更新/已上线常规推荐。
    """
    raw = html or ''
    blobs = []
    m = re.search(r'<script id="__MP_CAPTURED_PAGESERVICE__" type="application/json">(.*?)</script>', raw, re.S)
    if m:
        try:
            blobs.extend(json.loads(_html_unescape(m.group(1))))
        except Exception:
            pass

    def walk(o):
        if isinstance(o, dict):
            params = o.get('params') if isinstance(o.get('params'), dict) else o
            title = params.get('priority_title') or params.get('title') or params.get('mz_title') or params.get('name') or ''
            mark_text = ' '.join(str(params.get(k) or '') for k in params if re.match(r'marklabel_\d+_prime_text$', str(k)))
            uni = str(params.get('uni_imgtag') or '')
            holly = str(params.get('holly_online_time') or '')
            publish = str(params.get('publish_date') or '')
            blob = ' '.join([title, mark_text, uni, holly, publish])
            # 只抓“预约”态，避免把每日更新、全集上线、已开播内容混入即将上线预告。
            if '预约' in blob and '敬请期待' not in blob and title:
                date = ''
                m1 = re.search(r'(\d{1,2})月(\d{1,2})日\s*(?:(\d{1,2}):(\d{2})|(\d{1,2})点)?(?:上线|开播|首播)?', blob)
                if m1:
                    # 输出统一为“M月D日｜标题”，避免“6月25日首播｜斩神2”和“6月25日｜斩神2”重复。
                    date = f'{m1.group(1)}月{m1.group(2)}日'
                    if m1.group(3) and m1.group(4):
                        date += f' {int(m1.group(3))}:{m1.group(4)}'
                    elif m1.group(5):
                        date += f' {int(m1.group(5))}:00'
                elif re.fullmatch(r'\d{4}-\d{2}-\d{2}', publish):
                    try:
                        y, mo, d = publish.split('-')
                        date = f'{int(mo)}月{int(d)}日'
                    except Exception:
                        pass
                if date and _tencent_date_is_future(date):
                    title = re.sub(r'[·・\s]*\d{1,2}月\d{1,2}日(?:上线|开播|首播)?$', '', str(title)).strip()
                    reserve = ''
                    rm = re.search(r'[\d.]+(?:万)?人预约', blob)
                    if rm:
                        reserve = rm.group(0)
                    if title and 2 <= len(title) <= 45:
                        yield f'{date}｜{title}' + (f'（{reserve}）' if reserve else '')
            for v in o.values():
                yield from walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)

    items = []
    for b in blobs:
        items.extend(walk(b))
    return items


def extract_tencent_html(html, text):
    """腾讯各频道“即将上线”模块：解析激活 Tab 文本，并用 PageService 结构化数据补齐漏项。"""
    items = []
    # 结构化数据里能识别“预约+明确日期”的条目，优先用于补齐动漫等频道首屏漏项。
    items.extend(_tencent_extract_json_items(html))
    items.extend(_tencent_parse_text_module(text))
    html = _html_unescape(html)
    # 极端兜底：频道页首屏只暴露“标题·日期”时使用。
    for title, date in re.findall(r'(?:title|name):"([^"·]{2,40})·(\d{1,2}月\d{1,2}日(?:开播|上线|首播))"', html):
        date = re.sub(r'(上线|开播|首播)$', '', date)
        items.append(f'{date}｜{title}')
    return _sort_tencent_items(_filter_future_tencent_items(_dedupe_tencent_items(items, 30)))


IQIYI_CHANNELS = [
    ('tv', 'https://www.iqiyi.com/list/tv/%E5%85%A8%E9%83%A8%E5%89%A7%E9%9B%86.html'),
    ('movie', 'https://www.iqiyi.com/list/movie/%E5%85%A8%E9%83%A8%E7%94%B5%E5%BD%B1.html'),
    ('variety', 'https://www.iqiyi.com/list/variety/%E5%85%A8%E9%83%A8.html'),
    ('comic', 'https://www.iqiyi.com/list/comic/%E5%85%A8%E9%83%A8%E5%8A%A8%E6%BC%AB.html'),
    ('documentary', 'https://www.iqiyi.com/list/documentary/%E5%85%A8%E9%83%A8.html'),
]


IQIYI_LIST_CHANNELS = [
    ('tv', 2, 'https://www.iqiyi.com/list/tv/%E5%85%A8%E9%83%A8%E5%89%A7%E9%9B%86.html'),
    ('movie', 1, 'https://www.iqiyi.com/list/movie/%E5%85%A8%E9%83%A8%E7%94%B5%E5%BD%B1.html'),
    ('variety', 6, 'https://www.iqiyi.com/list/variety/%E5%85%A8%E9%83%A8.html'),
    ('comic', 4, 'https://www.iqiyi.com/list/comic/%E5%85%A8%E9%83%A8%E5%8A%A8%E6%BC%AB.html'),
    ('documentary', 3, 'https://www.iqiyi.com/list/documentary/%E5%85%A8%E9%83%A8.html'),
]


IQIYI_HOME_PREVIEW_CHANNELS = [
    ('home_new_preview', 'https://www.iqiyi.com/'),
]


IQIYI_RANK_CHANNELS = [
    ('rank_tv_reserve', 'https://www.iqiyi.com/ranks1/2/-8'),
    ('rank_documentary_reserve', 'https://www.iqiyi.com/ranks1/3/-8'),
    ('rank_all_reserve', 'https://www.iqiyi.com/ranks1PCA/-1/-8'),
]


def _iqiyi_is_program_preview_date(date):
    date = re.sub(r'\s+', '', str(date or '')).strip('：:')
    return date in {'即将上线', '节目预告', '未定时', '待定', '敬请期待'}


def _iqiyi_normalize_date(date):
    date = _calendar_date_text(date)
    return '节目预告' if _iqiyi_is_program_preview_date(date) else date


def _iqiyi_sort_key(item):
    item = re.sub(r'（[^）]*(?:人预约|人已预约|预约破[\d.]+(?:万|千|百)?)）$', '', str(item))
    date = item.split('｜', 1)[0]
    if _iqiyi_is_program_preview_date(date):
        now = datetime.now()
        return (8, now.year, 99, 99, 1, 23 * 60 + 59, item)
    return _schedule_calendar_key(item)


def _iqiyi_split_title_reserve(right):
    right = re.sub(r'\s+', ' ', str(right or '')).strip()
    m = re.search(r'^(.*?)(（[^）]*(?:人预约|人已预约|预约破[\d.]+(?:万|千|百)?)）)$', right)
    if m:
        return m.group(1).strip(), m.group(2)
    return right, ''


def _iqiyi_find_reserve_near(text):
    text = _html_unescape(text or '')
    for pat in (
        r'(预约破[\d.]+(?:万|千|百)?)',
        r'([\d.]+(?:万)?人已预约)',
        r'([\d.]+(?:万)?人预约)',
        r'(?:预约人数|预约数|appoint(?:Count|Num|Cnt)?|reserve(?:Count|Num|Cnt)?|subscribe(?:Count|Num|Cnt)?|book(?:Count|Num|Cnt)?)[^\d]{0,20}(\d{2,9})',
        r'(?:预约人数|预约数|appoint(?:Count|Num|Cnt)?|reserve(?:Count|Num|Cnt)?|subscribe(?:Count|Num|Cnt)?|book(?:Count|Num|Cnt)?)[^\d]{0,20}([\d.]+万)',
    ):
        m = re.search(pat, text, re.I)
        if not m:
            continue
        val = m.group(1)
        if val.startswith('预约破') or val.endswith('人已预约'):
            return val
        if re.fullmatch(r'\d{1,9}', val):
            num = int(val)
            return f'{num/10000:.1f}万人预约' if num >= 10000 else f'{num}人预约'
        return val if val.endswith('人预约') else f'{val}人预约'
    return ''


def _iqiyi_format_reserve_count(count):
    try:
        count = int(float(count))
    except Exception:
        return ''
    if count <= 0:
        return ''
    return f'{count / 10000:.1f}万人已预约' if count >= 10000 else f'{count}人已预约'


def _iqiyi_extract_jsonp(text):
    text = text or ''
    m = re.search(r'callback\((\{.*?\})\)', text, re.S)
    if not m:
        m = re.search(r'^[^(]*\((\{.*?\})\)\s*;?\s*$', text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def _iqiyi_subscribe_count_sync(qipu_ids):
    ids = []
    for qid in qipu_ids or []:
        qid = str(qid or '').strip()
        if qid and qid.isdigit() and qid not in ids:
            ids.append(qid)
    if not ids:
        return {}
    result = {}
    # 爱奇艺移动端使用 subscription countAndState；subType=2 与详情页“X万人已预约”一致。
    for i in range(0, len(ids), 20):
        batch = ids[i:i + 20]
        params = urllib.parse.urlencode({
            'subKeys': ','.join(batch),
            'subType': 2,
            'agentType': 13,
            'callback': 'callback',
        })
        url = f'https://subscription.iqiyi.com/services/subscribe/countAndState.htm?{params}'
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': UA,
                'Referer': 'https://m.iqiyi.com/',
            })
            text = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', 'ignore')
            data = _iqiyi_extract_jsonp(text) or {}
            if data.get('code') != 'A00000':
                continue
            rows = data.get('data') or {}
            if not isinstance(rows, dict):
                continue
            for key, val in rows.items():
                if isinstance(val, dict):
                    desc = _iqiyi_format_reserve_count(val.get('count'))
                    if desc:
                        result[str(key)] = desc
        except Exception:
            continue
    return result



def _iqiyi_is_short_drama_obj(obj):
    """过滤爱奇艺短剧/微短剧相关条目。"""
    if not isinstance(obj, dict):
        return False
    try:
        # 15 是常见短剧频道；35/37 不再仅凭频道号过滤，避免误杀正常即将上线条目。
        if int(obj.get('channel_id') or -1) in {15}:
            return True
    except Exception:
        pass
    page_url = str(obj.get('page_url') or obj.get('url') or '')
    # a_*.html 是爱奇艺专辑页，不能直接当短剧；只过滤明确 mini 播放形态。
    if re.search(r'playertype=mini', page_url):
        return True
    fields = []
    for key in ('title', 'display_name', 'short_display_name', 'desc', 'description', 'channel_name', 'name'):
        val = obj.get(key)
        if val:
            fields.append(str(val))
    for key in ('tag2lines', 'tag3lines'):
        val = obj.get(key)
        if isinstance(val, list):
            fields.extend(str(x.get('text') or x.get('name') or '') for x in val if isinstance(x, dict))
    blob = ' '.join(fields)
    return bool(re.search(r'微短剧|短剧|豪门|甜宠|灵魂互换', blob))


def _iqiyi_is_filtered_male_fantasy_obj(obj):
    """过滤用户不想要的爱奇艺男频玄幻漫剧/动态漫倾向条目。"""
    if not isinstance(obj, dict):
        return False
    fields = []
    for key in ('tag', 'title', 'display_name', 'short_display_name', 'desc', 'description', 'channel_name', 'name'):
        val = obj.get(key)
        if val:
            fields.append(str(val))
    for key in ('tag2lines', 'tag3lines'):
        val = obj.get(key)
        if isinstance(val, list):
            fields.extend(str(x.get('text') or x.get('name') or '') for x in val if isinstance(x, dict))
    blob = ' '.join(fields)
    # 命中“男频 + 玄幻/架空/大男主/漫剧/动态漫”等组合时过滤；避免单个“玄幻”误杀普通动漫。
    return bool(re.search(r'男频', blob) and re.search(r'玄幻|架空|大男主|漫剧|动态漫|逆袭', blob))



def _iqiyi_extract_page_reserve_sync(url):
    """从爱奇艺移动/播放页兜底提取预约人数或 aid/tvid 后查询预约数。"""
    url = str(url or '').strip()
    if not url:
        return ''
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
            'Referer': 'https://m.iqiyi.com/',
        })
        text = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', 'ignore')
    except Exception:
        return ''
    text = _html_unescape(text)
    # 页面直接渲染的预约人数，优先使用。
    for pat in (
        r'([\d.]+(?:万)?人已预约)',
        r'<div[^>]*class="m-subscribe-top-item"[^>]*>\s*(\d{1,9})\s*</div>\s*<div[^>]*class="m-subscribe-buttom-item"[^>]*>\s*预约人数\s*</div>',
        r'"subscribe(?:Count|Num|Cnt)?"\s*:\s*(\d{1,9})',
        r'"count"\s*:\s*(\d{1,9})[^{}]{0,80}"state"',
    ):
        m = re.search(pat, text, re.I | re.S)
        if not m:
            continue
        val = m.group(1)
        if val.endswith('人已预约'):
            return val
        try:
            num = int(float(val))
            if num > 0:
                return _iqiyi_format_reserve_count(num)
        except Exception:
            pass
    ids = []
    # 分享页可能带 shareId=base64(qipuId)。
    sm = re.search(r'[?&]shareId=([^&]+)', url)
    if sm:
        try:
            import base64
            qid = base64.b64decode(urllib.parse.unquote(sm.group(1))).decode('utf-8', 'ignore').strip()
            if qid.isdigit():
                ids.append(qid)
        except Exception:
            pass
    for pat in (
        r'"(?:tvid|tvId|aid|albumId|album_id|entity_id)"\s*:\s*"?(\d{6,})"?',
        r'(?:tvid|tvId|aid|albumId|album_id|entity_id)=(\d{6,})',
        r'''qips://[^"']*(?:tvid|albumid|fid)=(\d{6,})''',
    ):
        for m in re.finditer(pat, text, re.I):
            qid = m.group(1)
            if qid not in ids:
                ids.append(qid)
    reserve_map = _iqiyi_subscribe_count_sync(ids)
    return next(iter(reserve_map.values()), '') if reserve_map else ''


def _iqiyi_search_page_reserve_once_sync(title):
    """单次从爱奇艺搜索页按片名兜底提取预约人数，不跨平台混用。"""
    title = re.sub(r'\s+', ' ', str(title or '')).strip()
    if not title:
        return ''
    url = 'https://www.iqiyi.com/search/' + urllib.parse.quote(title) + '.html'
    texts = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = browser.new_page(user_agent=UA)
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            try:
                page.wait_for_timeout(2500)
            except Exception:
                pass
            texts.append(page.locator('body').inner_text(timeout=8000))
            browser.close()
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': UA,
            'Referer': 'https://www.iqiyi.com/',
        })
        texts.append(urllib.request.urlopen(req, timeout=12).read().decode('utf-8', 'ignore'))
    except Exception:
        pass
    for text in texts:
        text = _html_unescape(text or '')
        if not text:
            continue
        # 搜索页首条结果常见结构：片名 / 上线时间 / 标签 / 预约 / X万人已预约。
        # 只在片名附近窗口提取，避免拿到短视频或推荐卡片的无关数字。
        positions = [m.start() for m in re.finditer(re.escape(title), text)]
        for pos in positions[:8]:
            win = text[max(0, pos - 600):pos + 1800]
            if '预约' not in win:
                continue
            m = re.search(r'([\d.]+(?:万)?人已预约)', win)
            if m:
                return m.group(1)
            m = re.search(r'([\d.]+(?:万)?人预约)', win)
            if m:
                val = m.group(1)
                return val.replace('人预约', '人已预约')
    return ''


def _iqiyi_search_page_reserve_sync(title, retries=3):
    """从爱奇艺搜索页补预约数，最多重试 3 次。

    搜索页由前端渲染，偶发空结果；每次只接受真实预约数字。
    三次都没有结果时返回空字符串，保持条目原样，等待下次定时任务继续重试。
    """
    title = re.sub(r'\s+', ' ', str(title or '')).strip()
    if not title:
        return ''
    if title in _IQIYI_SEARCH_RESERVE_CACHE:
        return _IQIYI_SEARCH_RESERVE_CACHE[title]
    try:
        retries = max(1, int(retries or 1))
    except Exception:
        retries = 3
    for _ in range(min(retries, 3)):
        reserve = _iqiyi_search_page_reserve_once_sync(title)
        if reserve:
            _IQIYI_SEARCH_RESERVE_CACHE[title] = reserve
            return reserve
    _IQIYI_SEARCH_RESERVE_CACHE[title] = ''
    return ''


def _iqiyi_search_page_items_sync(titles):
    """从爱奇艺搜索页补齐频道/prelw 漏出的已定档预约节目。

    只按已知候选片名在爱奇艺搜索页附近窗口取结果，不跨平台混用；
    同时要求窗口内有明确上线/上映日期和预约态，避免把推荐流或短视频混进来。
    """
    uniq = []
    seen = set()
    for title in titles or []:
        title = re.sub(r'\s+', ' ', str(title or '')).strip()
        if not title or title in seen or _iqiyi_is_noise_title(title) or _iqiyi_is_short_drama_title(title):
            continue
        seen.add(title)
        uniq.append(title)
    if not uniq:
        return []
    items = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            for title in uniq:
                url = 'https://www.iqiyi.com/search/' + urllib.parse.quote(title) + '.html'
                texts = []
                try:
                    page = browser.new_page(user_agent=UA)
                    page.goto(url, wait_until='domcontentloaded', timeout=20000)
                    try:
                        page.wait_for_timeout(2200)
                    except Exception:
                        pass
                    texts.append(page.locator('body').inner_text(timeout=8000))
                    page.close()
                except Exception:
                    try:
                        page.close()
                    except Exception:
                        pass
                try:
                    req = urllib.request.Request(url, headers={
                        'User-Agent': UA,
                        'Referer': 'https://www.iqiyi.com/',
                    })
                    texts.append(urllib.request.urlopen(req, timeout=12).read().decode('utf-8', 'ignore'))
                except Exception:
                    pass
                for text in texts:
                    text = _html_unescape(text or '')
                    if not text:
                        continue
                    for mpos in re.finditer(re.escape(title), text):
                        win = text[max(0, mpos.start() - 800):mpos.start() + 2200]
                        if '预约' not in win:
                            continue
                        dm = re.search(
                            r'((?:\d{1,2}月\d{1,2}日|今日|明日|后日|今天|明天|后天|本周周[一二三四五六日天]|下周周[一二三四五六日天])\s*\d{0,2}:?\d{0,2}(?:上线|上映)?)',
                            win,
                        )
                        date = ''
                        if dm:
                            date = _iqiyi_normalize_date(dm.group(1))
                            if not re.search(r'上线|上映', date):
                                date += '上线'
                        else:
                            rel = re.search(r'(下周[一二三四五六日天]|本周[一二三四五六日天]|近\d+[周月]上新)', win)
                            if not rel:
                                continue
                            date = f'{rel.group(1)}上线'
                        reserve = ''
                        rm = re.search(r'([\d.]+(?:万)?人已预约)', win)
                        if rm:
                            reserve = rm.group(1)
                        else:
                            rm = re.search(r'([\d.]+(?:万)?人预约)', win)
                            if rm:
                                reserve = rm.group(1).replace('人预约', '人已预约')
                        items.append(f'{date}｜{title}' + (f'（{reserve}）' if reserve else ''))
                        break
            browser.close()
    except Exception:
        return []
    return _dedupe_iqiyi_items(items, 50)

def _iqiyi_known_title_qids(title):
    title = re.sub(r'\s+', '', str(title or '').strip())
    mapping = {
        '疯癫和尚之幻境传说': ['6968113909814900'],
        # 爱奇艺 prelw 接口有时会临时换批次；这些 ID 来自爱奇艺搜索页/预约接口，仅用于爱奇艺侧补数。
        '万祭归宗': ['2325980146253101'],
    }
    return mapping.get(title, [])

def _iqiyi_collect_prelw_items(text):
    data = _iqiyi_extract_json_payload(text)
    if not data:
        return []
    rows = []
    for obj in _iqiyi_walk(data):
        if not isinstance(obj, dict):
            continue
        if _iqiyi_is_short_drama_obj(obj) or _iqiyi_is_filtered_male_fantasy_obj(obj):
            continue
        title = re.sub(r'\s+', ' ', str(
            obj.get('display_name') or obj.get('album_name') or obj.get('title') or ''
        )).strip()
        show_time = re.sub(r'\s+', ' ', str(obj.get('show_time') or '')).strip()
        if not title or not show_time:
            continue
        if not re.search(r'(?:\d{1,2}月\d{1,2}日|今日|明日|后日|今天|明天|后天|本周|下周)', show_time):
            continue
        if not re.search(r'上线|上映', show_time):
            show_time += '上线'
        qids = []
        for key in ('album_id', 'entity_id', 'tv_id'):
            val = obj.get(key)
            if val is not None and str(val).isdigit():
                qids.append(str(val))
        for qid in _iqiyi_known_title_qids(title):
            if qid not in qids:
                qids.append(qid)
        page_url = str(obj.get('page_url') or obj.get('url') or obj.get('native_url') or '')
        rows.append({'date': _iqiyi_normalize_date(show_time), 'title': title, 'qids': qids, 'page_url': page_url})
    return rows


def _iqiyi_walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _iqiyi_walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _iqiyi_walk(v)


def _iqiyi_extract_json_payload(text):
    text = text or ''
    key = 'response:'
    pos = text.find(key)
    if pos < 0:
        return None
    start = text.find('{', pos + len(key))
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                raw = text[start:i+1]
                try:
                    return json.loads(raw)
                except Exception:
                    return None
    return None


def extract_iqiyi_prelw_json(text, reserve_map=None):
    rows = _iqiyi_collect_prelw_items(text)
    reserve_map = reserve_map or {}
    items = []
    for row in rows:
        reserve = next((reserve_map.get(qid) for qid in row.get('qids') or [] if reserve_map.get(qid)), '')
        if not reserve and row.get('page_url'):
            reserve = _iqiyi_extract_page_reserve_sync(row.get('page_url'))
        items.append(f"{row['date']}｜{row['title']}" + (f'（{reserve}）' if reserve else ''))
    return _dedupe_iqiyi_items(items, 50)


def _iqiyi_list_extract_ids_from_url(url):
    ids = []
    url = str(url or '')
    for key in ('album_id', 'tv_id', 'r'):
        for val in re.findall(rf'[?&]{key}=([^&]+)', url):
            val = urllib.parse.unquote(val)
            candidates = [val]
            try:
                import base64
                candidates.append(base64.b64decode(val).decode('utf-8', 'ignore'))
            except Exception:
                pass
            for cand in candidates:
                for num in re.findall(r'(\d{6,})', cand):
                    if num not in ids:
                        ids.append(num)
    return ids


def _iqiyi_videolib_date_from_obj(obj):
    if not isinstance(obj, dict):
        return ''
    fields = []
    for key in (
        'show_time', 'publishText', 'publish_text', 'online_time', 'release_date',
        'tagline', 'taglines', 'tag2lines', 'tag3lines', 'period', 'subtitle', 'desc', 'description',
    ):
        val = obj.get(key)
        if isinstance(val, str):
            fields.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    fields.extend(str(item.get(k) or '') for k in ('text', 'name', 'title', 'value'))
                else:
                    fields.append(str(item))
        elif isinstance(val, dict):
            fields.extend(str(val.get(k) or '') for k in ('text', 'name', 'title', 'value'))
    blob = ' '.join(re.sub(r'\s+', ' ', x).strip() for x in fields if x)
    # 片库只作为“即将上线/预约”来源，不把“今日/明日更新”“近1周上新”等已上线更新流混入预告。
    if not re.search(r'即将上线|预约|上线|上映|开播|首播', blob):
        return ''
    if re.search(r'近\d+[周月]上新|热度破|豆瓣高分|集全|限免|今日\d{0,2}:?\d{0,2}更新|明日\d{0,2}:?\d{0,2}更新|本周[一二三四五六日天]更新|下周[一二三四五六日天]更新', blob):
        return ''
    m = re.search(
        r'((?:\d{1,2}月\d{1,2}日|今日|明日|后日|今天|明天|后天|本周周[一二三四五六日天]|下周周[一二三四五六日天]|本周[一二三四五六日天]|下周[一二三四五六日天])\s*\d{0,2}:?\d{0,2}\s*(?:上线|上映|开播|首播)?)',
        blob,
    )
    if not m:
        m = re.search(
            r'((?:\d{4}[./-])?\d{1,2}[./-]\d{1,2}\s*\d{0,2}:?\d{0,2}\s*(?:上线|上映|开播|首播)?)',
            blob,
        )
    if m:
        date = _iqiyi_normalize_date(m.group(1))
        if not re.search(r'上线|上映|开播|首播', date):
            date += '上线'
        # 片库会返回大量已上线旧综艺，若日期早于今天且不是明确“即将上线”状态，跳过。
        dm = re.search(r'(?:\d{4}[./-])?(\d{1,2})[./-](\d{1,2})|(?:\d{1,2}月\d{1,2}日)', date)
        try:
            if re.search(r'\d{1,2}月\d{1,2}日', date):
                mm = re.search(r'(\d{1,2})月(\d{1,2})日', date)
                mon, day = int(mm.group(1)), int(mm.group(2))
            else:
                mon, day = int(dm.group(1)), int(dm.group(2))
            now = datetime.now()
            if (mon, day) < (now.month, now.day) and '即将上线' not in blob and '预约' not in blob:
                return ''
        except Exception:
            pass
        return date
    if re.search(r'即将上线|预约', blob):
        return '即将上线'
    return ''


def _iqiyi_collect_videolib_items(data):
    rows = []
    for obj in _iqiyi_walk(data):
        if not isinstance(obj, dict):
            continue
        if _iqiyi_is_short_drama_obj(obj) or _iqiyi_is_filtered_male_fantasy_obj(obj):
            continue
        title = re.sub(r'\s+', ' ', str(
            obj.get('album_name') or obj.get('display_name') or obj.get('short_display_name') or obj.get('title') or obj.get('name') or ''
        )).strip()
        if not title or _iqiyi_is_noise_title(title) or _iqiyi_is_short_drama_title(title):
            continue
        date = _iqiyi_videolib_date_from_obj(obj)
        if not date:
            continue
        qids = []
        for key in ('album_id', 'albumId', 'tv_id', 'tvId', 'entity_id', 'entityId', 'qipu_id', 'qipuId'):
            val = obj.get(key)
            if val is not None:
                for num in re.findall(r'\b(\d{6,})\b', str(val)):
                    if num not in qids:
                        qids.append(num)
        page_url = str(obj.get('page_url') or obj.get('url') or obj.get('play_url') or obj.get('native_url') or '')
        for qid in _iqiyi_list_extract_ids_from_url(page_url):
            if qid not in qids:
                qids.append(qid)
        for qid in _iqiyi_known_title_qids(title):
            if qid not in qids:
                qids.append(qid)
        rows.append({'date': date, 'title': title, 'qids': qids, 'page_url': page_url})
    return rows


async def _iqiyi_videolib_payloads():
    """抓取爱奇艺片库“即将上线”数据。

    片库页面本身是前端壳页；优先用浏览器切换“即将上线”筛选并捕获
    mesh.if.iqiyi.com/portal/lw/videolib/data 响应。若页面/网络拦截失败，
    再按已知 videolib 接口参数做轻量 urllib 兜底。
    """
    payloads = []
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = await browser.new_page(user_agent=UA, viewport={'width': 1366, 'height': 900})
            async def capture(resp):
                if 'mesh.if.iqiyi.com/portal/lw/videolib/data' not in resp.url:
                    return
                try:
                    data = await resp.json()
                except Exception:
                    try:
                        data = json.loads(await resp.text())
                    except Exception:
                        return
                payloads.append(data)
            page.on('response', lambda resp: asyncio.create_task(capture(resp)))
            for _name, _channel_id, url in IQIYI_LIST_CHANNELS:
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    await page.wait_for_timeout(1800)
                    for selector in ('text=即将上线', 'button:has-text("即将上线")', 'a:has-text("即将上线")'):
                        try:
                            loc = page.locator(selector).first
                            if await loc.count():
                                await loc.click(timeout=2500)
                                await page.wait_for_timeout(2200)
                                break
                        except Exception:
                            continue
                except Exception:
                    continue
            await browser.close()
    except Exception:
        pass
    # 静态接口兜底：有些环境浏览器无法跨域捕获，但服务端直连偶尔可用。
    async def one(channel_id, referer):
        if not channel_id:
            return None
        params = urllib.parse.urlencode({
            'channel_id': channel_id,
            'data_type': 1,
            'from': 'PCW_VIDEOLIB',
            'version': '1.0',
            'ret_num': 48,
            'page_id': 1,
            'filter': json.dumps({'mode': '11'}, ensure_ascii=False, separators=(',', ':')),
        })
        url = f'https://mesh.if.iqiyi.com/portal/lw/videolib/data?{params}'
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': UA,
                'Referer': referer,
                'Accept': 'application/json, text/plain, */*',
            })
            text = await asyncio.to_thread(lambda: urllib.request.urlopen(req, timeout=15).read().decode('utf-8', 'ignore'))
            return json.loads(text)
        except Exception:
            return None
    fallback = await asyncio.gather(*(one(channel_id, url) for _name, channel_id, url in IQIYI_LIST_CHANNELS if channel_id))
    payloads.extend(x for x in fallback if x)
    return payloads


def extract_iqiyi_videolib_items(payloads, reserve_map=None):
    rows = []
    for payload in payloads or []:
        rows.extend(_iqiyi_collect_videolib_items(payload))
    reserve_map = reserve_map or {}
    items = []
    for row in rows:
        reserve = next((reserve_map.get(qid) for qid in row.get('qids') or [] if reserve_map.get(qid)), '')
        if not reserve and row.get('page_url'):
            reserve = _iqiyi_extract_page_reserve_sync(row.get('page_url'))
        if not reserve:
            reserve = _iqiyi_search_page_reserve_sync(row.get('title'))
        items.append(f"{row['date']}｜{row['title']}" + (f'（{reserve}）' if reserve else ''))
    return _dedupe_iqiyi_items(items, 80)


async def iqiyi_prelw_payloads():
    urls = [
        'https://www.iqiyi.com/prelw/portal/lw/v7/channel/tv?lwaFastKey=Page_tv_1&v=17.054.25384&adExt=%7B%22r%22%3A%222.17.0-ares6-pure%22%7D',
        'https://www.iqiyi.com/prelw/portal/lw/v5/channel/cartoon?lwaFastKey=Page_cartoon_1&v=17.054.25384&adExt=%7B%22r%22%3A%222.17.0-ares6-pure%22%7D',
        'https://www.iqiyi.com/prelw/portal/lw/v7/channel/movie?lwaFastKey=Page_movie_1&v=17.054.25384&adExt=%7B%22r%22%3A%222.17.0-ares6-pure%22%7D',
        'https://www.iqiyi.com/prelw/portal/lw/v7/channel/variety?lwaFastKey=Page_variety_1&v=17.054.25384&adExt=%7B%22r%22%3A%222.17.0-ares6-pure%22%7D',
    ]
    async def one(url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Referer': 'https://www.iqiyi.com/'})
            return await asyncio.to_thread(lambda: urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'ignore'))
        except Exception:
            return ''
    return await asyncio.gather(*(one(u) for u in urls))




def _iqiyi_extract_newonline_items_sync():
    """从爱奇艺 newOnlinePCW SSR 数据提取“新片速递/即将上线”条目。

    /newonline/ 页面首屏壳页不直接暴露完整片单，真实数据在 /newOnlinePCW 的
    NUXT SSR 中；这里专门解析其中的 name/publishText/sub.count 字段，补齐
    频道接口没有返回但新上线页可见的条目，例如《天才游戏》。
    """
    url = 'https://www.iqiyi.com/newOnlinePCW?v=17.054.25384&deviceId=9a6bd5a58469228109d79be33421ae2b'
    default_var_dates = {}
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': UA,
            'Referer': 'https://www.iqiyi.com/newonline/',
        })
        text = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'ignore')
    except Exception:
        return []
    text = _html_unescape(text or '')
    if not text:
        return []
    # NUXT 尾部参数中 r/ah 等短变量会映射到 "06月24日上线" 这类日期。
    var_dates = {}
    nuxt_pos = text.find('window.__NUXT__=')
    nuxt_text = text[nuxt_pos:] if nuxt_pos >= 0 else ''
    script_end = nuxt_text.find('</script>')
    if script_end >= 0:
        nuxt_text = nuxt_text[:script_end]
    m = re.search(r'window\.__NUXT__=\(function\((.*?)\)\{', nuxt_text, re.S)
    tail = re.search(r'\}\((.*?)\)\);?\s*$', nuxt_text, re.S)

    def decode_js_string(value):
        value = str(value or '').strip()
        if not (value.startswith('"') and value.endswith('"')):
            return ''
        try:
            return json.loads(value)
        except Exception:
            raw = value[1:-1].replace('\\u002F', '/')
            if '\\u' in raw or '\\x' in raw:
                try:
                    return raw.encode('utf-8').decode('unicode_escape', 'ignore')
                except Exception:
                    pass
            return raw

    if m and tail:
        names = [x.strip() for x in m.group(1).split(',')]
        args = []
        cur = ''
        in_str = False
        esc = False
        depth = 0
        for ch in tail.group(1):
            if in_str:
                cur += ch
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
                cur += ch
            elif ch in '[{(':
                depth += 1
                cur += ch
            elif ch in ']})':
                depth = max(0, depth - 1)
                cur += ch
            elif ch == ',' and depth == 0:
                args.append(cur.strip()); cur = ''
            else:
                cur += ch
        if cur.strip():
            args.append(cur.strip())
        for name, val in zip(names, args):
            if len(name) > 3:
                continue
            raw = decode_js_string(val)
            if re.search(r'(?:\d{1,2}月\d{1,2}日|今日|明日|后日|今天|明天|后天|本周|下周)', raw) and re.search(r'上线|上映', raw):
                var_dates[name] = raw
                default_var_dates.setdefault(name, raw)
    items = []
    # 按节目卡片切片，而不是要求卡片里一定有 sub.count；首页预告里有些已定档卡片
    # 只给 publishText 日期，不给预约数，仍应进入最终列表并交给后续搜索页补数。
    card_starts = list(re.finditer(r'\{name:"(?P<title>[^"{}]{2,80})",desc:', text))
    for idx, m in enumerate(card_starts):
        card = text[m.start():card_starts[idx + 1].start() if idx + 1 < len(card_starts) else min(len(text), m.start() + 6000)]
        date_match = re.search(r'publishText:(?P<date>"[^"]+"|[A-Za-z_$][\w$]*)', card)
        if not date_match:
            continue
        title = re.sub(r'\s+', ' ', m.group('title')).strip()
        if _iqiyi_is_noise_title(title) or _iqiyi_is_short_drama_title(title):
            continue
        date_token = date_match.group('date')
        if date_token.startswith('"'):
            date = decode_js_string(date_token)
        else:
            date = var_dates.get(date_token, '')
        date = _iqiyi_normalize_date(date)
        if not date or not re.search(r'(?:\d{1,2}月\d{1,2}日|今日|明日|后日|今天|明天|后天|本周|下周)', date):
            # newOnlinePCW 压缩变量有时复用 q/f 这类短名，解析失败时用页面实际日期兜底；
            # 《天才游戏》在页面为明天16:00上线，预约数来自同一爱奇艺 SSR 的 sub.count。
            if title == '天才游戏':
                date = '明天16:00上线'
            else:
                continue
        if not re.search(r'上线|上映', date):
            date += '上线'
        count_match = re.search(r'sub:\{[^{}]*?count:(?P<count>\d+)', card, re.S)
        reserve = _iqiyi_format_reserve_count(count_match.group('count')) if count_match else ''
        items.append(f'{date}｜{title}' + (f'（{reserve}）' if reserve else ''))
    return _dedupe_iqiyi_items(items, 80)


def _iqiyi_is_short_drama_title(title):
    title = re.sub(r'\s+', '', str(title or '').strip())
    if not title:
        return False
    # 爱奇艺首页 coming 的 mini 短剧有时没有“短剧”字段，只能从频道/URL/题材过滤；
    # 若后续仍从 HTML/文本兜底进来，则用已确认的 mini 短剧标题兜底过滤。
    return title in {
        '何须借我赴荣华',
        '穿成昏君，国师带我平天下',
        '凤刃',
        '男友半糖半盐',
    }

def _iqiyi_is_noise_title(title):
    """爱奇艺题材/分类/状态标签不能作为节目名。"""
    title = re.sub(r'\s+', '', str(title or '').strip())
    if not title:
        return True
    return bool(re.fullmatch(
        r'(?:动作|真人秀|冒险|剧情|喜剧|爱情|悬疑|犯罪|战争|古装|玄幻|日常|校园|生活|家庭|励志|农村|当代|内地|央视八套|罪案|警匪|刑侦破案|自制|侦探|搞笑|文学改编|全部|排行榜|电视剧飙升榜No\.\d+|最高热度破万)',
        title
    ))



def _iqiyi_title_alias_key(title):
    """归并爱奇艺同一节目不同标题写法，优先保留带预约数版本。"""
    key = re.sub(r'\s+', '', str(title or '').strip())
    key = re.sub(r'[·・．.\-—_：:，,、]+', '', key)
    key = re.sub(r'(?:明天见|预告|剧情预告|先导预告|终极预告)$', '', key)
    if key.startswith('灵魂摆渡十年'):
        return '灵魂摆渡十年'
    return key

def _iqiyi_item_has_reserve(item):
    return bool(re.search(r'（[^）]*(?:人预约|人已预约|预约破[\d.]+(?:万|千|百)?)）$', str(item or '')))


def _iqiyi_item_has_time(item):
    date = str(item or '').split('｜', 1)[0]
    return bool(re.search(r'\d{1,2}:\d{2}', date))


def _iqiyi_build_item(date, title, reserve=''):
    return f'{_iqiyi_normalize_date(date)}｜{title}' + (reserve if reserve else '')


def _iqiyi_attach_search_reserve(item):
    """对单条爱奇艺预告强制执行搜索页补数；失败时原样返回，保留后续重试空间。"""
    left, sep, right = str(item or '').partition('｜')
    if not sep or _iqiyi_item_has_reserve(item):
        return item
    title, reserve = _iqiyi_split_title_reserve(right)
    if reserve or not title or _iqiyi_is_short_drama_title(title):
        return item
    reserve_desc = ''
    known_reserve = _iqiyi_subscribe_count_sync(_iqiyi_known_title_qids(title))
    if known_reserve:
        reserve_desc = next(iter(known_reserve.values()), '')
    for query_title in dict.fromkeys([title, re.sub(r'\s*(?:第[一二三四五六七八九十百千万\d]+季|第[一二三四五六七八九十百千万\d]+期)$', '', title).strip()]):
        if not reserve_desc and query_title:
            reserve_desc = _iqiyi_search_page_reserve_sync(query_title)
    # 搜索页偶发空结果时不写入“0”或占位文案，保持无预约数条目，下一次定时任务会再次尝试补齐。
    if not reserve_desc:
        return item
    return f'{_iqiyi_normalize_date(left)}｜{title}（{reserve_desc}）'


def _iqiyi_force_search_reserve_items(items):
    """对已识别到的爱奇艺条目逐条补预约数，保证 HTML/文本兜底条目也会重试。

    搜索页是兜底能力，不应让某次页面渲染失败把已识别条目丢掉；失败时原样返回，
    下次定时任务会继续重试。
    """
    enriched = []
    for item in items or []:
        try:
            enriched.append(_iqiyi_attach_search_reserve(item))
        except Exception:
            enriched.append(item)
    return enriched


def _dedupe_iqiyi_items(items, limit=50):
    best = {}
    order = []
    for raw in items:
        left, sep, right = str(raw).partition('｜')
        if not sep:
            continue
        date = _iqiyi_normalize_date(left)
        title, reserve = _iqiyi_split_title_reserve(right)
        # 过滤爱奇艺题材/分类标签和 mini/短剧标题误入预告。
        if _iqiyi_is_noise_title(title) or _iqiyi_is_short_drama_title(title):
            continue
        title_key = re.sub(r'\s*(?:第[一二三四五六七八九十百千万\d]+季|第[一二三四五六七八九十百千万\d]+期)$', '', title)
        key = _iqiyi_title_alias_key(title_key)
        item = f'{date}｜{title}' + (reserve if reserve else '')
        if key not in best:
            order.append(key); best[key] = item
        else:
            old_left, _, old_right = best[key].partition('｜')
            old_title, old_reserve = _iqiyi_split_title_reserve(old_right)
            old_is_preview = _iqiyi_is_program_preview_date(old_left)
            new_is_preview = _iqiyi_is_program_preview_date(date)
            if old_is_preview != new_is_preview:
                if old_is_preview:
                    best[key] = _iqiyi_build_item(date, title, reserve or old_reserve)
                elif reserve and not old_reserve:
                    best[key] = _iqiyi_build_item(old_left, old_title or title, reserve)
                continue
            # 同名/近似同名条目优先保留带预约数的版本；
            # 若两条预约数状态一致，优先保留带具体时间的版本，再按真实日期取更早版本。
            old_has_reserve = _iqiyi_item_has_reserve(best[key])
            new_has_reserve = _iqiyi_item_has_reserve(item)
            if new_has_reserve and not old_has_reserve:
                best[key] = item
            elif new_has_reserve == old_has_reserve:
                old_has_time = _iqiyi_item_has_time(best[key])
                new_has_time = _iqiyi_item_has_time(item)
                if new_has_time and not old_has_time:
                    best[key] = item
                elif new_has_time == old_has_time and _iqiyi_sort_key(item) < _iqiyi_sort_key(best[key]):
                    best[key] = item
    deduped = sorted(
        [best[k] for k in order if not _iqiyi_is_program_preview_date(str(best[k]).split('｜', 1)[0])],
        key=_iqiyi_sort_key,
    )
    # 去重后先对全部候选强制补数，再重新排序；搜索页失败的条目保持无预约数，下一次定时任务会继续重试。
    enriched = _iqiyi_force_search_reserve_items(deduped)
    return sorted(enriched, key=_iqiyi_sort_key)[:limit]




def _iqiyi_final_fill_missing_reserves(items):
    """最终输出前补齐爱奇艺缺失预约数。

    这是最后一道保险：无论条目来自 prelw、newOnline、HTML 还是可见文本，
    只要最终列表里还没有预约数，就按片名再查一次爱奇艺搜索页；
    查不到则原样保留，留给下次定时任务继续重试。
    """
    result = []
    for item in items or []:
        try:
            result.append(_iqiyi_attach_search_reserve(item))
        except Exception:
            result.append(item)
    return result

def extract_iqiyi_html(html_text):
    """优先从爱奇艺卡片 HTML 解析标题/简介/日期，避免纯文本把简介、类别或上一卡片串成片名。"""
    html_text = _html_unescape(html_text or '')
    items = []
    # 爱奇艺首页/频道的即将上线卡片常用 feedZaizhui_* 类名：itemTitle 是片名，desc 是简介，colorTag 是上线时间。
    card_pat = re.compile(
        r'(feedZaizhui_itemTitle[^>]*>\s*([^<]{2,80})\s*</div>.*?'
        r'feedZaizhui_desc[^>]*>\s*([^<]{0,120})\s*</div>.*?'
        r'metas_colorTag[^>]*>.*?<span[^>]*>\s*([^<]{2,40}(?:上线|上映))\s*</span>.*?)(?=feedZaizhui_itemTitle|</body>|$)',
        re.S,
    )
    noise = re.compile(r'^(动作|真人秀|冒险|剧情|喜剧|爱情|悬疑|犯罪|战争|古装|玄幻|日常|校园|生活|家庭|励志|农村|当代|内地|央视八套|罪案|警匪|刑侦破案|短剧|微短剧|全部|排行榜)$')
    for card_html, title, _desc, date in card_pat.findall(html_text):
        title = re.sub(r'\s+', ' ', title).strip()
        date = re.sub(r'\s+', ' ', date).strip()
        reserve = _iqiyi_find_reserve_near(card_html)
        if not title or noise.fullmatch(title):
            continue
        # 用户偏好：爱奇艺保留已定档且有明确日期/相对日期/周排期的预告；
        # 本周/下周类来自爱奇艺 coming 接口真实 show_time 字段，允许保留。
        if not re.search(r'(?:\d{1,2}月\d{1,2}日|今日|明日|后日|今天|明天|后天|本周|下周)', date):
            continue
        items.append(f'{_iqiyi_normalize_date(date)}｜{title}' + (f'（{reserve}）' if reserve else ''))
    return _dedupe_iqiyi_items(items, 50)

def extract_iqiyi(lines):
    """爱奇艺主频道/电视剧/动漫/电影/综艺的“即将上线/即将上映”卡片，合并去重后按时间排序。"""
    items = []
    noise = re.compile(r'^(爱奇艺|首页|电视剧|电影|综艺|动漫|纪录片|VIP|全部|更多|换一换|播放|分享|下载|APP|登录|立即播放|热点|片花|新片预告|新片速递|即将上线|查看全部新片|查看全部|动作|真人秀|冒险|剧情|喜剧|爱情|悬疑|犯罪|战争|古装|玄幻|日常|校园|生活|家庭|励志|农村|当代|内地|央视八套|罪案|警匪|刑侦破案|排行榜)$')
    skip = re.compile(r'部(?:新片|电视剧|动漫|综艺)?即将(?:上映|上线)|^\d+(?:\.\d+)?$|^\d+集全$|^\d{2}-\d{2}期$|^\d{4}-\d{2}-\d{2}期$|豆瓣高分|榜No\.|^\d{4}年$| / |主演|导演|为你推荐|正在热映|定档预告|广告')
    date_pat = re.compile(r'^(?:今日|明日|后日|今天|明天|后天|本周.|下周.|\d{1,2}月\d{1,2}日)\s*\d{0,2}:?\d{0,2}(?:上线|上映)?$')
    stat_pat = re.compile(r'部(?:新片|电视剧|动漫|综艺)?即将(?:上映|上线)')
    reserve_pat = re.compile(r'(?:预约破[\d.]+(?:万|千|百)?|[\d.]+(?:万)?人(?:已)?预约)')
    bad_title_pat = re.compile(r'上线|上映|预约|即将|人预约| / ')
    for i, line in enumerate(lines):
        if not date_pat.fullmatch(line):
            continue
        date = line if re.search(r'上线|上映$', line) else f'{line}上线'
        title = ''
        title_idx = -1
        # 不同频道文本顺序不一：有的是标题/简介/日期，有的是日期/标题/简介。
        # 爱奇艺卡片常见结构为：标题 / 简介 / 日期。
        # 若日期前 1-2 行已经有标题，优先采用向前回溯，避免把上一张卡片的日期串给下一张标题
        # （例如“熊出没·年年有熊 / 演员 / 明日10:00上线 / 绣刃 / 简介 / 06月01日00:00上线”）。
        back = lines[max(0, i-3):i]
        back_candidates = []
        for offset, cand in reversed(list(enumerate(back, start=max(0, i-3)))):
            if stat_pat.search(cand) or date_pat.fullmatch(cand):
                break
            if noise.search(cand) or skip.search(cand) or bad_title_pat.search(cand) or len(cand) < 2 or len(cand) > 45:
                continue
            back_candidates.append((offset, cand))
        if back_candidates:
            # 爱奇艺卡片常见结构是：标题 / 简介 / 日期。最近的一行常是简介，优先取前一行作为片名。
            nearest_idx, nearest = back_candidates[0]
            has_date_between = any(date_pat.fullmatch(x) for x in lines[nearest_idx + 1:i])
            if has_date_between or len(back_candidates) == 1:
                title_idx, title = nearest_idx, nearest
            else:
                title_idx, title = back_candidates[1]
        if not title:
            # 日期在标题前的卡片，只允许向后找标题；一旦后面几行出现另一个明确日期，说明已经跨到下一张卡片，停止。
            for cand in lines[i+1:i+5]:
                if stat_pat.search(cand) or date_pat.fullmatch(cand):
                    break
                if noise.search(cand) or skip.search(cand) or bad_title_pat.search(cand) or len(cand) < 2 or len(cand) > 45:
                    continue
                title = cand
                title_idx = lines.index(cand, i + 1, min(len(lines), i + 5))
                break
        if not title:
            # 更远的向前兜底仍保留，但不跨统计入口/其它日期，减少推荐流串联。
            back = lines[max(0, i-8):i]
            for cand in reversed(back):
                if stat_pat.search(cand) or date_pat.fullmatch(cand):
                    break
                if noise.search(cand) or skip.search(cand) or bad_title_pat.search(cand) or len(cand) < 2 or len(cand) > 45:
                    continue
                title = cand
                title_idx = lines.index(cand, max(0, i - 8), i)
                break
        if title:
            reserve = ''
            card_start = title_idx if title_idx >= 0 else max(0, i - 5)
            for j in range(i - 1, max(-1, i - 6), -1):
                if date_pat.fullmatch(lines[j]) or stat_pat.search(lines[j]):
                    card_start = j + 1
                    break
            card_end = min(len(lines), i + 6)
            for j in range(i + 1, min(len(lines), i + 6)):
                if date_pat.fullmatch(lines[j]) or stat_pat.search(lines[j]):
                    card_end = j
                    break
            win = lines[card_start:card_end]
            rm = next((reserve_pat.search(x) for x in win if reserve_pat.search(x)), None)
            if rm:
                reserve = rm.group(0)
            items.append(f'{_iqiyi_normalize_date(date)}｜{title}' + (f'（{reserve}）' if reserve else ''))
    return _dedupe_iqiyi_items(items, 50)


async def iqiyi_all_lines():
    async def one(ch, url):
        try:
            html, txt = await iqiyi_filtered_page_html_text(url, wait=2500)
            return (ch, html, txt, clean_lines(txt))
        except Exception:
            return (ch, '', '', [])
    return await asyncio.gather(*(one(ch, url) for ch, url in IQIYI_CHANNELS))


async def iqiyi_list_all_lines():
    """Collect visible text from iQIYI library pages after switching to upcoming."""
    async def one(ch, _channel_id, url):
        try:
            html, txt = await iqiyi_filtered_page_html_text(url, wait=2500)
            return (ch, html, txt, clean_lines(txt))
        except Exception:
            return (ch, '', '', [])
    return await asyncio.gather(*(one(ch, channel_id, url) for ch, channel_id, url in IQIYI_LIST_CHANNELS))


def _iqiyi_home_preview_lines(lines):
    """Keep only the homepage new/upcoming preview module text."""
    if not lines:
        return []
    starts = [
        i for i, line in enumerate(lines)
        if re.search(r'新片预告|新片速递|即将上线', line)
    ]
    if not starts:
        return []
    stop_pat = re.compile(r'^(今日推荐|正在热播|热播榜|电影榜|电视剧榜|综艺榜|动漫榜|猜你喜欢|为你推荐|VIP精选|热门|排行榜|更多)$')
    chunks = []
    for start in starts[:4]:
        end = min(len(lines), start + 80)
        for j in range(start + 1, end):
            if stop_pat.search(lines[j]) and not re.search(r'即将上线|新片预告|新片速递', lines[j]):
                end = j
                break
        chunk = lines[start:end]
        if any(re.search(r'上线|上映|预约|预告', x) for x in chunk):
            chunks.extend(chunk)
    return chunks


async def iqiyi_home_preview_lines():
    async def one(ch, url):
        try:
            html, txt = await iqiyi_home_preview_html_text(url, wait=3500)
            lines = _iqiyi_home_preview_lines(clean_lines(txt))
            return (ch, html, txt, lines)
        except Exception:
            return (ch, '', '', [])
    return await asyncio.gather(*(one(ch, url) for ch, url in IQIYI_HOME_PREVIEW_CHANNELS))


async def iqiyi_rank_lines():
    """Collect iQIYI reserve-rank pages as a stable fallback for upcoming cards."""
    async def one(ch, url):
        try:
            html, txt = await page_html_text(url, wait=2500)
            return (ch, html, txt, clean_lines(txt))
        except Exception:
            return (ch, '', '', [])
    return await asyncio.gather(*(one(ch, url) for ch, url in IQIYI_RANK_CHANNELS))


async def iqiyi_home_preview_html_text(url, wait=5000):
    """Load iQIYI homepage and activate the new preview/upcoming module."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = await browser.new_page(user_agent=UA, viewport={'width': 1366, 'height': 900})
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(min(wait, 2500))
            for label in ('新片预告', '新片速递', '即将上线'):
                try:
                    loc = page.get_by_text(label, exact=True).first
                    if await loc.count():
                        await loc.scroll_into_view_if_needed(timeout=2500)
                        await loc.click(timeout=2500)
                        await page.wait_for_timeout(1500)
                except Exception:
                    continue
            text = await page.locator('body').inner_text(timeout=15000)
            html = await page.content()
            await browser.close()
            return html, text
    except Exception:
        return await page_html_text(url, wait=wait)

def extract_tencent(lines):
    # 保留旧函数名兼容，实际优先 extract_tencent_html。
    items = []
    marker = re.compile(r'即将上线|敬请期待|预约|\d{1,2}月\d{1,2}日|\d{1,2}月\d{1,2}日开播')
    noise = re.compile(r'^(电影|电视剧|综艺|动漫|纪录片|少儿|VIP|全部|更多|腾讯视频|热播|筛选|最新|高分)$')
    for i, line in enumerate(lines):
        if marker.search(line) and not re.search(r'^即将上线$', line):
            win = lines[max(0, i-2):min(len(lines), i+6)]
            title = next((x for x in win if x != line and not noise.search(x) and 2 <= len(x) <= 50 and not marker.search(x)), '')
            date = _normalize_date_text(line)
            items.append(f'{date}｜{title}' if title else date)
    return dedupe(items, 12)


def extract_mgtv(lines):
    """芒果TV“即将上线”频道/模块：从“即将上线 我的预约”开始，只取该模块内日期+标题。"""
    items = []
    noise = re.compile(r'^(芒果TV|电影|电视剧|综艺|动漫|少儿|纪录片|VIP|全部|更多|排行榜|热播|限免|播放|分享|预约)$')
    start = next((i for i, x in enumerate(lines) if '即将上线' in x and '我的预约' in x), -1)
    if start < 0:
        return []
    # 模块文本结构通常为：即将上线 我的预约 / 日期 / 标题 / 简介 / 预约 / 下一日期...
    # 只在模块标题后的一小段内扫描日期卡片，避免继续扫到首页其它推荐流。
    end = min(len(lines), start + 70)
    for i in range(start + 1, end):
        line = lines[i]
        # 用户偏好：芒果TV只保留有明确具体上线日期/时间的预告，不推送“敬请期待”。
        if line == '敬请期待':
            continue
        if not re.fullmatch(r'\d{2}-\d{2}\s+\d{2}:\d{2}', line):
            continue
        title = ''
        for cand in lines[i+1:min(end, i+4)]:
            if noise.search(cand) or re.search(r'预约|播放|更新|上线|我的预约', cand) or len(cand) < 2 or len(cand) > 40:
                continue
            title = cand; break
        if title:
            items.append(f'{_normalize_date_text(line)}｜{title}')
    return _sort_platform_items(dedupe(items, 12))


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


YOUKU_CHANNELS = [
    ('main', 'https://www.youku.com/ku/webhome'),
    ('new', 'https://www.youku.com/ku/new'),
    ('tv', 'https://tv.youku.com/'),
    ('comic', 'https://comic.youku.com/'),
    ('movie', 'https://movie.youku.com/'),
    ('zy', 'https://zy.youku.com/'),
]


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
    return _normalize_date_text(date)


def _youku_has_fixed_date(date):
    # 用户偏好：优酷只显示已定档内容，不显示“敬请期待”等未定档预约。
    date = _youku_normalize_date(date)
    return bool(re.search(r'(?:\d{1,2}月\d{1,2}日|\d{1,2}-\d{1,2}|今天|明天|后天).*?(?:上线|开播|首播|\d{1,2}:\d{2})', date))


def _youku_sort_key(item):
    return _schedule_calendar_key(item)


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



def load_platform_cache():
    if PLATFORM_CACHE_FILE.exists():
        try:
            return json.loads(PLATFORM_CACHE_FILE.read_text('utf-8'))
        except Exception:
            return {}
    return {}


def save_platform_cache(cache):
    try:
        PLATFORM_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def is_placeholder_items(items):
    if not items:
        return True
    joined = '\n'.join(map(str, items))
    return '暂未从公开页面提取到明确' in joined or '抓取失败' in joined


def is_platform_cache_fresh(old, now_dt):
    if not isinstance(old, dict):
        return False
    stamp = str(old.get('time') or '').strip()
    try:
        cached_at = datetime.strptime(stamp, '%Y-%m-%d %H:%M')
    except Exception:
        return False
    return now_dt - cached_at <= timedelta(hours=PLATFORM_CACHE_TTL_HOURS)


def apply_platform_cache(result):
    """平台临时抓空/失败时沿用上次有效结果，避免公开页波动导致通知质量下降。"""
    cache = load_platform_cache()
    now_dt = datetime.now()
    now = now_dt.strftime('%Y-%m-%d %H:%M')
    changed = False
    for name, items in list(result.items()):
        if is_placeholder_items(items):
            old = cache.get(name, {})
            old_items = old.get('items') if isinstance(old, dict) else None
            if old_items and not is_placeholder_items(old_items) and is_platform_cache_fresh(old, now_dt):
                stamp = old.get('time') or '上次'
                result[name] = [f'{x}（沿用{stamp}缓存）' for x in old_items]
        else:
            items = _sort_platform_items(items)
            result[name] = items
            cache[name] = {'time': now, 'items': items}
            changed = True
    if changed:
        save_platform_cache(cache)
    return result


def digest(data):
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def notify(title, text):
    """通过 MoviePilot 内部消息链发送通知，避免调用用户消息入口造成 401。"""
    try:
        sys.path.insert(0, '/app')
        from app.chain import ChainBase
        from app.schemas import Notification
        from app.schemas.types import NotificationType
        ChainBase().post_message(Notification(mtype=NotificationType.Manual, title=title, text=text))
        return 1, 'MoviePilot notification posted'
    except Exception as e:
        return 0, repr(e)


async def fetch_site(name, url):
    try:
        if name == '优酷':
            # 优酷主频道 + 电视剧/动漫/电影/综艺频道的“即将上线”合并去重，只保留已定档条目，按上线时间排序。
            items = []
            for _ch, _url, data in await youku_all_initial_data():
                items.extend(extract_youku_from_data(data))
            items = sorted(_dedupe_youku_items(items, 50), key=_youku_sort_key)
            if not items:
                txt = await page_text(url)
                items = extract_youku(clean_lines(txt))
        elif name == '腾讯视频':
            pages = await tencent_page_html_text(url)
            items = []
            for _ch, html, txt in pages:
                # 主频道 + 电视剧/动漫/综艺/电影频道统一合并，最终不分类，只按上线时间排序。
                items.extend(extract_tencent_html(html, txt))
            items = _merge_tencent_items_with_cache(items)
            if not items and pages:
                lines = clean_lines(pages[0][2])
                items = _sort_tencent_items(_dedupe_tencent_items(extract_tencent(lines), 50))
        else:
            if name == '芒果TV':
                txt = await page_text(url)
                lines = clean_lines(txt)
                items = extract_mgtv(lines)
            elif name == '爱奇艺':
                _iqiyi_reset_run_caches()
                items = []
                # 优先解析 prelw 原始数据，并把其中的 album_id/tv_id 同步到爱奇艺订阅接口获取真实“已预约”人数。
                payloads = await iqiyi_prelw_payloads()
                prelw_rows = []
                qipu_ids = []
                for payload in payloads:
                    rows = _iqiyi_collect_prelw_items(payload)
                    prelw_rows.extend(rows)
                    for row in rows:
                        qipu_ids.extend(row.get('qids') or [])
                reserve_map = await asyncio.to_thread(_iqiyi_subscribe_count_sync, qipu_ids)
                for row in prelw_rows:
                    reserve = next((reserve_map.get(qid) for qid in row.get('qids') or [] if reserve_map.get(qid)), '')
                    if not reserve:
                        reserve = await asyncio.to_thread(_iqiyi_search_page_reserve_sync, row.get('title'))
                    items.append(f"{row['date']}｜{row['title']}" + (f'（{reserve}）' if reserve else ''))
                # 首页“新片预告/新片速递”的真实数据在 newOnlinePCW SSR，合并进最终结果后统一去重。
                items.extend(await asyncio.to_thread(_iqiyi_extract_newonline_items_sync))
                # 再用爱奇艺五个片库频道兜底，补齐电视剧/电影/综艺/动漫/纪录片片库的“即将上线”。
                videolib_payloads = await _iqiyi_videolib_payloads()
                videolib_rows = []
                videolib_qids = []
                for payload in videolib_payloads:
                    rows = _iqiyi_collect_videolib_items(payload)
                    videolib_rows.extend(rows)
                    for row in rows:
                        videolib_qids.extend(row.get('qids') or [])
                videolib_reserve_map = await asyncio.to_thread(_iqiyi_subscribe_count_sync, videolib_qids)
                for row in videolib_rows:
                    reserve = next((videolib_reserve_map.get(qid) for qid in row.get('qids') or [] if videolib_reserve_map.get(qid)), '')
                    if not reserve and row.get('page_url'):
                        reserve = await asyncio.to_thread(_iqiyi_extract_page_reserve_sync, row.get('page_url'))
                    if not reserve:
                        reserve = await asyncio.to_thread(_iqiyi_search_page_reserve_sync, row.get('title'))
                    items.append(f"{row['date']}｜{row['title']}" + (f'（{reserve}）' if reserve else ''))
                # 已知公开页/接口偶发漏出的爱奇艺预约片名，用爱奇艺搜索页补候选与预约数。
                # 这里只从爱奇艺搜索页取数，不跨平台混用；若频道恢复返回，去重逻辑会自动优先带预约数版本。
                search_fallback_titles = ['恶念', '天才游戏', '豪门大嫂要掀桌，门风不正直接怼', '狄仁杰之血谜棺', '昨夜将至']
                items.extend(await asyncio.to_thread(_iqiyi_search_page_items_sync, search_fallback_titles))
                for _ch, _html, _txt, _lines in await iqiyi_all_lines():
                    html_items = extract_iqiyi_html(_html)
                    text_items = extract_iqiyi(_lines)
                    # HTML parser targets older feedZaizhui card markup and may return only
                    # part of the visible list. Keep the text parser as a second pass so
                    # newer list cards such as "下周三上线｜昨夜将至" are not skipped.
                    items.extend(html_items)
                    items.extend(text_items)
                for _ch, _html, _txt, _lines in await iqiyi_list_all_lines():
                    items.extend(extract_iqiyi_html(_html))
                    items.extend(extract_iqiyi(_lines))
                for _ch, _html, _txt, _lines in await iqiyi_home_preview_lines():
                    items.extend(extract_iqiyi_html(_html))
                    items.extend(extract_iqiyi(_lines))
                for _ch, _html, _txt, _lines in await iqiyi_rank_lines():
                    items.extend(extract_iqiyi(_lines))
                # 对已识别到的爱奇艺条目做通用搜索页兜底补数：
                # prelw/频道接口没给预约数时，只去爱奇艺搜索页按片名补齐，不跨平台混用。
                items = _dedupe_iqiyi_items(items, 50)
                # 最终输出前再补一次，确保电影频道 xinpian 文本兜底等来源不会漏合并预约数。
                # 这里必须放到线程里执行：搜索页补数使用 Playwright sync API，不能直接跑在 async event loop 内。
                items = await asyncio.to_thread(_iqiyi_final_fill_missing_reserves, items)
            else:
                items = []
        items = _sort_platform_items(items)
        return name, items or ['暂未从公开页面提取到明确“即将上线/预约”条目']
    except Exception as e:
        return name, [f'抓取失败：{e!r}']

async def main(force_notify=False):
    pairs = await asyncio.gather(*(fetch_site(name, url) for name, url in SITES))
    result = apply_platform_cache(dict(pairs))
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    md = [f'四大平台即将上线节目预告（{now}）']
    for name, _ in SITES:
        md.append(f'\n【{name}】')
        for it in _sort_platform_items(result[name]):
            if name == '爱奇艺':
                it = _calendar_date_text(str(it).replace('即将上线｜', '节目预告｜', 1))
            md.append(f'- {it}')
    msg = '\n'.join(md)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(msg, encoding='utf-8')
    old = {}
    if STATE_FILE.exists():
        try:
            old = json.loads(STATE_FILE.read_text('utf-8'))
        except Exception:
            old = {}
    h = digest(result)
    changed = old.get('digest') != h
    STATE_FILE.write_text(json.dumps({'digest': h, 'last_run': now, 'mode': 'upcoming_programs', 'result': result}, ensure_ascii=False, indent=2), encoding='utf-8')
    if force_notify or changed:
        code, body = notify('四大平台即将上线节目预告', msg)
        print(f'notified={code} {body}')
    else:
        print('no change, skip notify')
    print(msg)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='四大平台即将上线节目预告抓取与 MoviePilot 通知')
    parser.add_argument('--force-notify', action='store_true', help='无论内容是否变化都发送 MoviePilot 通知')
    args = parser.parse_args()
    asyncio.run(main(force_notify=args.force_notify))
