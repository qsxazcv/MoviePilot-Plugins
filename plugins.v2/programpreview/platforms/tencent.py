# -*- coding: utf-8 -*-
"""腾讯视频节目预告解析。"""

import asyncio
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from ..cache import load_platform_cache
from ..categories import item_category, normalize_category, strip_item_category, with_category, with_category_many
from ..constants import UA
from ..date_utils import normalize_date_text, schedule_calendar_key, sort_platform_items
from ..fetcher import page_html_text
from ..text_utils import clean_lines, dedupe, html_unescape

try:
    from app.log import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)


TENCENT_PAGESERVICE_CHANNELS = [
    ('tv', '100113'),
    ('tvdrama', '100173'),
    ('variety', '100109'),
    ('cartoon', '100119'),
    ('movie', '100105'),
    ('shortdrama', '100101'),
]

TENCENT_TITLE_ALIASES = {
    # 腾讯 PageService 的 title 字段偶尔是推荐文案，真实片名在 mz_title/title_pc。
    # 旧缓存或文本兜底可能已保存该文案，这里统一修正显示。
    '代露娃唐诗逸双强博弈': '画梦录',
}

TENCENT_SEARCH_URL = 'https://pbaccess.video.qq.com/trpc.videosearch.mobile_search.MultiTerminalSearch/MbSearch?vversion_platform=2'
_TENCENT_SEARCH_CATEGORY_CACHE = {}


def _tencent_enabled_pageservice_channels(include_short_drama=False):
    if include_short_drama:
        return list(TENCENT_PAGESERVICE_CHANNELS)
    return [(channel, page_id) for channel, page_id in TENCENT_PAGESERVICE_CHANNELS if channel != 'shortdrama']


def _tencent_pageservice_payload(page_id):
    url = 'https://pbaccess.video.qq.com/trpc.vector_layout.page_view.PageService/getPage?video_appid=3000010&vversion_platform=2'
    body = {
        'page_params': {
            'page_type': 'channel',
            'page_id': page_id,
            'scene': 'channel',
            'new_mark_label_enabled': '1',
            'vl_to_mvl': '1' if page_id == '120188' else '',
            'ad_exp_ids': '',
            'ams_cookies': '',
            'ad_trans_data': json.dumps({'ad_request_id': f'mp-{page_id}', 'game_sessions': []}),
            'skip_privacy_types': '0',
            'support_click_scan': '1',
        },
        'page_bypass_params': {
            'params': {
                'platform_id': '2',
                'caller_id': '3000010',
                'data_mode': 'default',
                'user_mode': 'default',
                'specified_strategy': '',
                'page_type': 'channel',
                'page_id': page_id,
                'scene': 'channel',
                'new_mark_label_enabled': '1',
            },
            'scene': 'channel',
            'app_version': '',
            'abtest_bypass_id': '',
        },
        'page_context': None,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
        method='POST',
        headers={
            'User-Agent': UA,
            'Content-Type': 'application/json',
            'Origin': 'https://v.qq.com',
            'Referer': 'https://v.qq.com/channel/tv',
        },
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode('utf-8', 'ignore'))


def _tencent_pageservice_pages(include_short_drama=False):
    pages = []
    for channel, page_id in _tencent_enabled_pageservice_channels(include_short_drama):
        try:
            payload = _tencent_pageservice_payload(page_id)
        except Exception:
            continue
        html = (
            '<script id="__MP_CAPTURED_PAGESERVICE__" type="application/json">'
            + json.dumps([payload], ensure_ascii=False)
            + '</script>'
        )
        pages.append((channel, html, ''))
    return pages


def _tencent_search_payload(query):
    body = {
        'query': query,
        'pagenum': 0,
        'pagesize': 12,
        'queryFrom': 'input',
        'version': '8.2.96',
        'clientType': 1,
        'filterValue': '',
        'retry': 0,
        'featureList': [
            'DEFAULT_FEFEATURE',
            'PC_SHORT_VIDEOS_WATERFALL',
            'PC_WANT_EPISODE_V2',
            'PC_WANT_EPISODE',
        ],
    }
    req = urllib.request.Request(
        TENCENT_SEARCH_URL,
        data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
        method='POST',
        headers={
            'User-Agent': UA,
            'Content-Type': 'application/json',
            'Origin': 'https://v.qq.com',
            'Referer': 'https://v.qq.com/x/search/?q=' + urllib.parse.quote(query),
        },
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode('utf-8', 'ignore'))


