import time
from typing import Any, Dict, List, Optional, Tuple

from app import schemas
from app.sdk.config import settings
from app.sdk.events import Event, eventmanager
from app.sdk.logging import logger
from app.plugins import _PluginBase
from app.schemas import DiscoverSourceEventData, MediaRecognizeConvertEventData
from app.schemas.types import ChainEventType, MediaSource, MediaType
from app.sdk.media import resolve_media_identity

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
    plugin_version = "2.1.2"
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
                "response_model": schemas.Response[List[schemas.MediaInfo]],
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
        media_source: MediaSource = None,
        media_id: str = None,
        **kwargs,
    ) -> Optional[schemas.MediaInfo]:
        """
        同步识别：按爱奇艺 albumId 拉取剧集信息，转 TMDB 搜索后回填 iqiyi 身份。

        v3 身份合同：MediaChain 以 media_source/media_id 调用；source/mediaid
        旧参数由 kwargs 兜底兼容。来源经 resolve_media_identity 归一化，
        非爱奇艺来源直接拒绝。
        """
        if not self._enabled:
            return None
        # 旧参数兼容：source/mediaid 由 kwargs 兜底（供旧调用方使用）
        if media_source is None and media_id is None:
            media_source = kwargs.get("source")
            media_id = kwargs.get("mediaid")
        source, normalized_media_id = resolve_media_identity(
            media_source=media_source,
            media_id=media_id,
        )
        if source != MediaSource.Iqiyi or not normalized_media_id:
            return None
        try:
            return self.__recognize_iqiyi(normalized_media_id, meta)
        except Exception as e:
            logger.error(f"爱奇艺识别失败：{str(e)}")
            return None

    async def async_recognize_media(
        self,
        meta: Any = None,
        mtype: MediaType = None,
        media_source: MediaSource = None,
        media_id: str = None,
        **kwargs,
    ) -> Optional[schemas.MediaInfo]:
        """
        异步识别：订阅弹窗季集查询走此入口。

        v3 身份合同：MediaChain 以 media_source/media_id 调用；source/mediaid
        旧参数由 kwargs 兜底兼容。来源经 resolve_media_identity 归一化，
        非爱奇艺来源直接拒绝。
        """
        if not self._enabled:
            return None
        # 旧参数兼容：source/mediaid 由 kwargs 兜底（供旧调用方使用）
        if media_source is None and media_id is None:
            media_source = kwargs.get("source")
            media_id = kwargs.get("mediaid")
        source, normalized_media_id = resolve_media_identity(
            media_source=media_source,
            media_id=media_id,
        )
        if source != MediaSource.Iqiyi or not normalized_media_id:
            return None
        try:
            return self.__recognize_iqiyi(normalized_media_id, meta)
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
        # 缓存优先（cache or fetch）：
        # 先查本地缓存，未命中时实时反查探索推荐接口拿最新剧名并补缓存。
        cached = self.__get_cached_album(mediaid)
        if cached:
            cached_title, cached_year = cached
            if cached_title:
                from app.sdk.media import MetaInfo

                search_meta = MetaInfo(title=cached_title)
                search_meta.type = MediaType.TV
                if cached_year:
                    search_meta.year = cached_year
                mediainfo = MediaChain().recognize_media(
                    meta=search_meta,
                    mtype=MediaType.TV,
                )
                if mediainfo:
                    return self.__finalize_iqiyi_mediainfo(
                        mediainfo, mediaid, MediaType.TV, None
                    )
        # 反查：扫视频道/电影前 2 页按 albumId 匹配，命中后补缓存
        item = self.__fetch_videolib_item(mediaid, mtype="tv")
        if not item:
            item = self.__fetch_videolib_item(mediaid, mtype="movie")
        if item:
            self.__cache_albums([item])
            from app.sdk.media import MetaInfo

            search_meta = MetaInfo(title=pick_title(item))
            search_meta.type = MediaType.TV
            year = pick_year(item)
            if year:
                search_meta.year = year
            mediainfo = MediaChain().recognize_media(
                meta=search_meta,
                mtype=MediaType.TV,
            )
            if mediainfo:
                return self.__finalize_iqiyi_mediainfo(
                    mediainfo, mediaid, MediaType.TV, None,
                    overview=self.__item_overview(item),
                )
        # 回退：按原始请求标题识别
        if meta and getattr(meta, "title", None):
            mediainfo = MediaChain().recognize_media(meta=meta)
            if mediainfo:
                return mediainfo

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

    def __fetch_videolib_item(
        self, media_id: str, mtype: str = "tv"
    ) -> Optional[Dict[str, Any]]:
        """
        从爱奇艺探索推荐接口主动查找 albumId 对应的条目。

        按媒体类型扫描对应频道推荐列表（最多 2 页），命中即返回条目，
        用于 vlist 接口失效且本地缓存未命中时，按 albumId 找回剧名后走 TMDB 识别。
        """
        media_id = str(media_id or "").strip()
        if not media_id:
            return None
        for page in (1, 2):
            rows = request_videolib(page=page, mtype=mtype, count=48)
            for item in rows:
                if not isinstance(item, dict):
                    continue
                if str(pick_media_id(item) or "").strip() == media_id:
                    return item
        return None

    @staticmethod
    def __item_overview(item: Optional[Dict[str, Any]]) -> str:
        """
        从 videolib 条目中提取简介文本，供识别结果补全 overview。
        """
        if not item or not isinstance(item, dict):
            return ""
        for key in ("description", "desc", "longDescription", "intro"):
            value = item.get(key)
            if value:
                text = str(value).strip()
                if text and text.lower() not in ("null", "none"):
                    return text
        return ""

    def __prune_album_cache(self, cache: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理超过 3 天的专辑缓存条目，并限制缓存总量不超过 5000 条。

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
        # 超过上限时按更新时间裁剪，保留最新的 5000 条
        if len(kept) > 5000:
            ordered = sorted(
                kept.items(),
                key=lambda kv: float(kv[1].get("updated_at") or 0),
                reverse=True,
            )
            kept = dict(ordered[:5000])
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
                existing = dict(existing)
                existing["updated_at"] = int(time.time())
                cache[key] = existing
                changed = True
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
        from app.sdk.media import MetaInfo

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
    def __normalize_mtype(media_type: Any) -> Optional[MediaType]:
        """
        将字符串媒体类型统一转换为 MediaType 枚举（防御外部字符串调用）。

        例如 "TV"/"电视剧"/"电影" 等字符串在 __finalize_iqiyi_mediainfo
        判断前统一转换，避免类型比较失效。
        """
        if isinstance(media_type, MediaType):
            return media_type
        if media_type is None:
            return None
        text = str(media_type or "").strip().lower()
        mapping = {
            "movie": MediaType.MOVIE,
            "电影": MediaType.MOVIE,
            "tv": MediaType.TV,
            "电视剧": MediaType.TV,
            "剧集": MediaType.TV,
            "music": MediaType.MUSIC,
            "音乐": MediaType.MUSIC,
        }
        return mapping.get(text)

    @staticmethod
    def __finalize_iqiyi_mediainfo(
        mediainfo: Any,
        mediaid: str,
        media_type: MediaType = None,
        avlist: Dict[str, Any] = None,
        overview: str = "",
    ) -> schemas.MediaInfo:
        """
        将识别结果回填为 iqiyi 身份，电视剧无季信息时按 allNum 补齐。

        :param overview: 反查命中时携带的简介文本，识别结果缺简介时补全
        """
        mediainfo.media_source = MediaSource.Iqiyi
        mediainfo.media_id = mediaid
        media_type = IqiyiDiscover.__normalize_mtype(media_type)
        if overview and not mediainfo.overview:
            mediainfo.overview = overview
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
    ) -> schemas.Response:
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
        return schemas.Response(success=True, data=medias)

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
            media_source=MediaSource.Iqiyi,
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

    @eventmanager.register(ChainEventType.MediaRecognizeConvert)
    def media_recognize_convert(self, event: Event) -> None:
        """
        把爱奇艺探索身份转换为 TMDB 主身份，供订阅搜索链路使用。

        订阅季集查询走 /seasons 明确来源识别（插件 get_module 已覆盖）；
        订阅资源搜索需要 TMDB 主身份，宿主无内置爱奇艺转换时广播本事件，
        插件按已识别结果回填 TMDB 身份，保证订阅能跨源搜索站点资源。
        """
        if not self._enabled:
            return
        event_data: MediaRecognizeConvertEventData = event.event_data
        if not event_data:
            return
        if event_data.target_media_source != MediaSource.TMDB:
            return
        if event_data.media_source != MediaSource.Iqiyi:
            return
        try:
            mediainfo = self.__recognize_iqiyi(event_data.media_id)
        except Exception as e:
            logger.error(f"爱奇艺媒体身份转换失败：{str(e)}")
            return
        tmdb_id = getattr(mediainfo, "tmdb_id", None)
        if tmdb_id:
            event_data.media_dict.update(
                {
                    "id": tmdb_id,
                    "media_source": MediaSource.TMDB,
                    "media_id": str(tmdb_id),
                }
            )

    def stop_service(self) -> None:
        """
        停止插件服务。
        """
        return None
