# -*- coding: utf-8 -*-
"""节目预告插件常量与路径配置。"""

from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
DATA_DIR = Path('/config/plugins/programpreview')
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = DATA_DIR / 'latest_preview.md'
STATE_FILE = DATA_DIR / 'state.json'
PLATFORM_CACHE_FILE = DATA_DIR / 'platform_cache.json'
OUT_FILE.touch(exist_ok=True)
PLATFORM_CACHE_TTL_HOURS = 72

SITES = [
    ('爱奇艺', 'https://www.iqiyi.com/'),
    ('腾讯视频', 'https://v.qq.com/channel/tv'),
    ('芒果TV', 'https://www.mgtv.com'),
    ('优酷', 'https://www.youku.com/ku/webhome'),
]

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
