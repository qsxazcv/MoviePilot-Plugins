"""?????? MoviePilot ????????"""

from app import schemas

from .constants import MOVIEPILOT_MEDIA_TYPES

def normalize_image(url: str = "") -> str:
    """
    规范化爱奇艺海报地址。
    """
    url = str(url or "").strip()
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("http://"):
        return "https://" + url[7:]
    return url

def pick_title(item: dict) -> str:
    """
    从爱奇艺接口条目中提取标题。
    """
    return str(
        item.get("name")
        or item.get("title")
        or item.get("album_name")
        or item.get("display_name")
        or item.get("short_display_name")
        or ""
    ).strip()

def pick_year(item: dict) -> str:
    """
    从上线日期字段中提取年份。
    """
    date = item.get("date")
    if isinstance(date, dict) and date.get("year"):
        return str(date.get("year"))
    period = str(item.get("period") or item.get("publishTime") or item.get("showDate") or "")
    if len(period) >= 4 and period[:4].isdigit():
        return period[:4]
    return ""

def pick_media_id(item: dict) -> str:
    """
    从爱奇艺条目中提取稳定媒体 ID。
    """
    for key in ("albumId", "album_id", "qipuId", "qipu_id", "tvId", "tv_id", "firstId"):
        value = item.get(key)
        if value:
            return str(value)
    return ""

def to_media(item: dict, mtype: str) -> schemas.MediaInfo:
    """
    将爱奇艺条目转换为 MoviePilot 媒体信息。
    """
    title = pick_title(item)
    year = pick_year(item)
    image_url = normalize_image(
        item.get("imageUrl")
        or item.get("poster")
        or item.get("album_image_url_hover")
        or item.get("album_img")
        or item.get("image_url_normal")
        or item.get("image_cover")
        or item.get("image_url")
        or item.get("thumbnail_url")
        or item.get("banner_image_url")
        or item.get("back_image")
        or ""
    )
    return schemas.MediaInfo(
        type=MOVIEPILOT_MEDIA_TYPES.get(mtype, "电视剧"),
        title=title,
        year=year,
        title_year=f"{title} ({year})" if year else title,
        # source 用于 resolve_media_identity 解析媒体身份，缺省会导致
        # /mediaserver/notexists 无法识别该来源，订阅弹窗媒体库状态为空
        # 而兜底默认「全集洗版」；补上后订阅默认恢复「普通订阅」。
        source="iqiyi",
        mediaid_prefix="iqiyi",
        media_id=pick_media_id(item),
        poster_path=image_url,
        overview=item.get("description") or item.get("desc") or "",
        vote_average=float(item.get("score") or 0),
    )
