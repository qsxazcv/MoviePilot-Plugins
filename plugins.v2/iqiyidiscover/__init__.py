import time
from typing import Any, Dict, List, Optional, Tuple

from app import schemas
from app.core.config import settings
from app.core.event import Event, eventmanager
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import DiscoverSourceEventData
from app.schemas.types import ChainEventType, MediaType

from .client import request_videolib
from .constants import (
    ADVANCED_FILTER_MODELS,
    FILTER_EXPAND_COLLAPSED_VALUE,
    FILTER_EXPAND_MODEL,
    FILTER_MODELS,
)
from .filters import apply_official_filter_json, filter_query_params, normalize_mode
from .media import pick_media_id, pick_title, pick_year, to_media
from .recognize import request_avlist, strip_episode_noise, year_from_publish_time
from .ui import iqiyi_filter_ui

class IqiyiDiscover(_PluginBase):
    """
    爱奇艺探索插件，让探索支持爱奇艺片库数据浏览。
    """

    plugin_name = "爱奇艺探索"
    plugin_desc = "让探索支持爱奇艺视频的数据浏览。"
    plugin_icon = "https://www.iqiyi.com/logo.png"
    plugin_version = "1.0.41"
    plugin_label = "探索"
    plugin_author = "qsxazcv"
    author_url = "https://github.com/qsxazcv/MoviePilot-Plugins"
    plugin_config_prefix = "iqiyidiscover_"
    plugin_order = 98
    auth_level = 1

    # 专辑 ID 到标题/年份的映射缓存键（用于识别兜底，vlist 接口失效时使用）
    _ALBUM_CACHE_KEY = "iqiyi_album_cache"

    _enabled = False

    def init_plugin(self, config: dict = None) -> None:
        """
        根据配置初始化插件状态，并补充爱奇艺图片安全域名。
        """
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self.__ensure_image_domains()

    def get_state(self) -> bool:
        """
        获取插件启用状态。
        """
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        返回插件远程命令列表。
        """
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """
        注册爱奇艺探索数据 API。
        """
        return [
            {
                "path": "/iqiyi_discover",
                "endpoint": self.iqiyi_discover,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "爱奇艺探索数据源",
                "description": "获取爱奇艺片库探索数据",
            }
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        返回插件配置表单与默认配置。
        """
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ], {"enabled": False}

    def get_page(self) -> List[dict]:
        """
        返回插件详情页。
        """
        return [
            {
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "tonal",
                    "text": "启用后会在 MoviePilot 探索页新增“爱奇艺”数据源。",
                },
            }
        ]

    @staticmethod
    def __ensure_image_domains() -> None:
        """
        将爱奇艺图片主域名加入 MoviePilot 安全图片域名，子域由非严格匹配自动覆盖。
        """
        if "iqiyipic.com" not in settings.SECURITY_IMAGE_DOMAINS:
            settings.SECURITY_IMAGE_DOMAINS.append("iqiyipic.com")

    def get_module(self) -> Dict[str, Any]:
        """
        注册媒体识别模块（方法名 -> 方法实现）。

        注意：get_module 协议要求返回 dict，key 是模块方法名（如 async_recognize_media），
        不是数据源名称。来源过滤（iqiyi / iqiyidiscover）由 recognize_media /
        async_recognize_media 内部通过 source 参数自行判断，因此只需注册一次。
        """
        if not self._enabled:
            return {}
        return {
            "recognize_media": self.recognize_media,
            "async_recognize_media": self.async_recognize_media,
        }

    def recognize_media(
        self,
        meta: Any = None,
        mtype: MediaType = None,
        tmdbid: int = None,
        doubanid: str = None,
        bangumiid: int = None,
        anilistid: int = None,
        source: str = None,
        mediaid: str = None,
        **kwargs,
    ) -> Optional[schemas.MediaInfo]:
        """
        同步识别：按爱奇艺 albumId 拉取剧集信息，转 TMDB 搜索后回填 iqiyi 身份。
        """
        if not self._enabled:
            return None
        if source not in ("iqiyi", "iqiyidiscover") or not mediaid:
            return None
        try:
            return self.__recognize_iqiyi(mediaid, meta)
        except Exception as e:
            logger.error(f"爱奇艺识别失败：{str(e)}")
            return None

    async def async_recognize_media(
        self,
        meta: Any = None,
        mtype: MediaType = None,
        tmdbid: int = None,
        doubanid: str = None,
        bangumiid: int = None,
        anilistid: int = None,
        source: str = None,
        mediaid: str = None,
        **kwargs,
    ) -> Optional[schemas.MediaInfo]:
        """
        异步识别：订阅弹窗季集查询走此入口。
        """
        if not self._enabled:
            return None
        if source not in ("iqiyi", "iqiyidiscover") or not mediaid:
            return None
        try:
            return self.__recognize_iqiyi(mediaid, meta)
        except Exception as e:
            logger.error(f"爱奇艺异步识别失败：{str(e)}")
            return None

    def __recognize_iqiyi(
        self, mediaid: str, meta: Any = None
    ) -> Optional[schemas.MediaInfo]:
        """
        爱奇艺识别核心逻辑：优先按 avlist 真实剧名走 TMDB，失败时回退本地缓存剧名，
        最后回退原标题。
        """
        from app.chain.media import MediaChain

        avlist = request_avlist(mediaid)
        if avlist:
            search_meta, search_type, search_year = self.__prepare_iqiyi_meta(
                avlist, meta
            )
            if search_meta:
                # 年份通过 meta.year 传递：recognize_media 签名不含 year 参数，
                # 直接传 year= 会触发 TypeError 导致识别失败
                if search_year:
                    search_meta.year = search_year
                media_chain = MediaChain()
                mediainfo = media_chain.recognize_media(
                    meta=search_meta, mtype=search_type
                )
                if mediainfo:
                    return self.__finalize_iqiyi_mediainfo(
                        mediainfo, mediaid, search_type, avlist
                    )
        # 回退1：使用探索页缓存的爱奇艺剧名（vlist 接口失效时的主要兜底路径）
        cached = self.__get_cached_album(mediaid)
        # 回退1.5：缓存未命中时，主动从探索推荐接口按 albumId 找回剧名并补缓存
        # （vlist 接口 404 后，未浏览过探索页直接点订阅时的应急路径）
        if not cached:
            item = self.__fetch_videolib_item(mediaid)
            if item:
                self.__cache_albums([item])
                cached = (pick_title(item), pick_year(item) or None)
        if cached:
            cached_title, cached_year = cached
            if cached_title:
                from app.core.metainfo import MetaInfo

                search_meta = MetaInfo(title=cached_title)
                search_meta.type = MediaType.TV
                if cached_year:
                    search_meta.year = cached_year
                media_chain = MediaChain()
                mediainfo = media_chain.recognize_media(
                    meta=search_meta,
                    mtype=MediaType.TV,
                )
                if mediainfo:
                    return self.__finalize_iqiyi_mediainfo(
                        mediainfo, mediaid, MediaType.TV, None
                    )
        # 回退2：按原始请求标题识别（电影等无 avlist 的场景）
        if meta and getattr(meta, "title", None):
            from app.chain.media import MediaChain

            media_chain = MediaChain()
            mediainfo = media_chain.recognize_media(meta=meta)
            if mediainfo:
                return self.__finalize_iqiyi_mediainfo(
                    mediainfo, mediaid, getattr(meta, "type", None), None
                )
        return None

    @staticmethod
    def __cache_key_for(media_id: str) -> str:
        """
        生成专辑缓存键（归一化数字字符串）。
        """
        return str(media_id or "").strip()

    def __get_cached_album(self, media_id: str) -> Optional[Tuple[str, Optional[str]]]:
        """
        从插件数据缓存中读取专辑 ID 对应的剧名与年份。

        :param media_id: 爱奇艺专辑 ID
        :return: (title, year) 或 None
        """
        if not media_id:
            return None
        cache = self.get_data(self._ALBUM_CACHE_KEY) or {}
        if not isinstance(cache, dict):
            return None
        item = cache.get(self.__cache_key_for(media_id)) or {}
        if not isinstance(item, dict):
            return None
        title = str(item.get("title") or "").strip()
        if not title:
            return None
        year = str(item.get("year") or "").strip() or None
        return title, year

    def __fetch_videolib_item(self, media_id: str) -> Optional[Dict[str, Any]]:
        """
        从爱奇艺探索推荐接口主动查找 albumId 对应的条目。

        扫描电视剧频道推荐列表（最多 2 页），命中即返回条目，用于 vlist
        接口失效且本地缓存未命中时，按 albumId 找回剧名后走 TMDB 识别。
        """
        media_id = str(media_id or "").strip()
        if not media_id:
            return None
        for page in (1, 2):
            rows = request_videolib(page=page, mtype="tv", count=48)
            for item in rows:
                if not isinstance(item, dict):
                    continue
                if str(pick_media_id(item) or "").strip() == media_id:
                    return item
        return None

    def __prune_album_cache(self, cache: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理超过 3 天的专辑缓存条目，避免缓存无限增长。

        无时间戳的历史条目保留并补齐时间戳，兼容旧数据。
        """
        if not isinstance(cache, dict) or not cache:
            return cache
        now = time.time()
        keep_after = now - 3 * 86400
        kept: Dict[str, Any] = {}
        for key, item in cache.items():
            if not isinstance(item, dict):
                continue
            ts = item.get("updated_at")
            if not ts:
                item = dict(item)
                item["updated_at"] = int(now)
                kept[key] = item
                continue
            try:
                ts = float(ts)
            except (TypeError, ValueError):
                ts = 0
            if ts >= keep_after:
                kept[key] = item
        return kept

    def __cache_albums(self, rows: List[dict]) -> None:
        """
        把探索页返回的爱奇艺专辑条目写入本地缓存（albumId -> title/year），
        供识别兜底使用。缓存按 3 天自然过期，由 __prune_album_cache 清理。
        """
        if not rows:
            return
        cache = self.get_data(self._ALBUM_CACHE_KEY) or {}
        if not isinstance(cache, dict):
            cache = {}
        # 写入前先清理超过 3 天的旧条目，避免缓存无限增长
        cache = self.__prune_album_cache(cache)
        changed = False
        for item in rows:
            if not isinstance(item, dict):
                continue
            media_id = pick_media_id(item)
            title = pick_title(item)
            if not media_id or not title:
                continue
            key = self.__cache_key_for(media_id)
            existing = cache.get(key) or {}
            if not isinstance(existing, dict):
                existing = {}
            year = pick_year(item)
            # 内容变更时覆盖更新（非空保护），老剧改名/改年份能及时生效
            if existing.get("title") != title:
                existing = dict(existing)
                existing["title"] = title
                changed = True
            if year and existing.get("year") != year:
                existing = dict(existing)
                existing["year"] = year
                changed = True
            if existing is not cache.get(key):
                existing["updated_at"] = int(time.time())
                cache[key] = existing
        if changed:
            self.save_data(self._ALBUM_CACHE_KEY, cache)
            logger.debug(f"爱奇艺探索缓存已更新 {len(cache)} 条专辑映射")

    @staticmethod
    def __prepare_iqiyi_meta(
        avlist: Dict[str, Any], meta: Any = None
    ) -> Tuple[Optional[Any], MediaType, Optional[str]]:
        """
        从 avlist 构造用于 TMDB 搜索的 MetaInfo。

        :return: (search_meta, media_type, year)
        """
        from app.core.metainfo import MetaInfo

        vlist = avlist.get("vlist") or []
        if not vlist:
            return None, None, None
        first = vlist[0]
        title = strip_episode_noise(str(first.get("shortTitle") or ""))
        if not title and meta:
            title = getattr(meta, "title", "") or ""
        if not title:
            return None, None, None
        year = year_from_publish_time(first.get("publishTime"))
        search_meta = MetaInfo(title=title)
        search_meta.type = MediaType.TV
        return search_meta, MediaType.TV, year

    @staticmethod
    def __finalize_iqiyi_mediainfo(
        mediainfo: Any,
        mediaid: str,
        media_type: MediaType = None,
        avlist: Dict[str, Any] = None,
    ) -> schemas.MediaInfo:
        """
        将识别结果回填为 iqiyi 身份，电视剧无季信息时按 allNum 补齐。
        """
        mediainfo.source = "iqiyi"
        mediainfo.media_id = mediaid
        if media_type == MediaType.TV and not mediainfo.seasons and avlist:
            all_num = avlist.get("allNum")
            if all_num:
                mediainfo.seasons = [{"season_number": 1, "episode_count": int(all_num)}]
        return mediainfo

    def iqiyi_discover(
        self,
        mtype: str = "tv",
        mode: str = "11",
        filter_expand: str = None,
        region: str = None,
        genre: str = None,
        subgenre: str = None,
        age: str = None,
        age_detail: str = None,
        audience: str = None,
        rank: str = None,
        spec: str = None,
        award: str = None,
        hall: str = None,
        theater: str = None,
        actor: str = None,
        recommend: str = None,
        setting: str = None,
        background: str = None,
        style: str = None,
        star: str = None,
        serial: str = None,
        version: str = None,
        screen: str = None,
        series: str = None,
        language: str = None,
        producer: str = None,
        person: str = None,
        grade: str = None,
        subject: str = None,
        duration: str = None,
        year: str = None,
        is_purchase: str = None,
        page: int = 1,
        count: int = 10,
    ) -> List[schemas.MediaInfo]:
        """
        获取爱奇艺探索数据。
        """
        mode = normalize_mode(mtype, mode)
        query_params = filter_query_params(
            mtype=mtype,
            region=region,
            genre=genre,
            subgenre=subgenre,
            age=age,
            age_detail=age_detail,
            audience=audience,
            rank=rank,
            spec=spec,
            award=award,
            hall=hall,
            theater=theater,
            recommend=recommend,
            setting=setting,
            background=background,
            actor=actor,
            style=style,
            star=star,
            serial=serial,
            version=version,
            screen=screen,
            series=series,
            language=language,
            producer=producer,
            person=person,
            grade=grade,
            subject=subject,
            duration=duration,
            year=year,
            is_purchase=is_purchase,
        )
        filter_mode = query_params.pop("mode", "")
        if filter_mode == "24":
            mode = "24"
            query_params.pop("is_purchase", None)
            query_params.pop("recent_free", None)
        three_category_id = query_params.pop("three_category_id", "")
        year_param = query_params.pop("market_release_date_level", "")
        is_purchase_param = query_params.pop("is_purchase", "")
        recent_free_param = query_params.pop("recent_free", "")
        if recent_free_param and is_purchase_param == "0":
            is_purchase_param = "0_recent_free"
        apply_official_filter_json(query_params)
        rows = request_videolib(
            page=page,
            mtype=mtype,
            mode=mode,
            three_category_id=three_category_id,
            year=year_param,
            is_purchase=is_purchase_param,
            recent_free=recent_free_param,
            count=count,
            extra_params=tuple(query_params.items()),
        )
        medias: List[schemas.MediaInfo] = []
        seen = set()
        for item in rows:
            if not isinstance(item, dict):
                continue
            title = pick_title(item)
            media_id = pick_media_id(item)
            if not title or not media_id:
                continue
            key = (title, media_id)
            if key in seen:
                continue
            seen.add(key)
            medias.append(to_media(item, mtype))
            if len(medias) >= max(int(count or 10), 1):
                break
        # 把当前页专辑信息写入缓存，供识别兜底
        self.__cache_albums(rows)
        return medias

    @eventmanager.register(ChainEventType.DiscoverSource)
    def discover_source(self, event: Event) -> None:
        """
        向 MoviePilot 探索页注册爱奇艺数据源。
        """
        if not self._enabled:
            return
        event_data: DiscoverSourceEventData = event.event_data
        depends = {model: ["mtype"] for model in FILTER_MODELS}
        for model in ADVANCED_FILTER_MODELS:
            if model in depends:
                depends[model] = ["mtype", FILTER_EXPAND_MODEL]
        depends[FILTER_EXPAND_MODEL] = ["mtype"]
        depends["subgenre"] = ["mtype", "genre", FILTER_EXPAND_MODEL]
        iqiyi_source = schemas.DiscoverMediaSource(
            name="爱奇艺",
            mediaid_prefix="iqiyidiscover",
            api_path=f"plugin/IqiyiDiscover/iqiyi_discover?apikey={settings.API_TOKEN}",
            filter_params={
                "mtype": "tv",
                "mode": "11",
                FILTER_EXPAND_MODEL: FILTER_EXPAND_COLLAPSED_VALUE,
                **{model: None for model in FILTER_MODELS},
            },
            filter_ui=iqiyi_filter_ui(),
            depends=depends,
        )
        if not event_data.extra_sources:
            event_data.extra_sources = [iqiyi_source]
        else:
            event_data.extra_sources.append(iqiyi_source)

    def stop_service(self) -> None:
        """
        停止插件服务。
        """
        return None
