from typing import Any, Dict, List, Tuple

from app import schemas
from app.core.config import settings
from app.core.event import Event, eventmanager
from app.plugins import _PluginBase
from app.schemas import DiscoverSourceEventData
from app.schemas.types import ChainEventType

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
    plugin_version = "1.0.38"
    plugin_label = "探索"
    plugin_author = "qsxazcv"
    author_url = "https://github.com/qsxazcv/MoviePilot-Plugins"
    plugin_config_prefix = "iqiyidiscover_"
    plugin_order = 98
    auth_level = 1

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