def _iter_tencent_video_infos(obj):
    if isinstance(obj, dict):
        video_info = obj.get('videoInfo')
        if isinstance(video_info, dict):
            yield video_info
        for value in obj.values():
            yield from _iter_tencent_video_infos(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _iter_tencent_video_infos(value)


def _tencent_search_category(title):
    title = _normalize_tencent_title(title)
    if not title:
        return ''
    if title in _TENCENT_SEARCH_CATEGORY_CACHE:
        return _TENCENT_SEARCH_CATEGORY_CACHE[title]
    category = ''
    try:
        payload = _tencent_search_payload(title)
        for info in _iter_tencent_video_infos(payload):
            found_title = re.sub(r'<[^>]+>', '', html_unescape(info.get('title') or '')).strip()
            if _normalize_tencent_title(found_title) != title:
                continue
            category = normalize_category(info.get('typeName'))
            if category:
                break
    except Exception as err:
        logger.debug(f'腾讯视频搜索分类补全失败：{title}，原因：{err!r}')
    _TENCENT_SEARCH_CATEGORY_CACHE[title] = category
    return category


def _tencent_item_title(item):
    clean = strip_item_category(item)
    _left, sep, right = str(clean).partition('｜')
    if not sep:
        return ''
    title = re.sub(r'（[^）]*预约）$', '', right).strip()
    return _normalize_tencent_title(title)


def _fill_tencent_missing_categories(items):
    out = []
    for item in items or []:
        current_category = item_category(item)
        if current_category and current_category != '未分类':
            out.append(item)
            continue
        title = _tencent_item_title(item)
        category = _tencent_search_category(title) if title else ''
        out.append(with_category(item, category) if category else item)
    return out


async def tencent_page_html_text(url, include_short_drama=False):
    # 按用户偏好：腾讯只抓各频道页里的“即将上线”模块，不合并首页或其它推荐流。
    try:
        from playwright.async_api import async_playwright
        channels = ['tv', 'tvdrama', 'cartoon', 'variety', 'movie']
        if include_short_drama:
            channels.append('shortdrama')
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
    except Exception as err:
        logger.warning(f'腾讯视频动态页面抓取失败，尝试 PageService 兜底，原因：{err!r}')
        pages = await asyncio.to_thread(_tencent_pageservice_pages, include_short_drama)
        if pages:
            return pages
        html, text = await page_html_text('https://v.qq.com/channel/tv', wait=5000)
        return [('tv', html, text)]

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
    return schedule_calendar_key(item)

def _sort_tencent_items(items):
    return sort_platform_items(items)

def _tencent_date_is_future(date, now=None):
    """Return True only when a Tencent preview date is still upcoming."""
    now = now or datetime.now()
    date = normalize_date_text(date)
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
    return _fill_tencent_missing_categories(_sort_tencent_items(_dedupe_tencent_items(merged, 50)))

def _normalize_tencent_title(title):
    original = str(title or '').strip()
    title = re.sub(r'[·・\s]*\d{1,2}月\d{1,2}日(?:上线|开播|首播)?$', '', original).strip()
    title = TENCENT_TITLE_ALIASES.get(title, title)
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
    left = normalize_date_text(left)
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
        title_key = strip_item_category(f'{left}｜{right}').partition('｜')[2]
        title_key = re.sub(r'（[^）]*预约）$', '', title_key)
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
            blobs.extend(json.loads(html_unescape(m.group(1))))
        except Exception:
            pass

    def _params_title(params):
        for key in ('mz_title', 'title_pc', 'priority_title', 'name', 'title'):
            title = str(params.get(key) or '').strip()
            if title:
                return title
        return ''

    def _params_text_blob(params):
        values = []
        for k, v in params.items():
            if re.match(r'marklabel_\d+_prime_text$', str(k)):
                values.append(str(v or ''))
        uni = str(params.get('uni_imgtag') or '')
        if uni:
            values.append(uni)
            try:
                tags = json.loads(uni)
                def tag_walk(o):
                    if isinstance(o, dict):
                        for value in o.values():
                            yield from tag_walk(value)
                    elif isinstance(o, list):
                        for value in o:
                            yield from tag_walk(value)
                    elif isinstance(o, (str, int, float)):
                        yield str(o)
                values.extend(tag_walk(tags))
            except Exception:
                pass
        for key in ('holly_online_time', 'hollywood_online', 'publish_date'):
            values.append(str(params.get(key) or ''))
        return ' '.join(x for x in values if x)

    def walk(o):
        if isinstance(o, dict):
            params = o.get('params') if isinstance(o.get('params'), dict) else o
            title = _params_title(params)
            publish = str(params.get('publish_date') or '')
            blob = ' '.join([title, _params_text_blob(params)])
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
                else:
                    m_rel = re.search(r'(今日|明日|后日|今天|明天|后天)\s*(?:(\d{1,2}):(\d{2})|(\d{1,2})点)?(?:上线|开播|首播)?', blob)
                    if m_rel:
                        date = m_rel.group(1)
                        if m_rel.group(2) and m_rel.group(3):
                            date += f'{int(m_rel.group(2))}:{m_rel.group(3)}'
                        elif m_rel.group(4):
                            date += f'{int(m_rel.group(4))}:00'
                        date = normalize_date_text(date + '上线')
                if not date and re.fullmatch(r'\d{4}-\d{2}-\d{2}', publish):
                    try:
                        y, mo, d = publish.split('-')
                        date = f'{int(mo)}月{int(d)}日'
                    except Exception:
                        pass
                if date and _tencent_date_is_future(date):
                    title = re.sub(r'[·・\s]*\d{1,2}月\d{1,2}日(?:上线|开播|首播)?$', '', str(title)).strip()
                    reserve = ''
                    rm = re.search(r'[\d.]+(?:万)?人(?:已)?预约', blob)
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

def extract_tencent_html(html, text, category=None):
    """腾讯各频道“即将上线”模块：解析激活 Tab 文本，并用 PageService 结构化数据补齐漏项。"""
    items = []
    # 结构化数据里能识别“预约+明确日期”的条目，优先用于补齐动漫等频道首屏漏项。
    items.extend(_tencent_extract_json_items(html))
    items.extend(_tencent_parse_text_module(text))
    html = html_unescape(html)
    # 极端兜底：频道页首屏只暴露“标题·日期”时使用。
    for title, date in re.findall(r'(?:title|name):"([^"·]{2,40})·(\d{1,2}月\d{1,2}日(?:开播|上线|首播))"', html):
        date = re.sub(r'(上线|开播|首播)$', '', date)
        items.append(f'{date}｜{title}')
    items = _sort_tencent_items(_filter_future_tencent_items(_dedupe_tencent_items(items, 30)))
    return with_category_many(items, category) if category else items

def extract_tencent(lines):
    # 保留旧函数名兼容，实际优先 extract_tencent_html。
    items = []
    marker = re.compile(r'即将上线|敬请期待|预约|\d{1,2}月\d{1,2}日|\d{1,2}月\d{1,2}日开播')
    noise = re.compile(r'^(电影|电视剧|综艺|动漫|纪录片|少儿|VIP|全部|更多|腾讯视频|热播|筛选|最新|高分)$')
    for i, line in enumerate(lines):
        if marker.search(line) and not re.search(r'^即将上线$', line):
            win = lines[max(0, i-2):min(len(lines), i+6)]
            title = next((x for x in win if x != line and not noise.search(x) and 2 <= len(x) <= 50 and not marker.search(x)), '')
            date = normalize_date_text(line)
            items.append(f'{date}｜{title}' if title else date)
    return dedupe(items, 12)
