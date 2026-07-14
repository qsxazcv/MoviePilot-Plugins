# -*- coding: utf-8 -*-
"""节目类型标签工具。"""

import re
from collections import Counter


CATEGORY_ORDER = ["电影", "电视剧", "综艺", "动漫", "纪录片", "短剧", "少儿", "未分类"]

CATEGORY_ALIASES = {
    "影": "电影",
    "电影": "电影",
    "剧": "电视剧",
    "剧集": "电视剧",
    "电视剧": "电视剧",
    "综": "综艺",
    "综艺": "综艺",
    "漫": "动漫",
    "动漫": "动漫",
    "动画": "动漫",
    "漫剧": "动漫",
    "纪": "纪录片",
    "纪录片": "纪录片",
    "纪录": "纪录片",
    "纪实": "纪录片",
    "短": "短剧",
    "短剧": "短剧",
    "少儿": "少儿",
    "儿童": "少儿",
    "未分类": "未分类",
}

CATEGORY_SHORT_LABELS = {
    "电影": "影",
    "电视剧": "剧",
    "综艺": "综",
    "动漫": "漫",
    "纪录片": "纪",
    "短剧": "短",
    "少儿": "少",
    "未分类": "?",
}

SOURCE_CATEGORY = {
    "tencent": {
        "tv": "电视剧",
        "tvdrama": "电视剧",
        "variety": "综艺",
        "cartoon": "动漫",
        "comic": "动漫",
        "movie": "电影",
        "doco": "纪录片",
        "child": "少儿",
        "shortdrama": "短剧",
    },
    "iqiyi": {
        "tv": "电视剧",
        "movie": "电影",
        "variety": "综艺",
        "comic": "动漫",
        "cartoon": "动漫",
        "documentary": "纪录片",
        "rank_tv_reserve": "电视剧",
        "rank_documentary_reserve": "纪录片",
    },
    "youku": {
        "tv": "电视剧",
        "movie": "电影",
        "zy": "综艺",
        "comic": "动漫",
        "child": "少儿",
        "documentary": "纪录片",
        "shortdrama": "短剧",
    },
}

IQIYI_CHANNEL_ID_CATEGORY = {
    "1": "电影",
    "2": "电视剧",
    "3": "纪录片",
    "4": "动漫",
    "6": "综艺",
    "15": "短剧",
    "35": "短剧",
    "37": "短剧",
}


def normalize_category(category):
    text = re.sub(r"\s+", "", str(category or ""))
    if not text:
        return ""
    return CATEGORY_ALIASES.get(text, text if text in CATEGORY_ORDER else "")


def short_category_label(category):
    label = normalize_category(category)
    return CATEGORY_SHORT_LABELS.get(label, label[:1] if label else "?")


def source_category(platform, source):
    return SOURCE_CATEGORY.get(str(platform or "").lower(), {}).get(str(source or "").lower(), "")


def category_from_marker(text):
    text = str(text or "")
    m = re.search(r"^(剧|影|综|漫|少儿|纪)[・·]", text)
    return normalize_category(m.group(1)) if m else ""


def category_from_iqiyi_obj(obj):
    if not isinstance(obj, dict):
        return ""
    for key in ("channel_id", "channelId", "cid", "channel"):
        val = obj.get(key)
        if val is not None:
            category = IQIYI_CHANNEL_ID_CATEGORY.get(str(val))
            if category:
                return category
    fields = []
    for key in ("channel", "channel_name", "channelName", "category", "categoryName", "type", "typeName", "albumType"):
        val = obj.get(key)
        if isinstance(val, str):
            fields.append(val)
    blob = " ".join(fields)
    for key in ("电影", "电视剧", "剧集", "综艺", "动漫", "动画", "漫剧", "纪录片", "纪录", "纪实", "短剧", "少儿"):
        if key in blob:
            return normalize_category(key)
    return ""


def split_category_prefix(text):
    m = re.match(r"^\[([^\]]{1,12})\]\s*(.*)$", str(text or "").strip())
    if not m:
        return "", str(text or "").strip()
    category = normalize_category(m.group(1))
    return category, m.group(2).strip()


def item_category(item):
    text = str(item or "").strip()
    category, _ = split_category_prefix(text)
    if category:
        return category
    _left, sep, right = text.partition("｜")
    if sep:
        category, _ = split_category_prefix(right)
        return category
    return ""


def is_short_drama_item(item):
    return item_category(item) == "短剧"


def filter_short_drama_items(items, include_short_drama=False):
    items = list(items or [])
    if include_short_drama:
        return items
    return [item for item in items if not is_short_drama_item(item)]


def strip_item_category(item):
    text = str(item or "")
    left, sep, right = text.partition("｜")
    if not sep:
        _category, rest = split_category_prefix(text)
        return rest
    _category, rest = split_category_prefix(right)
    return f"{left}｜{rest}"


def with_category(item, category):
    text = str(item or "")
    left, sep, right = text.partition("｜")
    if not sep:
        return text
    label = normalize_category(category)
    if not label:
        return text
    _old, clean_right = split_category_prefix(right)
    return f"{left}｜[{label}] {clean_right}"


def ensure_category(item, default="未分类"):
    if "｜" not in str(item or "") or item_category(item):
        return str(item or "")
    return with_category(item, default)


def with_category_many(items, category):
    return [with_category(item, category) for item in items or []]


def ensure_category_many(items, default="未分类"):
    return [ensure_category(item, default) for item in items or []]


def category_summary(items):
    counts = Counter()
    for item in items or []:
        category = item_category(item)
        if category:
            counts[category] += 1
    return [(name, counts[name]) for name in CATEGORY_ORDER if counts.get(name)]
