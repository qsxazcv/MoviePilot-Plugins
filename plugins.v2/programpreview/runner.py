# -*- coding: utf-8 -*-
"""节目预告抓取主流程。"""

import asyncio
import hashlib
import json
from datetime import datetime

from .cache import apply_platform_cache
from .constants import OUT_FILE, SITES, STATE_FILE
from .date_utils import format_preview_item, sort_platform_items
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
                items = await asyncio.to_thread(mgtv_playbill_items)
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
        items = sort_platform_items(items)
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
        for it in sort_platform_items(result[name]):
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
