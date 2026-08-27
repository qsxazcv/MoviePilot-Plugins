"""?????????????"""

import random
import string
from typing import List, Tuple

from app.sdk.config import settings
from app.sdk.logging import logger
from app.sdk.network import RequestUtils

from .constants import CHANNEL_PARAMS, IQIYI_HEADERS
from .filters import normalize_mode

def build_device_id() -> str:
    """
    生成爱奇艺列表接口使用的临时设备 ID。
    """
    return "".join(random.choice(string.hexdigits.lower()) for _ in range(32))


def request_videolib(
        page: int,
        mtype: str,
        mode: str = "11",
        three_category_id: str = None,
        year: str = None,
        is_purchase: str = None,
        recent_free: str = None,
        count: int = 24,
        extra_params: Tuple[Tuple[str, str], ...] = (),
) -> List[dict]:
    """
    请求爱奇艺推荐列表接口。
    """
    channel = CHANNEL_PARAMS.get(mtype, CHANNEL_PARAMS["tv"])
    mode = normalize_mode(
        mtype,
        mode,
        allow_recent=str(mode or "") == "24" or str(is_purchase or "") in ("0", "0_recent_free"),
    )
    device_id = build_device_id()
    params = {
        "channel_id": channel["id"],
        "mode": mode,
        "page_id": str(max(int(page or 1), 1)),
        "ret_num": str(max(int(count or 24), 1)),
        "version": "11.0",
        "pcv": "",
        "device": device_id,
        "device_id": device_id,
        "uid": "",
        "passport_id": "",
    }
    url = "https://mesh.if.iqiyi.com/portal/videolib/data"
    if three_category_id:
        params["three_category_id"] = three_category_id
    if year:
        params["market_release_date_level"] = str(year)
    if is_purchase:
        params["is_purchase"] = "0" if str(is_purchase) == "0_recent_free" else str(is_purchase)
    if recent_free:
        params["recent_free"] = str(recent_free)
    for key, value in extra_params or ():
        if key and value:
            params[str(key)] = str(value)
    try:
        response = RequestUtils(
            proxies=settings.PROXY,
            headers=IQIYI_HEADERS,
            timeout=15,
        ).get_res(url=url, params=params)
        if not response or response.status_code != 200:
            return []
        data = response.json()
    except Exception as err:
        logger.warning(f"请求爱奇艺探索数据失败: {err}")
        return []
    if data.get("code") not in ("A00000", 0, "0"):
        logger.warning(f"爱奇艺探索接口返回异常: {data.get('code')} {data.get('msg')}")
        return []
    rows = data.get("data") or []
    if isinstance(rows, dict):
        rows = rows.get("list") or rows.get("items") or rows.get("data") or []
    return rows if isinstance(rows, list) else []
