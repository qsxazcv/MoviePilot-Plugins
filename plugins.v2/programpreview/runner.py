# -*- coding: utf-8 -*-
"""节目预告抓取主流程。"""

import asyncio
import hashlib
import json
from datetime import datetime

from .cache import apply_platform_cache
from .categories import category_summary, ensure_category_many, filter_short_drama_items, short_category_label, source_category, with_category
from .constants import OUT_FILE, SITES, STATE_FILE
from .date_utils import drop_past_items, format_preview_item, sort_platform_items
from .fetcher import page_text
from .notify import notify
from .platforms.iqiyi import (
    _dedupe_iqiyi_items,
    _iqiyi_collect_prelw_items,
    _iqiyi_collect_videolib_items,
    _iqiyi_extract_newonline_items_sync,
    _iqiyi_extract_page_reserve_sync,
    _iqiyi_final_fill_missing_reserves,
    _iqiyi_reset_run_caches,
    _iqiyi_search_page_items_sync,
    _iqiyi_search_page_reserve_sync,
    _iqiyi_subscribe_count_sync,
    _iqiyi_videolib_payloads,
    extract_iqiyi,
    extract_iqiyi_html,
    iqiyi_all_lines,
    iqiyi_home_preview_lines,
    iqiyi_list_all_lines,
    iqiyi_prelw_payloads,
    iqiyi_rank_lines,
)
from .platforms.mgtv import extract_mgtv, mgtv_playbill_items
from .platforms.tencent import (
    _dedupe_tencent_items,
    _merge_tencent_items_with_cache,
    _tencent_search_fallback_items_sync,
    _sort_tencent_items,
    extract_tencent,
    extract_tencent_html,
    tencent_page_html_text,
)
from .platforms.youku import (
    _dedupe_youku_items,
    _youku_sort_key,
    extract_youku,
    extract_youku_from_data,
    youku_all_initial_data,
)
from .text_utils import clean_lines


def digest(data):
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()

def _placeholder_items():
    return ['暂未从公开页面提取到明确“即将上线/预约”条目']


def platform_heading(name, items):
    items = list(items or [])
    summary = ' '.join(f'{short_category_label(category)}{count}' for category, count in category_summary(items))
    parts = [name, f'{len(items)}条']
    if summary:
        parts.append(summary)
    return f"━━━━ {' · '.join(parts)} ━━━━"


async def fetch_site(name, url, include_short_drama=False):
    try:
        if name == '优酷':
            # 优酷主频道 + 电视剧/动漫/电影/综艺频道的“即将上线”合并去重，只保留已定档条目，按上线时间排序。
            items = []
            for _ch, _url, data in await youku_all_initial_data(include_short_drama=include_short_drama):
                items.extend(extract_youku_from_data(data, category=source_category('youku', _ch), include_short_drama=include_short_drama))
            items = sorted(_dedupe_youku_items(items, 50), key=_youku_sort_key)
            if not items:
                txt = await page_text(url)
                items = extract_youku(clean_lines(txt))
        elif name == '腾讯视频':
            pages = await tencent_page_html_text(url, include_short_drama=include_short_drama)
            items = []
            for _ch, html, txt in pages:
                # 主频道 + 电视剧/动漫/综艺/电影频道统一合并，最终按来源频道补分类标签后按上线时间排序。
                items.extend(extract_tencent_html(html, txt, category=source_category('tencent', _ch)))
            items.extend(await asyncio.to_thread(_tencent_search_fallback_items_sync))
            items = _merge_tencent_items_with_cache(items)
            if not items and pages:
                lines = clean_lines(pages[0][2])
                items = _sort_tencent_items(_dedupe_tencent_items(extract_tencent(lines), 50))
                items = [with_category(item, source_category('tencent', pages[0][0])) for item in items]
        else:
            if name == '芒果TV':
                items = await asyncio.to_thread(mgtv_playbill_items, include_short_drama)
                if not items:
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
                prelw_categories = ['电视剧', '动漫', '电影', '综艺']
                for category, payload in zip(prelw_categories, payloads):
                    rows = _iqiyi_collect_prelw_items(payload)
                    for row in rows:
                        row['category'] = row.get('category') or category
                    prelw_rows.extend(rows)
                    for row in rows:
                        qipu_ids.extend(row.get('qids') or [])
                reserve_map = await asyncio.to_thread(_iqiyi_subscribe_count_sync, qipu_ids)
                for row in prelw_rows:
                    reserve = next((reserve_map.get(qid) for qid in row.get('qids') or [] if reserve_map.get(qid)), '')
                    if not reserve:
                        reserve = await asyncio.to_thread(_iqiyi_search_page_reserve_sync, row.get('title'))
                    items.append(with_category(f"{row['date']}｜{row['title']}" + (f'（{reserve}）' if reserve else ''), row.get('category')))
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
                    items.append(with_category(f"{row['date']}｜{row['title']}" + (f'（{reserve}）' if reserve else ''), row.get('category')))
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
                    category = source_category('iqiyi', _ch)
                    items.extend(with_category(item, category) for item in html_items)
                    items.extend(with_category(item, category) for item in text_items)
                for _ch, _html, _txt, _lines in await iqiyi_list_all_lines():
                    category = source_category('iqiyi', _ch)
                    items.extend(with_category(item, category) for item in extract_iqiyi_html(_html))
                    items.extend(with_category(item, category) for item in extract_iqiyi(_lines))
                for _ch, _html, _txt, _lines in await iqiyi_home_preview_lines():
                    category = source_category('iqiyi', _ch)
                    items.extend(with_category(item, category) for item in extract_iqiyi_html(_html))
                    items.extend(with_category(item, category) for item in extract_iqiyi(_lines))
                for _ch, _html, _txt, _lines in await iqiyi_rank_lines():
                    category = source_category('iqiyi', _ch)
                    items.extend(with_category(item, category) for item in extract_iqiyi(_lines))
                # 对已识别到的爱奇艺条目做通用搜索页兜底补数：
                # prelw/频道接口没给预约数时，只去爱奇艺搜索页按片名补齐，不跨平台混用。
                items = _dedupe_iqiyi_items(items, 50)
                # 最终输出前再补一次，确保电影频道 xinpian 文本兜底等来源不会漏合并预约数。
                # 这里必须放到线程里执行：搜索页补数使用 Playwright sync API，不能直接跑在 async event loop 内。
                items = await asyncio.to_thread(_iqiyi_final_fill_missing_reserves, items)
            else:
                items = []
        items = filter_short_drama_items(items, include_short_drama)
        items = ensure_category_many(sort_platform_items(items))
        return name, items or _placeholder_items()
    except Exception as e:
        return name, [f'抓取失败：{e!r}']

async def main(force_notify=False, include_short_drama=False):
    pairs = await asyncio.gather(*(fetch_site(name, url, include_short_drama=include_short_drama) for name, url in SITES))
    result = apply_platform_cache(dict(pairs))
    for name, items in list(result.items()):
        filtered = filter_short_drama_items(items, include_short_drama)
        filtered = drop_past_items(filtered)
        result[name] = filtered or _placeholder_items()
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    md = [f'四大平台即将上线节目预告（{now}）']
    for name, _ in SITES:
        items = sort_platform_items(result[name])
        md.append(f'\n{platform_heading(name, items)}')
        for it in items:
            md.append(f'- {format_preview_item(name, it)}')
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
