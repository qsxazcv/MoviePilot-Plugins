# -*- coding: utf-8 -*-
"""爱奇艺节目预告解析。"""

import asyncio
import json
import re
import urllib.parse
import urllib.request

from ..constants import UA
from ..date_utils import calendar_date_text, normalize_date_text, schedule_calendar_key, sort_platform_items
from ..fetcher import iqiyi_filtered_page_html_text, page_html_text
from ..text_utils import clean_lines, dedupe, html_unescape


_IQIYI_SEARCH_RESERVE_CACHE = {}


def _iqiyi_reset_run_caches():
    _IQIYI_SEARCH_RESERVE_CACHE.clear()

def _iqiyi_is_program_preview_date(date):
    date = re.sub(r'\s+', '', str(date or '')).strip('：:')
    return date in {'即将上线', '节目预告', '未定时', '待定', '敬请期待'}

def _iqiyi_normalize_date(date):
    date = calendar_date_text(date)
    return '节目预告' if _iqiyi_is_program_preview_date(date) else date

def _iqiyi_sort_key(item):
    item = re.sub(r'（[^）]*(?:人预约|人已预约|预约破[\d.]+(?:万|千|百)?)）$', '', str(item))
    date = item.split('｜', 1)[0]
    if _iqiyi_is_program_preview_date(date):
        now = datetime.now()
        return (8, now.year, 99, 99, 1, 23 * 60 + 59, item)
    return schedule_calendar_key(item)

def _iqiyi_split_title_reserve(right):
    right = re.sub(r'\s+', ' ', str(right or '')).strip()
    m = re.search(r'^(.*?)(（[^）]*(?:人预约|人已预约|预约破[\d.]+(?:万|千|百)?)）)$', right)
    if m:
        return m.group(1).strip(), m.group(2)
    return right, ''

def _iqiyi_find_reserve_near(text):
    text = html_unescape(text or '')
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
    text = html_unescape(text)
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
        text = html_unescape(text or '')
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
                    text = html_unescape(text or '')
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
    text = html_unescape(text or '')
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
    html_text = html_unescape(html_text or '')
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

iqiyi_reset_run_caches = _iqiyi_reset_run_caches
