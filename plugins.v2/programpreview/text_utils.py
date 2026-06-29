# -*- coding: utf-8 -*-
"""节目预告文本清洗工具。"""

import html
import re


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


def html_unescape(value):
    """反转义 HTML 实体文本。"""
    return html.unescape(value or '')

_html_unescape = html_unescape
