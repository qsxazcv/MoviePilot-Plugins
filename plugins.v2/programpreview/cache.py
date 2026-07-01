# -*- coding: utf-8 -*-
"""节目预告平台结果缓存。"""

import json
from datetime import datetime, timedelta

from .constants import PLATFORM_CACHE_FILE, PLATFORM_CACHE_TTL_HOURS
from .date_utils import sort_platform_items


def load_platform_cache():
    """读取平台缓存数据。"""
    if PLATFORM_CACHE_FILE.exists():
        try:
            return json.loads(PLATFORM_CACHE_FILE.read_text('utf-8'))
        except Exception:
            return {}
    return {}


def save_platform_cache(cache):
    """保存平台缓存数据。"""
    try:
        PLATFORM_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def is_placeholder_items(items):
    """判断平台结果是否为抓取失败占位。"""
    if not items:
        return True
    joined = '\n'.join(map(str, items))
    return '暂无可解析的即将上线/预约节目' in joined or '抓取失败' in joined


def is_platform_cache_fresh(old, now_dt):
    """判断平台缓存是否仍在有效期。"""
    if not isinstance(old, dict):
        return False
    stamp = str(old.get('time') or '').strip()
    try:
        cached_at = datetime.strptime(stamp, '%Y-%m-%d %H:%M')
    except Exception:
        return False
    return now_dt - cached_at <= timedelta(hours=PLATFORM_CACHE_TTL_HOURS)


def apply_platform_cache(result, use_cache_fallback=False):
    """Use cached platform results only when fallback is explicitly enabled."""
    if not use_cache_fallback:
        for name, items in list(result.items()):
            if not is_placeholder_items(items):
                result[name] = sort_platform_items(items)
        return result

    cache = load_platform_cache()
    now_dt = datetime.now()
    now = now_dt.strftime('%Y-%m-%d %H:%M')
    changed = False
    for name, items in list(result.items()):
        if is_placeholder_items(items):
            old = cache.get(name, {})
            old_items = old.get('items') if isinstance(old, dict) else None
            if old_items and not is_placeholder_items(old_items) and is_platform_cache_fresh(old, now_dt):
                stamp = old.get('time') or '??'
                result[name] = [f'{x}（缓存 {stamp}）' for x in old_items]
        else:
            items = sort_platform_items(items)
            result[name] = items
            cache[name] = {'time': now, 'items': items}
            changed = True
    if changed:
        save_platform_cache(cache)
    return result
