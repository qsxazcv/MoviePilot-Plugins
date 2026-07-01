#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""节目预告兼容入口，重新导出拆分后的功能模块。"""

import argparse
import asyncio
import sys
import types
from datetime import datetime
from pathlib import Path

if not __package__:
    package = sys.modules.get("programpreview")
    if package is None:
        package = types.ModuleType("programpreview")
        package.__path__ = [str(Path(__file__).resolve().parent)]
        sys.modules["programpreview"] = package
    __package__ = "programpreview"
    __spec__ = None

from .cache import apply_platform_cache, load_platform_cache, save_platform_cache
from .constants import DATA_DIR, OUT_FILE, PLATFORM_CACHE_FILE, PLATFORM_CACHE_TTL_HOURS, PLUGIN_DIR, SITES, STATE_FILE, UA
from . import date_utils as _date_utils
from .fetcher import iqiyi_filtered_page_html_text, page_html_text, page_text
from .notify import notify
from .platforms import iqiyi as _iqiyi
from .platforms import tencent as _tencent
from .runner import digest, fetch_site, main
from .text_utils import clean_lines, dedupe, html_unescape as _html_unescape

_iqiyi_force_search_reserve_items = _iqiyi._iqiyi_force_search_reserve_items


def _sync_compat_state():
    _date_utils.datetime = datetime
    _iqiyi.datetime = datetime
    _tencent.datetime = datetime
    _iqiyi._iqiyi_force_search_reserve_items = _iqiyi_force_search_reserve_items
    _tencent.load_platform_cache = load_platform_cache


def _normalize_date_text(date):
    return _date_utils.normalize_date_text(date)


def _schedule_time_parts(text):
    return _date_utils.schedule_time_parts(text)


def _schedule_calendar_key(item, now=None):
    _sync_compat_state()
    return _date_utils.schedule_calendar_key(item, now=now)


def _sort_platform_items(items):
    _sync_compat_state()
    return _date_utils.sort_platform_items(items)


def _format_preview_item(platform, item):
    _sync_compat_state()
    return _date_utils.format_preview_item(platform, item)


def _calendar_date_text(text, now=None):
    _sync_compat_state()
    return _date_utils.calendar_date_text(text, now=now)


def _dedupe_iqiyi_items(items, limit=30):
    _sync_compat_state()
    return _iqiyi._dedupe_iqiyi_items(items, limit=limit)


def extract_tencent_html(html, text):
    _sync_compat_state()
    return _tencent.extract_tencent_html(html, text)


def _merge_tencent_items_with_cache(items, cache_name='腾讯视频'):
    _sync_compat_state()
    return _tencent._merge_tencent_items_with_cache(items, cache_name=cache_name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='抓取四大平台节目预告并写入 MoviePilot 通知')
    parser.add_argument('--force-notify', action='store_true', help='即使内容未变化也发送 MoviePilot 通知')
    parser.add_argument('--include-short-drama', action='store_true', help='抓取并显示短剧/微短剧条目')
    args = parser.parse_args()
    asyncio.run(main(force_notify=args.force_notify, include_short_drama=args.include_short_drama))
