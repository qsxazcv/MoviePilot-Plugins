# -*- coding: utf-8 -*-
"""芒果 TV 节目预告解析。"""

import json
import re
import urllib.request

from ..constants import UA
from ..date_utils import normalize_date_text, sort_platform_items
from ..text_utils import dedupe

MGTV_PLAYBILL_URL = 'https://playbill.api.mgtv.com/yy/module?pbId=9&allowedRC=1&type=4&uuid=&ticket=&device=pcweb&_support=10000000'


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


def extract_mgtv_from_data(data):
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
    for row in root.get('data') or []:
        if not isinstance(row, dict):
            continue
        date = str(row.get('beginTime') or '').strip()
        title = str(row.get('title') or row.get('name') or '').strip()
        if not title or date == '敬请期待':
            continue
        if not re.fullmatch(r'\d{2}-\d{2}\s+\d{2}:\d{2}', date):
            continue
        items.append(f'{normalize_date_text(date)}｜{title}')
    return sort_platform_items(dedupe(items, 12))


def mgtv_playbill_items():
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
    return extract_mgtv_from_data(data)
