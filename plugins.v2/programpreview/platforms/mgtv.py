# -*- coding: utf-8 -*-
"""芒果 TV 节目预告解析。"""

import re

from ..date_utils import normalize_date_text, sort_platform_items
from ..text_utils import dedupe


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
