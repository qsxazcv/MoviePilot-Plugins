# -*- coding: utf-8 -*-
"""芒果 TV 节目预告解析。"""

import json
import re
import urllib.request
from html import unescape

from ..categories import normalize_category, with_category
from ..constants import UA
from ..date_utils import normalize_date_text, sort_platform_items
from ..text_utils import dedupe

MGTV_PLAYBILL_URL = 'https://playbill.api.mgtv.com/yy/module?pbId=9&allowedRC=1&type=4&uuid=&ticket=&device=pcweb&_support=10000000'
_MGTV_DETAIL_CATEGORY_CACHE = {}


def _mgtv_decode_js_value(value):
    value = str(value or '').strip()
    if value.startswith('"') and value.endswith('"'):
        try:
            return json.loads(value)
        except Exception:
            return value[1:-1].replace('\\u002F', '/')
    return value


def _mgtv_split_js_args(text):
    args = []
    cur = ''
    in_str = False
    esc = False
    depth = 0
    for ch in str(text or ''):
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
            args.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        args.append(cur.strip())
    return args


def _mgtv_nuxt_vars(text):
    nuxt_pos = str(text or '').find('window.__NUXT__=')
    nuxt_text = text[nuxt_pos:] if nuxt_pos >= 0 else str(text or '')
    script_end = nuxt_text.find('</script>')
    if script_end >= 0:
        nuxt_text = nuxt_text[:script_end]
    m = re.search(r'window\.__NUXT__=\(function\((.*?)\)\{', nuxt_text, re.S)
    tail = re.search(r'\}\((.*?)\)\);?\s*$', nuxt_text, re.S)
    if not m or not tail:
        return {}, nuxt_text
    names = [x.strip() for x in m.group(1).split(',')]
    args = _mgtv_split_js_args(tail.group(1))
    return {name: _mgtv_decode_js_value(val) for name, val in zip(names, args)}, nuxt_text


def _mgtv_category_from_text(text):
    text = re.sub(r'\s+', '', str(text or ''))
    if not text:
        return ''
    for key in ('纪录片', '纪录', '电影', '电视剧', '剧集', '综艺', '动漫', '动画', '少儿', '儿童', '短剧'):
        if key in text:
            return normalize_category(key)
    return ''


def _mgtv_resolve_token(token, var_map):
    token = str(token or '').strip()
    if token in var_map:
        return var_map.get(token)
    return _mgtv_decode_js_value(token)


def _mgtv_category_from_detail_html(html_text):
    """从芒果详情页 SSR 数据提取一级分类。"""
    text = unescape(html_text or '')
    var_map, nuxt_text = _mgtv_nuxt_vars(text)

    for m in re.finditer(r'detail:\{(?P<body>.{0,1600}?)\}', nuxt_text, re.S):
        fm = re.search(r'fstlvlType:(?P<value>[^,{}]+)', m.group('body'))
        if not fm:
            continue
        category = _mgtv_category_from_text(_mgtv_resolve_token(fm.group('value'), var_map))
        if category:
            return category

    for m in re.finditer(r'font:(?P<value>"[^"]+"|[A-Za-z_$][\w$]*)', nuxt_text):
        category = _mgtv_category_from_text(_mgtv_resolve_token(m.group('value'), var_map))
        if category:
            return category

    for m in re.finditer(r'pcwPath:"(?P<path>tv|movie|variety|cartoon|documentary|child)"', nuxt_text):
        category = {
            'tv': '电视剧',
            'movie': '电影',
            'variety': '综艺',
            'cartoon': '动漫',
            'documentary': '纪录片',
            'child': '少儿',
        }.get(m.group('path'), '')
        if category:
            return category
    return ''


def _mgtv_detail_category_sync(row):
    if not isinstance(row, dict):
        return ''
    url = str(row.get('url') or '').strip()
    aid = str(row.get('aid') or '').strip()
    if not url and aid:
        url = f'https://www.mgtv.com/b/{aid}'
    if not url:
        return ''
    if url in _MGTV_DETAIL_CATEGORY_CACHE:
        return _MGTV_DETAIL_CATEGORY_CACHE[url]
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': UA,
                'Referer': 'https://www.mgtv.com/',
            },
        )
        html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', 'ignore')
        category = _mgtv_category_from_detail_html(html)
    except Exception:
        category = ''
    _MGTV_DETAIL_CATEGORY_CACHE[url] = category
    return category


def _mgtv_is_fixed_begin_time(date):
    date = re.sub(r'\s+', ' ', str(date or '')).strip()
    return bool(re.fullmatch(r'(?:\d{2}-\d{2}|今天|明天|后天|今日|明日|后日)\s+\d{1,2}:\d{2}', date))


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
            items.append(f'{normalize_date_text(line)}｜{title}')
    return sort_platform_items(dedupe(items, 12))


def extract_mgtv_from_data(data, category_lookup=None, include_short_drama=False):
    """解析芒果 TV playbill 即将上线接口。"""
    root = data.get('data') if isinstance(data, dict) else {}
    if not isinstance(root, dict):
        return []
    if root.get('moduleTitle') != '即将上线':
        return []
    more = root.get('more') if isinstance(root.get('more'), dict) else {}
    if more.get('moreName') != '我的预约':
        return []
    items = []
    category_lookup = category_lookup or _mgtv_detail_category_sync
    for row in root.get('data') or []:
        if not isinstance(row, dict):
            continue
        date = str(row.get('beginTime') or '').strip()
        title = str(row.get('title') or row.get('name') or '').strip()
        if not title:
            continue
        if date == '敬请期待':
            continue
        if not _mgtv_is_fixed_begin_time(date):
            continue
        try:
            category = category_lookup(row)
        except Exception:
            category = ''
        items.append(with_category(f'{normalize_date_text(date)}｜{title}', category))
    return sort_platform_items(dedupe(items, 12))


def mgtv_playbill_items(include_short_drama=False):
    """从芒果 TV 公开 playbill 接口读取即将上线预约节目。"""
    req = urllib.request.Request(
        MGTV_PLAYBILL_URL,
        headers={
            'User-Agent': UA,
            'Referer': 'https://www.mgtv.com/',
        },
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode('utf-8', 'ignore'))
    return extract_mgtv_from_data(data, include_short_drama=include_short_drama)
