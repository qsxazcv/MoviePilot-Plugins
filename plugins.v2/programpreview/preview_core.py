#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""节目预告兼容入口，重新导出拆分后的功能模块。"""

import argparse
import asyncio

from .cache import apply_platform_cache, load_platform_cache, save_platform_cache
from .constants import DATA_DIR, OUT_FILE, PLATFORM_CACHE_FILE, PLATFORM_CACHE_TTL_HOURS, PLUGIN_DIR, SITES, STATE_FILE, UA
from .date_utils import (
    calendar_date_text as _calendar_date_text,
    format_preview_item as _format_preview_item,
    normalize_date_text as _normalize_date_text,
    schedule_calendar_key as _schedule_calendar_key,
    schedule_time_parts as _schedule_time_parts,
    sort_platform_items as _sort_platform_items,
)
from .fetcher import iqiyi_filtered_page_html_text, page_html_text, page_text
from .notify import notify
from .runner import digest, fetch_site, main
from .text_utils import clean_lines, dedupe, html_unescape as _html_unescape


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='抓取四大平台节目预告并写入 MoviePilot 通知')
    parser.add_argument('--force-notify', action='store_true', help='即使内容未变化也发送 MoviePilot 通知')
    args = parser.parse_args()
    asyncio.run(main(force_notify=args.force_notify))
