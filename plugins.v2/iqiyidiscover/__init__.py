import time
from typing import Any, Dict, List, Optional, Tuple

from app import schemas
from app.chain.media import MediaChain
from app.core.config import settings
from app.core.event import Event, eventmanager
from app.core.metainfo import MetaBase, MetaInfo
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import DiscoverSourceEventData, MediaRecognizeConvertEventData
from app.schemas.types import ChainEventType, MediaType

from .client import request_videolib
from .constants import (
    ADVANCED_FILTER_MODELS,
    FILTER_EXPAND_COLLAPSED_VALUE,
    FILTER_EXPAND_MODEL,
    FILTER_MODELS,
)
from .filters import apply_official_filter_json, filter_query_params, normalize_mode
from .media import pick_media_id, pick_title, to_media
from .ui import iqiyi_filter_ui

class IqiyiDiscover(_PluginBase):
    """
    爱奇艺探索插件，让探索支持爱奇艺片库数据浏览。
    """

    plugin_name = "爱奇艺探索"
    plugin_desc = "让探索支持爱奇艺视频的数据浏览。"
    plugin_icon = "https://www.iqiyi.com/logo.png"
    plugin_version = "1.0.43"
    plugin_label = "探索"
    plugin_author = "qsxazcv"
    author_url = "https://github.com/qsxazcv/MoviePilot-Plugins"
    plugin_config_prefix = "iqiyidiscover_"
    plugin_order = 98
    auth_level = 1

    _enabled = False

    # 探索条目缓存：albumId -> (缓存时间戳, MediaInfo)，用于详情识别补全
    _media_cache: Dict[str, Tuple[float, schemas.MediaInfo]] = {}
    _MEDIA_CACHE_TTL = 24 * 3600
    _MEDIA_CACHE_MAX = 500
    # 持久化缓存使用的插件数据 key
    _MEDIA_CACHE_DATA_KEY = "media_cache_data"
    # 磁盘缓存是否已加载到内存（惰性加载，避免重复读插件数据）
    _disk_cache_loaded = False

    def init_plugin(self, config: dict = None) -> None:
        """
        根据配置初始化插件状态，并补充爱奇艺图片安全域名。
        """
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._media_cache = {}
        self._disk_cache_loaded = False
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
        将爱奇艺图片域名加入 MoviePilot 安全图片域名。
        """
        domains = (
            ["iqiyipic.com", "www.iqiyipic.com", "m.iqiyipic.com", "u0.iqiyipic.com"]
            + [f"pic{i}.iqiyipic.com" for i in range(10)]
        )
        for domain in domains:
            if domain not in settings.SECURITY_IMAGE_DOMAINS:
                settings.SECURITY_IMAGE_DOMAINS.append(domain)

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
            mediainfo = to_media(item, mtype)
            try:
                self._fill_tmdb_info_sync(mediainfo, MediaType.TV if mtype == "tv" else MediaType.MOVIE)
            except Exception as err:
                logger.warning(f"爱奇艺探索补全列表 TMDB 信息失败: {err}")
            self._remember_media(media_id, mediainfo)
            medias.append(mediainfo)
            if len(medias) >= max(int(count or 10), 1):
                break
        # 探索列表返回前把条目缓存持久化，保证点击详情时即使进程重启/插件重载也能识别
        self._save_cache_to_disk()
        return medias

    @eventmanager.register(ChainEventType.MediaRecognizeConvert)
    def media_recognize_convert(self, event: Event) -> None:
        """
        兼容旧的 iqiyi:<albumId> 详情/搜索链接，命中缓存时转换为 MoviePilot 标准 TMDB ID。
        """
        if not self._enabled:
            return
        event_data: MediaRecognizeConvertEventData = event.event_data
        if not event_data or event_data.convert_type != "themoviedb":
            return
        mediaid = str(event_data.mediaid or "")
        if not mediaid.startswith("iqiyi:"):
            return
        cached = self._get_cached_media(mediaid[6:])
        if not cached or not cached.tmdb_id:
            return
        event_data.media_dict = {"id": cached.tmdb_id}

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

    def get_module(self) -> Dict[str, Any]:
        """
        注册识别模块，让主程序可识别 iqiyi 来源的媒体详情。
        """
        return {
            "recognize_media": self.recognize_media,
            "async_recognize_media": self.async_recognize_media,
        }

    def recognize_media(
            self,
            meta: MetaBase = None,
            mtype: MediaType = None,
            source: str = None,
            mediaid: str = None,
            **kwargs,
    ) -> Optional[schemas.MediaInfo]:
        """
        识别 iqiyi 来源媒体信息：命中探索缓存时返回基础媒体信息。
        """
        if not self._enabled:
            return None
        if kwargs.get("tmdbid") or kwargs.get("doubanid") or kwargs.get("bangumiid") or kwargs.get("anilistid"):
            return None
        if source != "iqiyi" or not mediaid:
            return None
        cached = self._get_cached_media(str(mediaid))
        if cached:
            return cached.model_copy(deep=True)
        return self._build_fallback_media(meta=meta, mtype=mtype, mediaid=str(mediaid), **kwargs)

    async def async_recognize_media(
            self,
            meta: MetaBase = None,
            mtype: MediaType = None,
            source: str = None,
            mediaid: str = None,
            **kwargs,
    ) -> Optional[schemas.MediaInfo]:
        """
        识别 iqiyi 来源媒体信息：命中探索缓存时返回并尽力补全 TMDB 信息。
        """
        if not self._enabled:
            return None
        if kwargs.get("tmdbid") or kwargs.get("doubanid") or kwargs.get("bangumiid") or kwargs.get("anilistid"):
            return None
        if source != "iqiyi" or not mediaid:
            return None
        cached = self._get_cached_media(str(mediaid))
        if cached:
            mediainfo = cached.model_copy(deep=True)
        else:
            mediainfo = self._build_fallback_media(meta=meta, mtype=mtype, mediaid=str(mediaid), **kwargs)
        if not mediainfo:
            return None
        await self._fill_tmdb_info(mediainfo, mtype)
        return mediainfo

    @staticmethod
    def _build_fallback_media(
            meta: MetaBase = None,
            mtype: MediaType = None,
            mediaid: str = None,
            **kwargs,
    ) -> Optional[schemas.MediaInfo]:
        """
        缓存未命中时，用详情页传入的标题/年份/类型构造基础媒体信息，避免直开或刷新详情页返回空对象。
        """
        title = str(
            kwargs.get("title")
            or getattr(meta, "title", None)
            or getattr(meta, "name", None)
            or ""
        ).strip()
        if not title:
            return None
        year = str(kwargs.get("year") or getattr(meta, "year", None) or "").strip()
        media_type = mtype or getattr(meta, "type", None) or MediaType.TV
        return schemas.MediaInfo(
            type=media_type,
            title=title,
            year=year,
            title_year=f"{title} ({year})" if year else title,
            mediaid_prefix="iqiyi",
            media_id=mediaid,
        )

    async def _fill_tmdb_info(self, mediainfo: schemas.MediaInfo, mtype: MediaType = None) -> None:
        """
        按标题与年份匹配 TMDB，补全后把详情入口升级为 tmdb:<id>。
        """
        if mediainfo.tmdb_id or not mediainfo.title:
            return
        try:
            chain = MediaChain()
            meta = self._build_tmdb_meta(mediainfo, mtype)
            info = await chain.async_recognize_by_meta(meta, obtain_images=False)
            self._apply_tmdb_info(mediainfo, info)
        except Exception as err:
            logger.warning(f"爱奇艺探索补全 TMDB 信息失败: {err}")

    def _fill_tmdb_info_sync(self, mediainfo: schemas.MediaInfo, mtype: MediaType = None) -> None:
        """
        同步接口返回探索列表前尽力补全 TMDB，让前端卡片直接进入 TMDB 详情页。
        """
        if mediainfo.tmdb_id or not mediainfo.title:
            return
        try:
            chain = MediaChain()
            meta = self._build_tmdb_meta(mediainfo, mtype)
            info = chain.recognize_by_meta(meta, obtain_images=False)
            self._apply_tmdb_info(mediainfo, info)
        except Exception as err:
            logger.warning(f"爱奇艺探索补全 TMDB 信息失败: {err}")

    @staticmethod
    def _build_tmdb_meta(mediainfo: schemas.MediaInfo, mtype: MediaType = None) -> MetaInfo:
        meta = MetaInfo(title=mediainfo.title)
        if mediainfo.year:
            meta.year = mediainfo.year
        if mtype:
            meta.type = mtype
        return meta

    @staticmethod
    def _apply_tmdb_info(mediainfo: schemas.MediaInfo, info: Optional[schemas.MediaInfo]) -> None:
        if not info or not info.tmdb_id:
            return
        mediainfo.tmdb_id = info.tmdb_id
        mediainfo.mediaid_prefix = "tmdb"
        mediainfo.media_id = str(info.tmdb_id)
        mediainfo.vote_average = info.vote_average or mediainfo.vote_average
        mediainfo.genres = info.genres or mediainfo.genres
        mediainfo.overview = info.overview or mediainfo.overview
        mediainfo.poster_path = info.poster_path or mediainfo.poster_path
        mediainfo.backdrop_path = info.backdrop_path or mediainfo.backdrop_path

    def _remember_media(self, media_id: str, mediainfo: schemas.MediaInfo) -> None:
        """
        缓存探索条目，供详情识别使用；带 TTL 与数量上限。
        """
        if not media_id:
            return
        now = time.time()
        cache = self._media_cache
        cache[str(media_id)] = (now, mediainfo)
        expired = [key for key, (ts, _) in cache.items() if now - ts > self._MEDIA_CACHE_TTL]
        for key in expired:
            cache.pop(key, None)
        if len(cache) > self._MEDIA_CACHE_MAX:
            ordered = sorted(cache.items(), key=lambda kv: kv[1][0])
            for key, _ in ordered[: len(cache) - self._MEDIA_CACHE_MAX]:
                cache.pop(key, None)

    def _save_cache_to_disk(self) -> None:
        """
        将探索条目缓存持久化到插件数据，进程重启/插件重载后仍可恢复。
        """
        try:
            data = {
                str(media_id): {"ts": ts, "media": mediainfo.model_dump()}
                for media_id, (ts, mediainfo) in self._media_cache.items()
            }
            self.save_data(self._MEDIA_CACHE_DATA_KEY, data)
        except Exception as err:
            logger.warning(f"爱奇艺探索持久化探索缓存失败: {err}")

    def _load_cache_from_disk(self) -> Dict[str, Tuple[float, schemas.MediaInfo]]:
        """
        从插件数据恢复未过期的探索条目缓存。
        """
        try:
            raw = self.get_data(self._MEDIA_CACHE_DATA_KEY) or {}
            now = time.time()
            restored: Dict[str, Tuple[float, schemas.MediaInfo]] = {}
            for media_id, item in raw.items():
                try:
                    ts = float(item.get("ts") or 0)
                    if now - ts > self._MEDIA_CACHE_TTL:
                        continue
                    media = schemas.MediaInfo(**item["media"])
                    restored[str(media_id)] = (ts, media)
                except Exception:
                    continue
            return restored
        except Exception as err:
            logger.warning(f"爱奇艺探索加载探索缓存失败: {err}")
            return {}

    def _get_cached_media(self, media_id: str) -> Optional[schemas.MediaInfo]:
        """
        读取未过期的探索条目缓存；内存未命中时惰性加载持久化缓存兜底。
        """
        item = self._media_cache.get(media_id)
        if not item and not self._disk_cache_loaded:
            self._media_cache.update(self._load_cache_from_disk())
            self._disk_cache_loaded = True
            item = self._media_cache.get(media_id)
        if not item:
            return None
        ts, mediainfo = item
        if time.time() - ts > self._MEDIA_CACHE_TTL:
            self._media_cache.pop(media_id, None)
            return None
        return mediainfo
