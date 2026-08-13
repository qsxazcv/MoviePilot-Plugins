"""
爱奇艺探索插件 - 识别辅助模块。

提供 iqiyi 来源媒体识别所需的工具函数：
- strip_episode_noise: 从剧集标题中剥离分集/期数噪声，得到可用于 TMDB 搜索的剧名
- year_from_publish_time: 从爱奇艺发布时间戳提取年份
- request_avlist: 按 albumId 请求爱奇艺剧集列表接口
"""

import re
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.config import settings
from app.utils.http import RequestUtils

# 分集/期数噪声：第N集 / 第N期 / 第N话 / 第N回 / 更新至N集 等
_EPISODE_NOISE = re.compile(
    r"(?:第\s*\d+\s*(?:集|期|话|回|章|节|弹))"
    r"|(?:更新\s*至\s*\d+\s*集)"
    r"|(?:第\s*\d+\s*季)"
    r"|(?:更新\s*至\s*第\s*\d+\s*集)"
)

# 爱奇艺剧集列表接口（albumId 维度）
_AVLIST_URL = "https://mesh.if.iqiyi.com/portal/album/vlist"


def strip_episode_noise(title: str) -> str:
    """
    剥离标题中的分集/期数噪声，返回干净的剧名。

    示例：
        "这一秒过火第1集" -> "这一秒过火"
        "凡人修仙传第101集" -> "凡人修仙传"
        "幽宅奇谭第1期" -> "幽宅奇谭"
    """
    if not title:
        return ""
    cleaned = _EPISODE_NOISE.sub("", title)
    return cleaned.strip()


def year_from_publish_time(publish_time: Any) -> Optional[str]:
    """
    从爱奇艺发布时间戳（毫秒）提取年份字符串。

    :param publish_time: 毫秒时间戳或可解析的值
    :return: 如 "2025"，无法解析时返回 None
    """
    try:
        ts = int(publish_time or 0)
        if ts <= 0:
            return None
        return str(datetime.fromtimestamp(ts / 1000).year)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def request_avlist(album_id: str) -> Optional[Dict[str, Any]]:
    """
    按 albumId 请求爱奇艺剧集列表接口，返回 vlist 数据。

    :param album_id: 爱奇艺 albumId（如 "5100000000000000"）
    :return: 接口 JSON 的 data 部分；失败或无数据时返回 None
    """
    if not album_id:
        return None
    try:
        res = RequestUtils(
            proxies=settings.PROXY,
            headers={"User-Agent": settings.USER_AGENT},
            timeout=10,
        ).get_res(
            url=_AVLIST_URL,
            params={
                "albumId": album_id,
                "pageNum": 1,
                "pageSize": 1,
                "fields": "shortTitle,publishTime,allNum",
            },
        )
        if not res or res.status_code != 200:
            return None
        data = res.json()
        if not data:
            return None
        result = data.get("data") or {}
        if not result.get("vlist"):
            return None
        return result
    except Exception:
        return None