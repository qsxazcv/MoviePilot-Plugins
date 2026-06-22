"""爱奇艺探索插件测试。"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_FILE = REPO_ROOT / "plugins.v2" / "iqiyidiscover" / "__init__.py"
TV_SHOW = "{{mtype == 'tv'}}"
TV_DEFAULT_SUBGENRE_SHOW = "{{mtype == 'tv' && !genre}}"
TV_COSTUME_GENRE = "three_category_id_v2=2289882683101933"
TV_WAR_GENRE = "three_category_id_v2=4705204050526533"
SHORT_DRAMA_SHOW = "{{mtype == 'short_drama'}}"
MOVIE_SHOW = "{{mtype == 'movie'}}"
MOVIE_DEFAULT_SUBGENRE_SHOW = "{{mtype == 'movie' && !genre}}"
MOVIE_COMEDY_GENRE = "three_category_id_v2=3842875764248933"
VARIETY_SHOW = "{{mtype == 'variety'}}"
VARIETY_DEFAULT_SUBGENRE_SHOW = "{{mtype == 'variety' && !genre}}"
VARIETY_REALITY_GENRE = "three_category_id_v2=7220796148913633"
ANIME_SHOW = "{{mtype == 'anime'}}"
ANIME_DEFAULT_SUBGENRE_SHOW = "{{mtype == 'anime' && !genre}}"
ANIME_FANTASY_GENRE = "three_category_id_v2=2951669507454533"
CHILDREN_SHOW = "{{mtype == 'children'}}"
COMIC_SHOW = "{{mtype == 'comic'}}"
DOCUMENTARY_SHOW = "{{mtype == 'documentary'}}"
DOCUMENTARY_DEFAULT_SUBGENRE_SHOW = "{{mtype == 'documentary' && !genre}}"
DOCUMENTARY_NATURE_GENRE = "three_category_id_v2=7300210567835933"
KNOWLEDGE_SHOW = "{{mtype == 'knowledge'}}"
KNOWLEDGE_PARENTING_GENRE = "three_category_id_v2=3082422540629633"
ADVANCED_FILTER_MODELS = {
    "subgenre",
    "age_detail",
    "setting",
    "background",
    "spec",
    "award",
    "theater",
    "actor",
    "producer",
    "person",
    "style",
    "star",
    "serial",
    "version",
    "screen",
    "series",
    "language",
    "duration",
    "grade",
    "subject",
}


def tv_subgenre_show(genre: str) -> str:
    """返回电视剧指定类型对应的细选显示条件。"""
    return subgenre_show("tv", genre)


def subgenre_show(mtype: str, genre: str) -> str:
    """返回指定频道类型对应的细选显示条件。"""
    return "{{mtype == '" + mtype + "' && genre == '" + genre + "'}}"


def expanded_show(show: str) -> str:
    """返回指定 show 条件展开高级筛选后的显示条件。"""
    return "{{" + show.removeprefix("{{").removesuffix("}}").strip() + " && filter_expand == '1'}}"


def chip_texts_for(ui: list, label: str, show: str | None = None) -> list[str]:
    """返回指定筛选行的 VChip 文案。"""
    for row in ui:
        props = row.get("props") or {}
        if show is not None and props.get("show") != show:
            continue
        content = row.get("content") or []
        if not content:
            continue
        row_label = content[0]["content"][0]["text"]
        if row_label == label:
            return [chip["text"] for chip in content[1]["content"]]
    raise AssertionError(f"未找到筛选行: {label}")


def chip_values_for(ui: list, label: str, show: str | None = None) -> list[str]:
    """返回指定筛选行的 VChip value。"""
    for row in ui:
        props = row.get("props") or {}
        if show is not None and props.get("show") != show:
            continue
        content = row.get("content") or []
        if not content:
            continue
        row_label = content[0]["content"][0]["text"]
        if row_label == label:
            return [chip["props"]["value"] for chip in content[1]["content"]]
    raise AssertionError(f"未找到筛选行: {label}")


def actual_rows_for(ui: list, show: str) -> list[str]:
    """返回指定频道的筛选行文案。"""
    return [
        row["content"][0]["content"][0]["text"]
        for row in ui
        if (row.get("props") or {}).get("show") == show
        and ((row.get("content") or [{}])[-1].get("props") or {}).get("model") != "filter_expand"
    ]


def components_named(node: object, component: str) -> list[dict]:
    """递归返回指定组件节点。"""
    found = []
    if isinstance(node, dict):
        if node.get("component") == component:
            found.append(node)
        for child in node.get("content") or []:
            found.extend(components_named(child, component))
    elif isinstance(node, list):
        for child in node:
            found.extend(components_named(child, component))
    return found


def expected_rows_for(module, channel: str) -> list[str]:
    """返回指定频道默认收起时应直接显示的筛选行文案。"""
    return [
        group["label"]
        for group in module.FILTER_GROUPS[channel]
        if not group.get("show") and group["model"] not in ADVANCED_FILTER_MODELS
    ] + ["排序"]


def filter_items_for(module, channel: str, model: str) -> dict:
    """按筛选模型返回指定频道的筛选项。"""
    for group in module.FILTER_GROUPS[channel]:
        if group["model"] == model:
            return group["items"]
    raise AssertionError(f"未找到筛选模型: {channel}/{model}")


@dataclass
class FakeMediaInfo:
    """模拟 MoviePilot 媒体信息对象。"""

    type: str
    title: str
    year: str
    title_year: str
    mediaid_prefix: str
    media_id: str
    poster_path: str
    overview: str = ""
    vote_average: float = 0


@dataclass
class FakeDiscoverMediaSource:
    """模拟 MoviePilot 探索数据源对象。"""

    name: str
    mediaid_prefix: str
    api_path: str
    filter_params: dict
    filter_ui: list
    depends: dict


class FakeResponse:
    """模拟 requests 响应对象。"""

    def __init__(self, payload: dict) -> None:
        """保存待返回的 JSON 数据。"""
        self._payload = payload

    def raise_for_status(self) -> None:
        """模拟成功响应。"""
        return None

    def json(self) -> dict:
        """返回响应 JSON。"""
        return self._payload


class FakeLogger:
    """模拟 MoviePilot 日志对象。"""

    def warning(self, *_args, **_kwargs) -> None:
        """记录 warning 日志。"""
        return None

    def error(self, *_args, **_kwargs) -> None:
        """记录 error 日志。"""
        return None

    def debug(self, *_args, **_kwargs) -> None:
        """记录 debug 日志。"""
        return None


class FakePluginBase:
    """模拟 MoviePilot 插件基类。"""


class FakeSettings:
    """模拟 MoviePilot 配置对象。"""

    API_TOKEN = "test-token"
    SECURITY_IMAGE_DOMAINS: list[str] = []


class FakeEventManager:
    """模拟事件管理器。"""

    def register(self, _event_type: str):
        """返回保持原函数不变的注册装饰器。"""

        def decorator(func):
            """返回被装饰的函数。"""
            return func

        return decorator


class FakeEvent:
    """模拟 MoviePilot 事件对象。"""

    def __init__(self, event_data) -> None:
        """保存事件数据。"""
        self.event_data = event_data


class FakeDiscoverSourceEventData:
    """模拟探索数据源事件数据。"""

    def __init__(self, extra_sources=None) -> None:
        """保存额外数据源列表。"""
        self.extra_sources = extra_sources


class FakeChainEventType:
    """模拟链式事件类型。"""

    DiscoverSource = "DiscoverSource"


def fake_cached(**_kwargs):
    """返回保持原函数不变的缓存装饰器。"""

    def decorator(func):
        """返回被装饰的函数。"""
        return func

    return decorator


def load_plugin_module():
    """加载带有 MoviePilot 依赖桩的插件模块。"""
    fake_settings = FakeSettings()
    fake_settings.SECURITY_IMAGE_DOMAINS = []

    app_module = types.ModuleType("app")
    schemas_module = types.ModuleType("app.schemas")
    schemas_module.MediaInfo = FakeMediaInfo
    schemas_module.DiscoverMediaSource = FakeDiscoverMediaSource
    schemas_module.DiscoverSourceEventData = FakeDiscoverSourceEventData
    app_module.schemas = schemas_module

    cache_module = types.ModuleType("app.core.cache")
    cache_module.cached = fake_cached

    config_module = types.ModuleType("app.core.config")
    config_module.settings = fake_settings

    event_module = types.ModuleType("app.core.event")
    event_module.Event = FakeEvent
    event_module.eventmanager = FakeEventManager()

    log_module = types.ModuleType("app.log")
    log_module.logger = FakeLogger()

    plugins_module = types.ModuleType("app.plugins")
    plugins_module._PluginBase = FakePluginBase

    types_module = types.ModuleType("app.schemas.types")
    types_module.ChainEventType = FakeChainEventType

    requests_module = types.ModuleType("requests")
    requests_module.get = lambda *_args, **_kwargs: None

    fake_modules = {
        "app": app_module,
        "app.schemas": schemas_module,
        "app.core": types.ModuleType("app.core"),
        "app.core.cache": cache_module,
        "app.core.config": config_module,
        "app.core.event": event_module,
        "app.log": log_module,
        "app.plugins": plugins_module,
        "app.schemas.types": types_module,
        "requests": requests_module,
    }

    with patch.dict(sys.modules, fake_modules):
        sys.modules.pop("iqiyidiscover_under_test", None)
        spec = importlib.util.spec_from_file_location(
            "iqiyidiscover_under_test",
            PLUGIN_FILE,
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["iqiyidiscover_under_test"] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return module, fake_settings


class IqiyiDiscoverTest(unittest.TestCase):
    """爱奇艺探索插件测试用例。"""

    def test_iqiyi_discover_converts_response_items(self) -> None:
        """接口数据应转换为去重后的 MediaInfo 列表。"""
        module, _settings = load_plugin_module()

        payload = {
            "code": "A00000",
            "data": {
                "list": [
                    {
                        "albumId": 1001,
                        "name": "问心2",
                        "imageUrl": "http://pic5.iqiyipic.com/image/poster.jpg",
                        "period": "2026-06-18",
                        "description": "医道切磋",
                        "score": 8.6,
                    },
                    {
                        "albumId": 1001,
                        "name": "问心2",
                        "imageUrl": "http://pic5.iqiyipic.com/image/poster.jpg",
                        "period": "2026-06-18",
                    },
                    {
                        "albumId": 1002,
                        "title": "南部档案",
                        "poster": "//pic0.iqiyipic.com/image/second.jpg",
                        "publishTime": "2026-06-16",
                    },
                ]
            },
        }

        def fake_get(_url, **_kwargs):
            """返回固定的爱奇艺接口数据。"""
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(mtype="tv", mode="24", page=1, count=10)

        self.assertEqual([media.title for media in medias], ["问心2", "南部档案"])
        self.assertEqual(medias[0].type, "电视剧")
        self.assertEqual(medias[0].year, "2026")
        self.assertEqual(medias[0].mediaid_prefix, "iqiyi")
        self.assertEqual(medias[0].media_id, "1001")
        self.assertEqual(
            medias[0].poster_path,
            "https://pic5.iqiyipic.com/image/poster.jpg",
        )
        self.assertEqual(
            medias[1].poster_path,
            "https://pic0.iqiyipic.com/image/second.jpg",
        )

    def test_iqiyi_discover_uses_moviepilot_standard_media_types(self) -> None:
        """非电影频道也要返回 MoviePilot 可识别的标准媒体类型。"""
        module, _settings = load_plugin_module()

        payload = {
            "code": "A00000",
            "data": {
                "list": [
                    {
                        "albumId": 1001,
                        "name": "测试片单",
                        "imageUrl": "http://pic5.iqiyipic.com/image/poster.jpg",
                        "period": "2026-06-18",
                    },
                ]
            },
        }

        expected_types = {
            "tv": "电视剧",
            "short_drama": "电视剧",
            "movie": "电影",
            "variety": "电视剧",
            "anime": "电视剧",
            "children": "电视剧",
            "comic": "电视剧",
            "documentary": "电视剧",
            "knowledge": "电视剧",
        }

        def fake_get(_url, **_kwargs):
            """返回固定的爱奇艺接口数据。"""
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            for mtype, expected_type in expected_types.items():
                with self.subTest(mtype=mtype):
                    medias = plugin.iqiyi_discover(mtype=mtype, page=1, count=10)
                    self.assertEqual(medias[0].type, expected_type)

    def test_discover_source_appends_iqiyi_source_when_enabled(self) -> None:
        """插件启用后应向探索页追加爱奇艺数据源。"""
        module, settings = load_plugin_module()
        plugin = module.IqiyiDiscover()
        plugin.init_plugin({"enabled": True})
        event_data = FakeDiscoverSourceEventData(extra_sources=["existing"])
        event = FakeEvent(event_data)

        plugin.discover_source(event)

        self.assertEqual(len(event_data.extra_sources), 2)
        source = event_data.extra_sources[1]
        self.assertEqual(source.name, "爱奇艺")
        self.assertEqual(source.mediaid_prefix, "iqiyidiscover")
        self.assertEqual(
            source.filter_params,
            {
                "mtype": "tv",
                "mode": "11",
                "filter_expand": "0",
                "region": None,
                "genre": None,
                "subgenre": None,
                "age": None,
                "age_detail": None,
                "audience": None,
                "rank": None,
                "spec": None,
                "award": None,
                "hall": None,
                "theater": None,
                "actor": None,
                "recommend": None,
                "setting": None,
                "background": None,
                "style": None,
                "star": None,
                "serial": None,
                "version": None,
                "screen": None,
                "series": None,
                "language": None,
                "producer": None,
                "person": None,
                "grade": None,
                "subject": None,
                "duration": None,
                "year": None,
                "is_purchase": None,
            },
        )
        self.assertEqual(
            source.depends,
            {
                "region": ["mtype"],
                "filter_expand": ["mtype"],
                "genre": ["mtype"],
                "subgenre": ["mtype", "genre", "filter_expand"],
                "age": ["mtype"],
                "age_detail": ["mtype", "filter_expand"],
                "audience": ["mtype"],
                "rank": ["mtype"],
                "spec": ["mtype", "filter_expand"],
                "award": ["mtype", "filter_expand"],
                "hall": ["mtype"],
                "theater": ["mtype", "filter_expand"],
                "actor": ["mtype", "filter_expand"],
                "recommend": ["mtype"],
                "setting": ["mtype", "filter_expand"],
                "background": ["mtype", "filter_expand"],
                "style": ["mtype", "filter_expand"],
                "star": ["mtype", "filter_expand"],
                "serial": ["mtype", "filter_expand"],
                "version": ["mtype", "filter_expand"],
                "screen": ["mtype", "filter_expand"],
                "series": ["mtype", "filter_expand"],
                "language": ["mtype", "filter_expand"],
                "producer": ["mtype", "filter_expand"],
                "person": ["mtype", "filter_expand"],
                "grade": ["mtype", "filter_expand"],
                "subject": ["mtype", "filter_expand"],
                "duration": ["mtype", "filter_expand"],
                "year": ["mtype"],
                "is_purchase": ["mtype"],
            },
        )
        self.assertNotIn("mode", source.depends)
        self.assertEqual(
            source.api_path,
            f"plugin/IqiyiDiscover/iqiyi_discover?apikey={settings.API_TOKEN}",
        )

    def test_filter_ui_exposes_extended_iqiyi_filters(self) -> None:
        """探索页筛选 UI 应提供地区、类型、年份、资费等更多维度。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()
        chip_group_models = []

        def collect_models(node):
            """递归收集 VChipGroup 的 model。"""
            if isinstance(node, dict):
                props = node.get("props") or {}
                if node.get("component") == "VChipGroup" and "model" in props:
                    chip_group_models.append(props["model"])
                collect_models(node.get("content"))
            elif isinstance(node, list):
                for child in node:
                    collect_models(child)

        collect_models(ui)

        self.assertIn("mtype", chip_group_models)
        self.assertIn("mode", chip_group_models)
        self.assertIn("region", chip_group_models)
        self.assertIn("genre", chip_group_models)
        self.assertIn("year", chip_group_models)
        self.assertIn("is_purchase", chip_group_models)
        self.assertGreaterEqual(len(ui), 6)

    def test_filter_ui_exposes_iqiyi_sort_modes(self) -> None:
        """探索页排序应只提供官网同款的最热、最新、高分。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()
        sort_group = next(
            row["content"][1]
            for row in ui
            if row["content"][1]["props"].get("model") == "mode"
        )
        sort_modes = {
            chip["props"]["value"]: chip["text"]
            for chip in sort_group["content"]
        }

        self.assertEqual(sort_modes, {"11": "最热", "4": "最新", "8": "高分"})
        self.assertNotIn("24", sort_modes)

    def test_filter_ui_uses_normal_size_chips_and_expandable_advanced_rows(self) -> None:
        """筛选芯片应恢复普通尺寸，并用展开/收起控制高级筛选。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()
        chips = components_named(ui, "VChip")

        self.assertGreater(len(chips), 0)
        for chip in chips:
            props = chip.get("props") or {}
            self.assertNotIn("density", props)
            self.assertNotIn("size", props)

        tv_collapsed_rows = actual_rows_for(ui, TV_SHOW)
        self.assertIn("推荐", tv_collapsed_rows)
        self.assertIn("排序", tv_collapsed_rows)
        self.assertNotIn("规格", tv_collapsed_rows)
        self.assertNotIn("奖项", tv_collapsed_rows)
        self.assertNotIn("剧场", tv_collapsed_rows)
        self.assertNotIn("演员", tv_collapsed_rows)
        self.assertEqual(chip_texts_for(ui, "规格", expanded_show(TV_SHOW)), ["自制", "独播"])

        toggle_groups = [
            node
            for node in components_named(ui, "VChipGroup")
            if (node.get("props") or {}).get("model") == "filter_expand"
        ]
        self.assertGreaterEqual(len(toggle_groups), 1)
        for group in toggle_groups:
            self.assertEqual([chip["text"] for chip in group.get("content", [])], ["展开", "收起"])
        toggle_rows = [
            row
            for row in ui
            if (row.get("content") or [{}])[-1] in toggle_groups
        ]
        self.assertIn(TV_SHOW, [(row.get("props") or {}).get("show") for row in toggle_rows])
        self.assertTrue(all("filter_expand" not in (row.get("props") or {}).get("show", "") for row in toggle_rows))

    def test_tv_filter_ui_matches_screenshot_order(self) -> None:
        """电视剧筛选应严格匹配截图中的行、文案顺序，排序放在最底部。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()

        self.assertEqual(
            chip_texts_for(ui, "类型", TV_SHOW),
            [
                "古装",
                "战争",
                "谍战",
                "爱情",
                "罪案",
                "悬疑",
                "家庭",
                "军旅",
                "喜剧",
                "都市",
                "武侠",
                "言情",
                "偶像",
                "青春",
                "农村",
                "穿越",
                "奇幻",
                "历史",
                "年代",
                "科幻",
                "生活",
                "剧情",
                "励志",
                "婚姻",
                "警匪",
                "犯罪",
                "推理",
                "商战",
                "宫廷",
                "仙侠",
                "神话",
                "动作",
                "复仇",
                "惊悚",
                "其他",
            ],
        )
        default_subgenre_texts = chip_texts_for(ui, "细选", expanded_show(TV_DEFAULT_SUBGENRE_SHOW))
        self.assertEqual(default_subgenre_texts[:6], ["全部", "古偶甜宠", "古装探案", "奇幻冒险", "婚姻生活", "熟龄浪漫"])
        self.assertIn("刑侦破案", default_subgenre_texts)
        self.assertEqual(
            chip_texts_for(ui, "细选", expanded_show(tv_subgenre_show(TV_COSTUME_GENRE))),
            [
                "全部",
                "古装爱情",
                "古装喜剧",
                "古偶甜宠",
                "古装探案",
                "古装神话",
                "江湖恩怨",
                "东方玄幻",
                "仙侠玄幻",
                "传统武侠",
                "甜虐爱情",
                "历史演义",
                "女扮男装",
                "前世今生",
                "童年神剧",
            ],
        )
        self.assertEqual(
            chip_texts_for(ui, "细选", expanded_show(tv_subgenre_show(TV_WAR_GENRE))),
            [
                "全部",
                "革命抗战",
                "战争传奇",
                "抗日战争",
                "反特谍战",
                "个人成长",
                "传奇变革",
                "民国传奇",
                "乱世情缘",
                "剿匪",
            ],
        )
        self.assertEqual(
            chip_texts_for(ui, "地区", TV_SHOW),
            ["内地", "中国香港", "中国台湾", "美国", "韩国", "泰国", "日本", "英国", "其他"],
        )
        self.assertEqual(
            chip_texts_for(ui, "时间", TV_SHOW),
            ["即将上线", "2026", "2025", "2024", "2023", "2022", "2021", "2020", "10年代", "00年代", "90年代", "80年代"],
        )
        self.assertEqual(
            chip_texts_for(ui, "资费", TV_SHOW),
            ["近期转免", "免费", "限免", "VIP"],
        )
        self.assertEqual(
            chip_texts_for(ui, "殿堂", TV_SHOW),
            ["荣誉殿堂", "国民殿堂", "人气殿堂", "佳片殿堂"],
        )
        self.assertEqual(
            chip_texts_for(ui, "推荐", TV_SHOW),
            ["豆瓣高分", "热度破10000", "评论破1000万", "弹幕破1000万"],
        )
        self.assertEqual(chip_texts_for(ui, "排序", TV_SHOW), ["最热", "最新", "高分"])

    def test_other_type_filters_use_official_linked_subgenres(self) -> None:
        """其他频道的类型细选应按官方 list_tag 随类型联动。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()

        self.assertEqual(
            chip_texts_for(ui, "细选", expanded_show(MOVIE_DEFAULT_SUBGENRE_SHOW))[:8],
            ["全部", "奇幻喜剧", "古装探案", "科幻灾难", "校园喜剧", "悬疑犯罪", "动作战争", "仙侠爱情"],
        )
        self.assertEqual(
            chip_texts_for(ui, "细选", expanded_show(subgenre_show("movie", MOVIE_COMEDY_GENRE))),
            [
                "全部",
                "爱情喜剧",
                "古装喜剧",
                "校园喜剧",
                "悬疑喜剧",
                "剧情喜剧",
                "动作喜剧",
                "奇幻喜剧",
                "家庭喜剧",
                "黑色幽默",
                "科幻喜剧",
                "东北喜剧",
            ],
        )
        self.assertEqual(
            chip_texts_for(ui, "细选", expanded_show(VARIETY_DEFAULT_SUBGENRE_SHOW))[:8],
            ["全部", "文化", "亲情关系", "生活", "美食", "元宵", "音乐", "棚内游戏"],
        )
        self.assertEqual(
            chip_texts_for(ui, "细选", expanded_show(subgenre_show("variety", VARIETY_REALITY_GENRE)))[:8],
            ["全部", "游戏节目", "户外游戏", "旅行观光", "青春成长", "音乐", "达人秀场", "音乐竞演"],
        )
        self.assertEqual(
            chip_texts_for(ui, "细选", expanded_show(ANIME_DEFAULT_SUBGENRE_SHOW))[:8],
            ["全部", "少年向", "休闲搞笑", "热血奇幻", "冒险悬疑", "原创", "科幻机甲", "少女向"],
        )
        self.assertEqual(
            chip_texts_for(ui, "细选", expanded_show(subgenre_show("anime", ANIME_FANTASY_GENRE))),
            ["全部", "武侠玄幻", "仙侠派", "热血冒险", "东方玄幻"],
        )
        self.assertEqual(
            chip_texts_for(ui, "细选", expanded_show(DOCUMENTARY_DEFAULT_SUBGENRE_SHOW))[:8],
            ["全部", "品牌", "荒野", "自然风光", "人物传记", "探店", "著名战役", "米其林"],
        )
        self.assertEqual(
            chip_texts_for(ui, "细选", expanded_show(subgenre_show("documentary", DOCUMENTARY_NATURE_GENRE)))[:8],
            ["全部", "野生动物", "地理", "自然风光", "风景", "荒野", "动物生存", "人与自然"],
        )
        self.assertEqual(
            chip_texts_for(ui, "细选", expanded_show(subgenre_show("knowledge", KNOWLEDGE_PARENTING_GENRE))),
            ["全部", "儿童文学 ", "亲子教育", "科普百科", "儿童健康"],
        )

    def test_short_drama_filter_ui_matches_screenshot_order(self) -> None:
        """短剧筛选应严格匹配截图中的行、文案顺序。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()
        self.assertEqual(actual_rows_for(ui, SHORT_DRAMA_SHOW), expected_rows_for(module, "short_drama"))
        self.assertEqual(
            chip_texts_for(ui, "类型", SHORT_DRAMA_SHOW),
            [
                "穿越",
                "逆袭",
                "重生",
                "爱情",
                "玄幻",
                "现代言情",
                "总裁",
                "虐恋",
                "甜宠",
                "神豪",
                "女性成长",
                "古风权谋",
                "家庭伦理",
                "复仇",
                "悬疑推理",
                "古风言情",
                "生活",
                "刑侦",
                "恐怖",
            ],
        )
        self.assertEqual(chip_texts_for(ui, "受众", SHORT_DRAMA_SHOW), ["男频", "女频"])
        self.assertEqual(
            chip_texts_for(ui, "时间", SHORT_DRAMA_SHOW),
            ["即将上线", "2026", "2025", "2024", "2023", "2022", "更早"],
        )
        self.assertEqual(
            chip_texts_for(ui, "资费", SHORT_DRAMA_SHOW),
            ["近期转免", "免费", "VIP", "独播"],
        )
        self.assertEqual(
            chip_texts_for(ui, "设定", expanded_show(SHORT_DRAMA_SHOW)),
            [
                "大女主",
                "马甲",
                "小人物",
                "无敌神医",
                "草根",
                "扮猪吃虎",
                "青梅竹马",
                "打脸虐渣",
                "先婚后爱",
                "都市修仙",
                "闪婚",
                "萌宝",
                "豪门恩怨",
                "强者回归",
                "破镜重圆",
                "欢喜冤家",
                "赘婿逆袭",
                "暗恋成真",
                "亲情",
                "传承觉醒",
            ],
        )
        self.assertEqual(
            chip_texts_for(ui, "背景", expanded_show(SHORT_DRAMA_SHOW)),
            ["古风", "架空", "民国", "乡村", "现代", "星际", "都市"],
        )
        self.assertEqual(chip_texts_for(ui, "排序", SHORT_DRAMA_SHOW), ["最热", "最新"])

    def test_movie_filter_ui_matches_screenshot_order(self) -> None:
        """电影筛选应严格匹配截图中的行、文案顺序。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()
        self.assertEqual(actual_rows_for(ui, MOVIE_SHOW), expected_rows_for(module, "movie"))
        self.assertEqual(
            chip_texts_for(ui, "类型", MOVIE_SHOW),
            [
                "喜剧",
                "动画",
                "动作",
                "爱情",
                "恐怖",
                "战争",
                "惊悚",
                "枪战",
                "科幻",
                "犯罪",
                "悬疑",
                "奇幻",
                "剧情",
                "青春",
                "冒险",
                "家庭",
                "少儿",
                "警匪",
                "历史",
                "武侠",
                "伦理",
                "灾难",
                "传记",
                "运动",
                "音乐",
                "魔幻",
                "歌舞",
                "戏曲",
                "玄幻",
                "悲剧",
                "史诗",
                "西部",
                "其他",
            ],
        )
        self.assertEqual(
            chip_texts_for(ui, "地区", MOVIE_SHOW),
            ["内地", "中国香港", "中国台湾", "美国", "韩国", "日本", "欧洲", "印度", "泰国", "丹麦", "英国", "其他"],
        )
        self.assertEqual(
            chip_texts_for(ui, "时间", MOVIE_SHOW),
            ["即将上线", "2026", "2025", "2024", "2023", "2022", "2021", "2020", "10年代", "00年代", "90年代", "80年代", "70年代", "60年代", "50年代", "更早"],
        )
        self.assertEqual(chip_texts_for(ui, "资费", MOVIE_SHOW), ["近期转免", "免费", "云影院", "VIP"])
        self.assertEqual(
            chip_texts_for(ui, "奖项", expanded_show(MOVIE_SHOW)),
            ["奥斯卡", "金像奖", "金鸡奖", "戛纳电影节", "威尼斯电影节", "柏林电影节", "金球奖", "华表奖"],
        )
        self.assertEqual(
            chip_texts_for(ui, "推荐", MOVIE_SHOW),
            ["高票房", "高分悬疑片", "高分战争片", "高分喜剧片", "冷门佳作", "豆瓣高分"],
        )
        self.assertEqual(chip_texts_for(ui, "排序", MOVIE_SHOW), ["最热", "最新", "高分"])

    def test_variety_filter_ui_matches_screenshot_order_with_star_row(self) -> None:
        """综艺筛选应严格匹配官方接口，并显示明星筛选行。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()
        variety_rows = actual_rows_for(ui, VARIETY_SHOW)
        self.assertEqual(variety_rows, expected_rows_for(module, "variety"))
        self.assertNotIn("明星", variety_rows)
        self.assertIn("明星", actual_rows_for(ui, expanded_show(VARIETY_SHOW)))
        self.assertEqual(
            chip_texts_for(ui, "类型", VARIETY_SHOW),
            ["喜剧", "真人秀", "音乐", "脱口秀", "观察", "访谈", "游戏", "晚会", "曲艺", "竞技", "竞演", "文化", "其他"],
        )
        self.assertEqual(chip_texts_for(ui, "地区", VARIETY_SHOW), ["内地", "港台", "海外"])
        self.assertEqual(
            chip_texts_for(ui, "时间", VARIETY_SHOW),
            ["即将上线", "2026", "2025", "2024", "2023", "2022", "2021", "2020", "10年代", "00年代"],
        )
        self.assertEqual(chip_texts_for(ui, "资费", VARIETY_SHOW), ["近期转免", "免费", "VIP"])
        self.assertEqual(chip_texts_for(ui, "风格", expanded_show(VARIETY_SHOW)), ["搞笑", "烧脑", "合家欢", "治愈", "慢生活"])
        self.assertEqual(
            chip_texts_for(ui, "明星", expanded_show(VARIETY_SHOW)),
            [
                "黄子韬",
                "郑恺",
                "沈腾",
                "白鹿",
                "范丞丞",
                "李晨",
                "沙溢",
                "黄晓明",
                "陈赫",
                "邓超",
                "黄渤",
                "郭麒麟",
                "李荣浩",
                "李诞",
                "李宇春",
                "十个勤天",
                "薛之谦",
                "宁静",
                "万妮达",
                "大张伟",
            ],
        )
        self.assertEqual(chip_texts_for(ui, "排序", VARIETY_SHOW), ["最热", "最新"])

    def test_anime_filter_ui_matches_screenshot_order(self) -> None:
        """动漫筛选应严格匹配截图中的行、文案顺序。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()
        self.assertEqual(actual_rows_for(ui, ANIME_SHOW), expected_rows_for(module, "anime"))
        self.assertEqual(
            chip_texts_for(ui, "类型", ANIME_SHOW),
            ["玄幻", "奇幻", "武侠", "恋爱", "搞笑", "冒险", "热血", "治愈", "科幻", "推理", "竞技", "励志", "机战", "偶像", "其他"],
        )
        self.assertEqual(chip_texts_for(ui, "地区", ANIME_SHOW), ["内地", "日本", "欧美", "其他"])
        self.assertEqual(
            chip_texts_for(ui, "时间", ANIME_SHOW),
            ["即将上线", "2026", "2025", "2024", "2023", "2022", "2021", "2020", "10年代", "00年代", "更早"],
        )
        self.assertEqual(chip_texts_for(ui, "资费", ANIME_SHOW), ["近期转免", "免费", "VIP"])
        self.assertEqual(chip_texts_for(ui, "连载", expanded_show(ANIME_SHOW)), ["连载中", "已完结"])
        self.assertEqual(chip_texts_for(ui, "版本", expanded_show(ANIME_SHOW)), ["动画", "动画电影", "动态漫画"])
        self.assertEqual(chip_texts_for(ui, "排序", ANIME_SHOW), ["最热", "最新"])

    def test_children_filter_ui_matches_screenshot_order(self) -> None:
        """少儿筛选应严格匹配截图中的行、文案顺序。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()
        self.assertEqual(actual_rows_for(ui, CHILDREN_SHOW), expected_rows_for(module, "children"))
        self.assertEqual(chip_texts_for(ui, "年龄", CHILDREN_SHOW), ["0-1岁", "2-3岁", "4-6岁", "7-10岁", "11-14岁"])
        self.assertEqual(
            chip_texts_for(ui, "时间", CHILDREN_SHOW),
            ["即将上线", "2026", "2025", "2024", "2023", "2022", "2021", "2020", "10年代", "00年代"],
        )
        self.assertEqual(chip_texts_for(ui, "资费", CHILDREN_SHOW), ["近期转免", "免费", "VIP"])
        self.assertEqual(
            chip_texts_for(ui, "类型", CHILDREN_SHOW),
            ["看动画", "玩玩具", "听儿歌", "看绘本", "涨知识", "学英语", "识字拼音", "好习惯", "国学", "做手工", "冒险救援", "生活日常", "搞笑", "动物", "公主"],
        )
        self.assertEqual(
            chip_texts_for(ui, "系列", expanded_show(CHILDREN_SHOW)),
            ["小猪佩奇", "汪汪队", "猪猪侠", "喜羊羊与灰太狼", "超级飞侠", "猫和老鼠", "海绵宝宝", "小马宝莉", "迷你特工队", "托马斯", "芭比"],
        )
        self.assertEqual(chip_texts_for(ui, "语种", expanded_show(CHILDREN_SHOW)), ["普通话", "英语"])
        self.assertEqual(chip_texts_for(ui, "排序", CHILDREN_SHOW), ["最热", "最新"])

    def test_comic_filter_ui_matches_screenshot_order(self) -> None:
        """漫剧筛选应严格匹配截图中的行、文案顺序。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()
        self.assertEqual(actual_rows_for(ui, COMIC_SHOW), expected_rows_for(module, "comic"))
        self.assertEqual(
            chip_texts_for(ui, "类型", COMIC_SHOW),
            ["逆袭", "穿越", "大女主", "系统", "玄幻", "搞笑", "废柴", "悬疑", "恋爱", "末日", "战神", "扮猪吃老虎", "修仙", "觉醒", "无敌", "科幻", "开局", "异能"],
        )
        self.assertEqual(chip_texts_for(ui, "受众", COMIC_SHOW), ["男频", "女频", "平衡"])
        self.assertEqual(chip_texts_for(ui, "时间", COMIC_SHOW), ["即将上线", "2026", "2025", "2024", "更早"])
        self.assertEqual(chip_texts_for(ui, "资费", COMIC_SHOW), ["近期转免", "免费", "VIP"])
        self.assertEqual(chip_texts_for(ui, "排序", COMIC_SHOW), ["最热", "最新"])

    def test_documentary_filter_ui_matches_screenshot_order(self) -> None:
        """纪录片筛选应严格匹配截图中的行、文案顺序。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()
        self.assertEqual(actual_rows_for(ui, DOCUMENTARY_SHOW), expected_rows_for(module, "documentary"))
        self.assertEqual(
            chip_texts_for(ui, "类型", DOCUMENTARY_SHOW),
            ["自然", "历史", "人文", "美食", "医疗", "萌宠", "财经", "罪案", "竞技", "灾难", "军事", "探险", "社会", "科技", "旅游", "其他"],
        )
        self.assertEqual(
            chip_texts_for(ui, "出品", expanded_show(DOCUMENTARY_SHOW)),
            ["爱奇艺", "央视", "BBC", "国家地理", "探索频道", "美国历史频道", "朗思文化", "其他"],
        )
        self.assertEqual(chip_texts_for(ui, "地区", DOCUMENTARY_SHOW), ["国内", "国外"])
        self.assertEqual(
            chip_texts_for(ui, "时间", DOCUMENTARY_SHOW),
            ["即将上线", "2026", "2025", "2024", "2023", "2022", "2021", "2020", "10年代", "00年代"],
        )
        self.assertEqual(chip_texts_for(ui, "资费", DOCUMENTARY_SHOW), ["近期转免", "免费", "VIP"])
        self.assertEqual(chip_texts_for(ui, "排序", DOCUMENTARY_SHOW), ["最热", "最新"])

    def test_knowledge_filter_ui_matches_screenshot_order(self) -> None:
        """知识筛选应严格匹配截图中的行、文案顺序。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()
        self.assertEqual(actual_rows_for(ui, KNOWLEDGE_SHOW), expected_rows_for(module, "knowledge"))
        self.assertEqual(
            chip_texts_for(ui, "类型", KNOWLEDGE_SHOW),
            ["亲子", "文史", "中小学", "外语", "运动健身", "艺术", "职场", "财经", "生活", "心理", "互联网", "职业考证", "健康", "大学", "党政"],
        )
        self.assertEqual(
            chip_texts_for(ui, "年级", expanded_show(KNOWLEDGE_SHOW)),
            ["一年级", "二年级", "三年级", "四年级", "五年级", "六年级", "初一", "初二", "初三", "高一", "高二", "高三"],
        )
        self.assertEqual(chip_texts_for(ui, "科目", expanded_show(KNOWLEDGE_SHOW)), ["语文", "数学", "英语"])
        self.assertEqual(chip_texts_for(ui, "资费", KNOWLEDGE_SHOW), ["免费", "付费", "VIP"])
        self.assertEqual(chip_texts_for(ui, "排序", KNOWLEDGE_SHOW), ["最热", "最新"])

    def test_filter_ui_exposes_all_iqiyi_channels_from_screenshots(self) -> None:
        """探索页种类应覆盖截图中的爱奇艺频道。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()
        mtype_group = ui[0]["content"][1]
        channels = {
            chip["props"]["value"]: chip["text"]
            for chip in mtype_group["content"]
        }

        self.assertEqual(
            channels,
            {
                "tv": "电视剧",
                "short_drama": "短剧",
                "movie": "电影",
                "variety": "综艺",
                "anime": "动漫",
                "children": "少儿",
                "comic": "漫剧",
                "documentary": "纪录片",
                "knowledge": "知识",
            },
        )

    def test_filter_ui_exposes_channel_specific_groups_from_screenshots(self) -> None:
        """频道专属筛选应只保留已确认可用的关键维度。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()
        groups_by_show = {}
        for row in ui:
            props = row.get("props") or {}
            show = props.get("show")
            if not show:
                continue
            content = row.get("content") or []
            if len(content) < 2:
                continue
            label = content[0]["content"][0]["text"]
            model = content[1]["props"]["model"]
            if model == "filter_expand":
                continue
            groups_by_show.setdefault(show, {})[label] = model

        shows = {
            "tv": TV_SHOW,
            "short_drama": SHORT_DRAMA_SHOW,
            "movie": MOVIE_SHOW,
            "variety": VARIETY_SHOW,
            "anime": ANIME_SHOW,
            "children": CHILDREN_SHOW,
            "comic": COMIC_SHOW,
            "documentary": DOCUMENTARY_SHOW,
            "knowledge": KNOWLEDGE_SHOW,
        }
        for channel, show in shows.items():
            expected = {
                group["label"]: group["model"]
                for group in module.FILTER_GROUPS[channel]
                if not group.get("show") and group["model"] not in ADVANCED_FILTER_MODELS
            }
            expected["排序"] = "mode"
            self.assertEqual(groups_by_show[show], expected)
            expanded_expected = {
                group["label"]: group["model"]
                for group in module.FILTER_GROUPS[channel]
                if not group.get("show") and group["model"] in ADVANCED_FILTER_MODELS
            }
            if expanded_expected:
                self.assertEqual(groups_by_show[expanded_show(show)], expanded_expected)

        self.assertEqual(groups_by_show[expanded_show(TV_DEFAULT_SUBGENRE_SHOW)]["细选"], "subgenre")
        self.assertEqual(groups_by_show[expanded_show(tv_subgenre_show(TV_COSTUME_GENRE))]["细选"], "subgenre")
        self.assertEqual(groups_by_show[expanded_show(tv_subgenre_show(TV_WAR_GENRE))]["细选"], "subgenre")
        self.assertEqual(groups_by_show[expanded_show(VARIETY_SHOW)]["明星"], "star")

    def test_filter_ui_uses_verified_iqiyi_category_params(self) -> None:
        """筛选 UI 不应继续暴露爱奇艺推荐接口会忽略的旧参数。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()
        values = []

        def collect_values(node):
            """递归收集所有 VChip value。"""
            if isinstance(node, dict):
                props = node.get("props") or {}
                if node.get("component") == "VChip" and "value" in props:
                    values.append(str(props["value"]))
                collect_values(node.get("content"))
            elif isinstance(node, list):
                for child in node:
                    collect_values(child)

        collect_values(ui)
        joined_values = ",".join(values)

        self.assertIn("three_category_id_v2=3842875764248933", joined_values)
        self.assertIn("three_category_id_v2=7300210567835933", joined_values)
        self.assertIn("three_category_id_v2=4748521006302433", joined_values)
        self.assertIn("three_category_id_v2=3082422540629633", joined_values)
        self.assertIn("three_category_id_v2=5853103378585233", joined_values)
        self.assertIn("three_category_id_v2=7111701593626433", joined_values)
        self.assertIn("three_category_id_v2=2289882683101933", joined_values)
        self.assertIn("three_category_id_v2=1009625990172533", joined_values)
        self.assertIn("three_category_id_v2=3839667100858533", joined_values)
        self.assertIn("three_category_id_v2=7621076906916433", joined_values)
        self.assertIn("three_category_id_v2=8052642132978633", joined_values)
        self.assertIn("three_category_id_v2=1466860523361833", joined_values)
        self.assertIn("structure_id=812b38302498d408_2_7", joined_values)
        self.assertIn("is_qiyi_produced=1", joined_values)
        self.assertIn("structure_id=95be70850d6d967f_2_9", joined_values)
        self.assertIn("smart_tag_v2=迷雾剧场", joined_values)
        self.assertIn("smart_tag_v2=张凌赫", joined_values)
        self.assertNotIn("tag_name=", joined_values)
        self.assertEqual(filter_items_for(module, "tv", "genre")["three_category_id_v2=2289882683101933"], "古装")
        self.assertEqual(filter_items_for(module, "tv", "genre")["three_category_id_v2=4705204050526533"], "战争")
        self.assertEqual(filter_items_for(module, "tv", "subgenre")["three_category_id_v2=1009625990172533"], "古偶甜宠")
        self.assertEqual(filter_items_for(module, "tv", "subgenre")["three_category_id_v2=3839667100858533"], "刑侦破案")
        self.assertIn("smart_tag_v2=近期转免", chip_values_for(ui, "资费", TV_SHOW))
        self.assertNotIn("mode=24", chip_values_for(ui, "资费", TV_SHOW))
        self.assertIn("is_purchase=0", chip_values_for(ui, "资费", TV_SHOW))
        self.assertEqual(filter_items_for(module, "tv", "region")["three_category_id_v2=4017747919047533"], "韩国")
        self.assertEqual(filter_items_for(module, "tv", "region")["three_category_id_v2=5724756842953133"], "中国台湾")
        self.assertEqual(
            module.FILTER_GROUPS["knowledge"][0]["items"],
            {
                "three_category_id_v2=3082422540629633": "亲子",
                "three_category_id_v2=4431665496460733": "文史",
                "three_category_id_v2=2183194625357733": "中小学",
                "three_category_id_v2=2442294194164733": "外语",
                "three_category_id_v2=2433470369840033": "运动健身",
                "three_category_id_v2=3706507570139933": "艺术",
                "three_category_id_v2=6382532838067233": "职场",
                "three_category_id_v2=5755239145165733": "财经",
                "three_category_id_v2=5942143787679933": "生活",
                "three_category_id_v2=3930311841648333": "心理",
                "three_category_id_v2=3284568334250033": "互联网",
                "three_category_id_v2=4968314448572033": "职业考证",
                "three_category_id_v2=2229720244524333": "健康",
                "three_category_id_v2=7060362979373733": "大学",
                "three_category_id_v2=6984959389689933": "党政",
            },
        )

    def test_iqiyi_discover_maps_extended_filters_to_api_params(self) -> None:
        """扩展筛选项应映射到爱奇艺推荐接口支持的参数。"""
        module, _settings = load_plugin_module()
        captured = {}

        payload = {
            "code": "A00000",
            "data": {
                "list": [
                    {
                        "albumId": 1003,
                        "name": "家业",
                        "imageUrl": "http://pic5.iqiyipic.com/image/jy.jpg",
                        "period": "2024-01-01",
                    }
                ]
            },
        }

        def fake_get(_url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(
                mtype="tv",
                mode="11",
                region="15",
                genre="24",
                subgenre="three_category_id_v2=1009625990172533",
                year="2024",
                is_purchase="0",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["家业"])
        self.assertEqual(captured["channel_id"], "2")
        self.assertEqual(captured["mode"], "11")
        self.assertEqual(captured["three_category_id"], "15,24")
        self.assertEqual(captured["three_category_id_v2"], "1009625990172533")
        self.assertEqual(captured["market_release_date_level"], "2024")
        self.assertEqual(captured["is_purchase"], "0")

    def test_iqiyi_discover_defaults_to_hottest_sort(self) -> None:
        """不传排序时应默认请求官网最热，而不是旧的综合。"""
        module, _settings = load_plugin_module()
        captured = {}

        payload = {
            "code": "A00000",
            "data": {
                "list": [
                    {
                        "albumId": 1005,
                        "name": "南部档案",
                        "imageUrl": "http://pic5.iqiyipic.com/image/nb.jpg",
                        "period": "2026-06-18",
                    }
                ]
            },
        }

        def fake_get(_url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(mtype="tv", page=1, count=10)

        self.assertEqual([media.title for media in medias], ["南部档案"])
        self.assertEqual(captured["mode"], "11")

    def test_iqiyi_discover_falls_back_to_hottest_for_removed_mode(self) -> None:
        """旧版综合排序参数不应继续影响默认列表顺序。"""
        module, _settings = load_plugin_module()
        captured = {}

        payload = {
            "code": "A00000",
            "data": {
                "list": [
                    {
                        "albumId": 1006,
                        "name": "南部档案",
                        "imageUrl": "http://pic5.iqiyipic.com/image/nb.jpg",
                        "period": "2026-06-18",
                    }
                ]
            },
        }

        def fake_get(_url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(mtype="tv", mode="24", page=1, count=10)

        self.assertEqual([media.title for media in medias], ["南部档案"])
        self.assertEqual(captured["mode"], "11")

    def test_iqiyi_discover_canonicalizes_removed_mode_before_cache(self) -> None:
        """无效排序应先归一再进入缓存请求，避免命中旧综合排序缓存。"""
        module, _settings = load_plugin_module()
        captured = {}

        def fake_request(**kwargs):
            """记录进入缓存请求前的参数。"""
            captured.update(kwargs)
            return [
                {
                    "albumId": 1007,
                    "name": "南部档案",
                    "imageUrl": "http://pic5.iqiyipic.com/image/nb.jpg",
                    "period": "2026-06-18",
                }
            ]

        plugin = module.IqiyiDiscover()
        with patch.object(plugin, "_IqiyiDiscover__request", fake_request):
            medias = plugin.iqiyi_discover(mtype="tv", mode="24", page=1, count=10)

        self.assertEqual([media.title for media in medias], ["南部档案"])
        self.assertEqual(captured["mode"], "11")

    def test_iqiyi_discover_maps_recent_free_to_official_smart_tag(self) -> None:
        """电视剧近期转免应使用新版官方 smart_tag_v2 筛选，而不是旧 mode=24。"""
        module, _settings = load_plugin_module()
        captured = {}

        payload = {
            "code": 0,
            "data": [
                {
                    "album_id": 1009,
                    "title": "绝密较量",
                    "image_url_normal": "http://pic5.iqiyipic.com/image/jm.jpg",
                    "showDate": "2025-01-01",
                }
            ],
        }

        def fake_get(url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured["url"] = url
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(
                mtype="tv",
                mode="11",
                is_purchase="smart_tag_v2=近期转免",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["绝密较量"])
        self.assertEqual(captured["url"], "https://mesh.if.iqiyi.com/portal/videolib/data")
        self.assertEqual(captured["mode"], "11")
        self.assertEqual(captured["smart_tag_v2"], "近期转免")
        self.assertNotIn("is_purchase", captured)

    def test_iqiyi_discover_normalizes_recent_free_smart_tag_value_internally(self) -> None:
        """资费栏近期转免 smart_tag 应映射为源码常量，避免 URL 中文传递差异。"""
        module, _settings = load_plugin_module()
        captured = {}

        def fake_request(**kwargs):
            """记录进入缓存请求前的参数。"""
            captured.update(kwargs)
            return [
                {
                    "albumId": 1011,
                    "name": "绝密较量",
                    "imageUrl": "http://pic5.iqiyipic.com/image/jm.jpg",
                    "period": "2025-01-01",
                }
            ]

        plugin = module.IqiyiDiscover()
        with patch.object(plugin, "_IqiyiDiscover__request", fake_request):
            medias = plugin.iqiyi_discover(
                mtype="tv",
                mode="11",
                is_purchase="smart_tag_v2=garbled",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["绝密较量"])
        self.assertEqual(captured["mode"], "11")
        self.assertEqual(captured["extra_params"], (("smart_tag_v2", "近期转免"),))

    def test_iqiyi_discover_maps_screenshot_filters_to_api_params(self) -> None:
        """截图新增筛选项应转换为爱奇艺接口参数。"""
        module, _settings = load_plugin_module()
        captured = {}

        payload = {
            "code": "A00000",
            "data": {
                "list": [
                    {
                        "albumId": 1004,
                        "name": "烟火藏锋：我为自己加冕",
                        "imageUrl": "http://pic5.iqiyipic.com/image/yh.jpg",
                        "period": "2026-06-18",
                    }
                ]
            },
        }

        def fake_get(_url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(
                mtype="short_drama",
                mode="11",
                year="market_release_date_level=2026",
                is_purchase="charge_control_paymark=1_1_1,is_purchase=1",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["烟火藏锋：我为自己加冕"])
        self.assertEqual(captured["channel_id"], "35")
        self.assertEqual(captured["mode"], "11")
        self.assertNotIn("smart_tag_v2", captured)
        self.assertEqual(captured["market_release_date_level"], "2026")
        self.assertEqual(captured["charge_control_paymark"], "1_1_1")
        self.assertEqual(captured["is_purchase"], "1")

    def test_iqiyi_discover_maps_tv_screenshot_filters_to_api_params(self) -> None:
        """电视剧筛选应走新版片库接口，筛选项不应覆盖显式排序。"""
        module, _settings = load_plugin_module()
        captured = {}

        payload = {
            "code": 0,
            "data": [
                {
                    "album_id": 1008,
                    "title": "雍正王朝",
                    "image_url_normal": "http://pic5.iqiyipic.com/image/yz.jpg",
                    "showDate": "1999-01-01",
                }
            ],
        }

        def fake_get(url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured["url"] = url
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(
                mtype="tv",
                mode="11",
                genre="smart_tag_v2=古装",
                region="smart_tag_v2=美国",
                hall="three_category_id=27850",
                recommend="mode=8",
                is_purchase="charge_control_paymark=1_1_1,is_purchase=1",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["雍正王朝"])
        self.assertEqual(captured["url"], "https://mesh.if.iqiyi.com/portal/videolib/data")
        self.assertEqual(captured["channel_id"], "2")
        self.assertEqual(set(captured["smart_tag_v2"].split(",")), {"古装", "美国"})
        self.assertEqual(captured["three_category_id"], "27850")
        self.assertEqual(captured["mode"], "11")
        self.assertEqual(captured["charge_control_paymark"], "1_1_1")
        self.assertEqual(captured["is_purchase"], "1")
        self.assertNotIn("data_type", captured)
        self.assertNotIn("session", captured)

    def test_iqiyi_discover_maps_movie_screenshot_filters_to_modern_api_params(self) -> None:
        """电影截图筛选应映射为爱奇艺新版片库接口参数。"""
        module, _settings = load_plugin_module()
        captured = {}

        payload = {
            "code": 0,
            "data": [
                {
                    "album_id": 1010,
                    "title": "我的妈耶",
                    "image_url_normal": "http://pic5.iqiyipic.com/image/movie.jpg",
                    "showDate": "2026-06-20",
                }
            ],
        }

        def fake_get(url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured["url"] = url
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(
                mtype="movie",
                mode="11",
                genre="three_category_id_v2=3842875764248933",
                region="three_category_id_v2=8052642132978633",
                year="market_release_date_level=1970-1979",
                is_purchase="is_cloud_cinema=1,is_purchase=1",
                award="structure_id=305de086434c2bad_1_9",
                recommend="structure_id=812b38302498d408_1_7",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["我的妈耶"])
        self.assertEqual(medias[0].poster_path, "https://pic5.iqiyipic.com/image/movie.jpg")
        self.assertEqual(captured["url"], "https://mesh.if.iqiyi.com/portal/videolib/data")
        self.assertEqual(captured["channel_id"], "1")
        self.assertEqual(captured["mode"], "11")
        self.assertEqual(
            set(captured["three_category_id_v2"].split(",")),
            {"3842875764248933", "8052642132978633"},
        )
        self.assertEqual(captured["market_release_date_level"], "1970-1979")
        self.assertEqual(captured["is_cloud_cinema"], "1")
        self.assertEqual(captured["is_purchase"], "1")
        official_filter = json.loads(captured["filter"])
        self.assertEqual(
            set(official_filter["structure_id"].split(",")),
            {"305de086434c2bad_1_9", "812b38302498d408_1_7"},
        )
        self.assertNotIn("structure_id", captured)
        self.assertNotIn("three_category_id", captured)

    def test_iqiyi_discover_maps_variety_screenshot_filters_to_modern_api_params(self) -> None:
        """综艺截图筛选应映射为爱奇艺新版片库接口参数。"""
        module, _settings = load_plugin_module()
        captured = {}

        payload = {
            "code": 0,
            "data": [
                {
                    "album_id": 1012,
                    "title": "天赐的声音第7季",
                    "image_url_normal": "http://pic5.iqiyipic.com/image/variety.jpg",
                    "showDate": "2026-06-20",
                }
            ],
        }

        def fake_get(url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured["url"] = url
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(
                mtype="variety",
                mode="4",
                genre="three_category_id_v2=1733179584798033",
                region="three_category_id_v2=8936628897143933",
                year="market_release_date_level=2026",
                is_purchase="charge_control_paymark=1_1_1,is_purchase=1",
                style="three_category_id_v2=1828637320674233",
                star="smart_tag_v2=黄子韬",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["天赐的声音第7季"])
        self.assertEqual(captured["url"], "https://mesh.if.iqiyi.com/portal/videolib/data")
        self.assertEqual(captured["channel_id"], "6")
        self.assertEqual(captured["mode"], "4")
        self.assertEqual(
            set(captured["three_category_id_v2"].split(",")),
            {"1733179584798033", "8936628897143933", "1828637320674233"},
        )
        self.assertEqual(captured["market_release_date_level"], "2026")
        self.assertEqual(captured["charge_control_paymark"], "1_1_1")
        self.assertEqual(captured["is_purchase"], "1")
        self.assertEqual(captured["smart_tag_v2"], "黄子韬")
        self.assertNotIn("star", captured)

    def test_iqiyi_discover_preserves_variety_overseas_should_region(self) -> None:
        """综艺海外地区应保留官方 should 组合值，避免接口返回空数据。"""
        module, _settings = load_plugin_module()
        captured = {}
        region_items = filter_items_for(module, "variety", "region")
        overseas_region = next(key for key, text in region_items.items() if text == "海外")

        payload = {
            "code": 0,
            "data": [
                {
                    "album_id": 10120,
                    "title": "拜托了冰箱",
                    "image_url_normal": "http://pic5.iqiyipic.com/image/variety-overseas.jpg",
                }
            ],
        }

        def fake_get(url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured["url"] = url
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(
                mtype="variety",
                mode="4",
                region=overseas_region,
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["拜托了冰箱"])
        self.assertEqual(
            captured["three_category_id_v2"],
            "4017747919047533;should,8936628897143933;should",
        )

    def test_iqiyi_discover_maps_anime_screenshot_filters_to_modern_api_params(self) -> None:
        """动漫截图筛选应映射为爱奇艺新版片库接口参数。"""
        module, _settings = load_plugin_module()
        captured = {}

        payload = {
            "code": 0,
            "data": [
                {
                    "album_id": 1013,
                    "title": "航海王",
                    "image_url_normal": "http://pic5.iqiyipic.com/image/anime.jpg",
                    "showDate": "2026-06-20",
                }
            ],
        }

        def fake_get(url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured["url"] = url
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(
                mtype="anime",
                mode="8",
                genre="three_category_id_v2=2951669507454533",
                region="three_category_id_v2=6234934322090433",
                year="market_release_date_level=2026",
                is_purchase="charge_control_paymark=1_1_1,is_purchase=1",
                serial="is_album_finished=0",
                version="three_category_id_v2=2276245863690833",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["航海王"])
        self.assertEqual(captured["url"], "https://mesh.if.iqiyi.com/portal/videolib/data")
        self.assertEqual(captured["channel_id"], "4")
        self.assertEqual(captured["mode"], "11")
        self.assertEqual(
            set(captured["three_category_id_v2"].split(",")),
            {"2951669507454533", "6234934322090433", "2276245863690833"},
        )
        self.assertEqual(captured["market_release_date_level"], "2026")
        self.assertEqual(captured["charge_control_paymark"], "1_1_1")
        self.assertEqual(captured["is_purchase"], "1")
        self.assertEqual(captured["is_album_finished"], "0")
        self.assertNotIn("three_category_id", captured)

    def test_iqiyi_discover_maps_children_screenshot_filters_to_modern_api_params(self) -> None:
        """少儿截图筛选应映射为爱奇艺新版片库接口参数。"""
        module, _settings = load_plugin_module()
        captured = {}

        payload = {
            "code": 0,
            "data": [
                {
                    "album_id": 1014,
                    "title": "小猪佩奇全集",
                    "image_url_normal": "http://pic5.iqiyipic.com/image/children.jpg",
                    "showDate": "2026-06-20",
                }
            ],
        }

        def fake_get(url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured["url"] = url
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(
                mtype="children",
                mode="8",
                age="three_category_id_v2=8422440588768333",
                genre="smart_tag_v2=动画",
                series="smart_tag_v2=小猪佩奇",
                language="smart_tag_v2=普通话",
                year="market_release_date_level=2026",
                is_purchase="charge_control_paymark=1_1_1,is_purchase=1",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["小猪佩奇全集"])
        self.assertEqual(captured["url"], "https://mesh.if.iqiyi.com/portal/videolib/data")
        self.assertEqual(captured["channel_id"], "15")
        self.assertEqual(captured["mode"], "11")
        self.assertEqual(captured["three_category_id_v2"], "8422440588768333")
        self.assertEqual(captured["smart_tag_v2"], "动画,小猪佩奇,普通话")
        self.assertEqual(captured["market_release_date_level"], "2026")
        self.assertEqual(captured["charge_control_paymark"], "1_1_1")
        self.assertEqual(captured["is_purchase"], "1")
        self.assertNotIn("three_category_id", captured)

    def test_iqiyi_discover_maps_comic_screenshot_filters_to_modern_api_params(self) -> None:
        """漫剧截图筛选应映射为爱奇艺新版片库接口参数。"""
        module, _settings = load_plugin_module()
        captured = {}

        payload = {
            "code": 0,
            "data": [
                {
                    "album_id": 1015,
                    "title": "狂守龙疆",
                    "image_url_normal": "http://pic5.iqiyipic.com/image/comic.jpg",
                    "showDate": "2026-06-20",
                }
            ],
        }

        def fake_get(url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured["url"] = url
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(
                mtype="comic",
                mode="8",
                genre="smart_tag_v2=逆袭",
                audience="smart_tag_v2=男频",
                year="market_release_date_level=2026",
                is_purchase="charge_control_paymark=1_1_1,is_purchase=1",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["狂守龙疆"])
        self.assertEqual(captured["url"], "https://mesh.if.iqiyi.com/portal/videolib/data")
        self.assertEqual(captured["channel_id"], "37")
        self.assertEqual(captured["mode"], "11")
        self.assertEqual(captured["smart_tag_v2"], "逆袭,男频")
        self.assertEqual(captured["market_release_date_level"], "2026")
        self.assertEqual(captured["charge_control_paymark"], "1_1_1")
        self.assertEqual(captured["is_purchase"], "1")
        self.assertNotIn("tag_name", captured)
        self.assertNotIn("three_category_id", captured)

    def test_iqiyi_discover_maps_documentary_screenshot_filters_to_modern_api_params(self) -> None:
        """纪录片截图筛选应映射为爱奇艺新版片库接口参数。"""
        module, _settings = load_plugin_module()
        captured = {}

        payload = {
            "code": 0,
            "data": [
                {
                    "album_id": 1016,
                    "title": "地球脉动",
                    "image_url_normal": "http://pic5.iqiyipic.com/image/documentary.jpg",
                    "showDate": "2026-06-20",
                }
            ],
        }

        def fake_get(url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured["url"] = url
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(
                mtype="documentary",
                mode="8",
                genre="three_category_id_v2=7300210567835933",
                producer="three_category_id_v2=1827835154826533",
                region="three_category_id=",
                year="market_release_date_level=2026",
                is_purchase="is_purchase=1",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["地球脉动"])
        self.assertEqual(captured["url"], "https://mesh.if.iqiyi.com/portal/videolib/data")
        self.assertEqual(captured["channel_id"], "3")
        self.assertEqual(captured["mode"], "11")
        self.assertEqual(
            set(captured["three_category_id_v2"].split(",")),
            {"7300210567835933", "1827835154826533"},
        )
        self.assertNotIn("three_category_id", captured)
        self.assertEqual(captured["market_release_date_level"], "2026")
        self.assertEqual(captured["is_purchase"], "1")

    def test_iqiyi_discover_maps_documentary_foreign_region_to_legacy_region_param(self) -> None:
        """纪录片国外地区仍应发送官方可区分的旧地区参数。"""
        module, _settings = load_plugin_module()
        captured = {}

        payload = {
            "code": 0,
            "data": [
                {
                    "album_id": 1017,
                    "title": "地球脉动",
                    "image_url_normal": "http://pic5.iqiyipic.com/image/documentary-foreign.jpg",
                    "showDate": "2026-06-20",
                }
            ],
        }

        def fake_get(url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured["url"] = url
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(
                mtype="documentary",
                region="three_category_id=20324",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["地球脉动"])
        self.assertEqual(captured["url"], "https://mesh.if.iqiyi.com/portal/videolib/data")
        self.assertEqual(captured["channel_id"], "3")
        self.assertEqual(captured["three_category_id"], "20324")

    def test_iqiyi_discover_maps_knowledge_screenshot_filters_to_modern_api_params(self) -> None:
        """知识截图筛选应映射为爱奇艺新版片库接口参数。"""
        module, _settings = load_plugin_module()
        captured = {}

        payload = {
            "code": 0,
            "data": [
                {
                    "album_id": 1017,
                    "title": "小学语文同步课",
                    "image_url_normal": "http://pic5.iqiyipic.com/image/knowledge.jpg",
                    "showDate": "2026-06-20",
                }
            ],
        }

        def fake_get(url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured["url"] = url
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(
                mtype="knowledge",
                mode="8",
                genre="three_category_id_v2=3082422540629633",
                grade="three_category_id_v2=5853103378585233",
                subject="three_category_id_v2=7111701593626433",
                is_purchase="charge_control_support_tvod=1_1_1,is_purchase=1",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["小学语文同步课"])
        self.assertEqual(captured["url"], "https://mesh.if.iqiyi.com/portal/videolib/data")
        self.assertEqual(captured["channel_id"], "12")
        self.assertEqual(captured["mode"], "11")
        self.assertEqual(
            set(captured["three_category_id_v2"].split(",")),
            {"3082422540629633", "5853103378585233", "7111701593626433"},
        )
        self.assertEqual(captured["charge_control_support_tvod"], "1_1_1")
        self.assertEqual(captured["is_purchase"], "1")
        self.assertNotIn("three_category_id", captured)

    def test_iqiyi_discover_maps_short_drama_filters_to_official_smart_tags(self) -> None:
        """短剧截图筛选应使用官方 smart_tag_v2，而不是旧 tag_name。"""
        module, _settings = load_plugin_module()
        captured = {}

        payload = {
            "code": 0,
            "data": [
                {
                    "album_id": 1011,
                    "title": "流放路上我靠锅铲养家",
                    "image_url_normal": "http://pic5.iqiyipic.com/image/short.jpg",
                    "showDate": "2026-06-20",
                }
            ],
        }

        def fake_get(url, **kwargs):
            """记录请求参数并返回固定响应。"""
            captured["url"] = url
            captured.update(kwargs.get("params") or {})
            return FakeResponse(payload)

        with patch.object(module.requests, "get", fake_get):
            plugin = module.IqiyiDiscover()
            medias = plugin.iqiyi_discover(
                mtype="short_drama",
                mode="4",
                genre="smart_tag_v2=穿越",
                audience="smart_tag_v2=男频",
                setting="smart_tag_v2=大女主",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["流放路上我靠锅铲养家"])
        self.assertEqual(captured["url"], "https://mesh.if.iqiyi.com/portal/videolib/data")
        self.assertEqual(captured["channel_id"], "35")
        self.assertEqual(captured["mode"], "4")
        self.assertEqual(captured["smart_tag_v2"], "穿越,男频,大女主")
        self.assertNotIn("tag_name", captured)

    def test_non_sort_filters_do_not_override_selected_sort(self) -> None:
        """非排序筛选项即使包含历史 mode 片段，也不应覆盖底部排序。"""
        module, _settings = load_plugin_module()
        captured = {}

        def fake_request(**kwargs):
            """记录进入缓存请求前的参数。"""
            captured.update(kwargs)
            return [
                {
                    "albumId": 1009,
                    "name": "绝密较量",
                    "imageUrl": "http://pic5.iqiyipic.com/image/jm.jpg",
                    "period": "2025-04-28",
                }
            ]

        plugin = module.IqiyiDiscover()
        with patch.object(plugin, "_IqiyiDiscover__request", fake_request):
            medias = plugin.iqiyi_discover(
                mtype="tv",
                mode="11",
                hall="mode=8",
                recommend="mode=11",
                is_purchase="is_purchase=0,mode=4",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["绝密较量"])
        self.assertEqual(captured["mode"], "11")
        self.assertEqual(captured["is_purchase"], "0")
        self.assertEqual(captured["extra_params"], ())

    def test_tv_hall_and_spec_filters_are_sent_in_official_filter_json(self) -> None:
        """电视剧殿堂叠加自制/独播时应按官网 filter JSON 发送。"""
        module, _settings = load_plugin_module()

        for spec_value, expected_key in [
            ("is_qiyi_produced=1", "is_qiyi_produced"),
            ("is_exclusive=1", "is_exclusive"),
        ]:
            captured = {}

            def fake_request(**kwargs):
                """记录进入缓存请求前的参数。"""
                captured.update(kwargs)
                return [
                    {
                        "albumId": 1010,
                        "name": "低智商犯罪",
                        "imageUrl": "http://pic5.iqiyipic.com/image/dzsfz.jpg",
                        "period": "2025-01-01",
                    }
                ]

            plugin = module.IqiyiDiscover()
            with patch.object(plugin, "_IqiyiDiscover__request", fake_request):
                plugin.iqiyi_discover(
                    mtype="tv",
                    mode="11",
                    hall="smart_tag_v2=荣誉殿堂",
                    spec=spec_value,
                    page=1,
                    count=10,
                )

            extra_params = dict(captured["extra_params"])
            self.assertIn("filter", extra_params)
            official_filter = json.loads(extra_params["filter"])
            self.assertEqual(official_filter["smart_tag_v2"], "荣誉殿堂")
            self.assertEqual(official_filter[expected_key], "1")

    def test_tv_hall_and_award_options_are_sent_in_official_filter_json(self) -> None:
        """电视剧殿堂和奖项所有选项应按官网 filter JSON 发送。"""
        module, _settings = load_plugin_module()
        plugin = module.IqiyiDiscover()

        def fake_request(**kwargs):
            """记录进入缓存请求前的参数。"""
            return [
                {
                    "albumId": 1011,
                    "name": "低智商犯罪",
                    "imageUrl": "http://pic5.iqiyipic.com/image/dzsfz.jpg",
                    "period": "2025-01-01",
                    "__captured": kwargs,
                }
            ]

        for model, expected_key in (("hall", "smart_tag_v2"), ("award", "structure_id")):
            for raw_value in filter_items_for(module, "tv", model):
                captured = {}

                def capture_request(**kwargs):
                    """保存当前筛选请求参数。"""
                    captured.update(kwargs)
                    return fake_request(**kwargs)

                with patch.object(plugin, "_IqiyiDiscover__request", capture_request):
                    plugin.iqiyi_discover(
                        mtype="tv",
                        mode="11",
                        **{model: raw_value},
                        page=1,
                        count=10,
                    )

                key, expected_value = raw_value.split("=", 1)
                self.assertEqual(key, expected_key)
                extra_params = dict(captured["extra_params"])
                self.assertIn("filter", extra_params)
                self.assertNotIn(expected_key, extra_params)
                official_filter = json.loads(extra_params["filter"])
                self.assertEqual(official_filter[expected_key], expected_value)

    def test_movie_award_options_are_sent_in_official_filter_json(self) -> None:
        """电影奖项所有选项应按官网 filter JSON 发送。"""
        module, _settings = load_plugin_module()
        plugin = module.IqiyiDiscover()

        for raw_value in filter_items_for(module, "movie", "award"):
            captured = {}

            def capture_request(**kwargs):
                """保存当前电影奖项请求参数。"""
                captured.update(kwargs)
                return [
                    {
                        "albumId": 1012,
                        "name": "我的妈耶",
                        "imageUrl": "http://pic5.iqiyipic.com/image/movie.jpg",
                        "period": "2025-01-01",
                    }
                ]

            with patch.object(plugin, "_IqiyiDiscover__request", capture_request):
                plugin.iqiyi_discover(
                    mtype="movie",
                    mode="11",
                    award=raw_value,
                    page=1,
                    count=10,
                )

            key, expected_value = raw_value.split("=", 1)
            self.assertEqual(key, "structure_id")
            extra_params = dict(captured["extra_params"])
            self.assertIn("filter", extra_params)
            self.assertNotIn("structure_id", extra_params)
            official_filter = json.loads(extra_params["filter"])
            self.assertEqual(official_filter["structure_id"], expected_value)

    def test_recommend_douban_high_score_is_sent_in_official_filter_json(self) -> None:
        """电视剧和电影推荐豆瓣高分应按官网 filter JSON 发送。"""
        module, _settings = load_plugin_module()
        plugin = module.IqiyiDiscover()

        for channel in ("tv", "movie"):
            recommend_items = filter_items_for(module, channel, "recommend")
            raw_value = next(
                key for key, label in recommend_items.items()
                if label == "豆瓣高分"
            )
            captured = {}

            def capture_request(**kwargs):
                """保存当前推荐筛选请求参数。"""
                captured.update(kwargs)
                return [
                    {
                        "albumId": 1013,
                        "name": "豆瓣高分样例",
                        "imageUrl": "http://pic5.iqiyipic.com/image/douban.jpg",
                        "period": "2025-01-01",
                    }
                ]

            with patch.object(plugin, "_IqiyiDiscover__request", capture_request):
                plugin.iqiyi_discover(
                    mtype=channel,
                    mode="11",
                    recommend=raw_value,
                    page=1,
                    count=10,
                )

            key, expected_value = raw_value.split("=", 1)
            self.assertEqual(key, "structure_id")
            extra_params = dict(captured["extra_params"])
            self.assertIn("filter", extra_params)
            self.assertNotIn("structure_id", extra_params)
            official_filter = json.loads(extra_params["filter"])
            self.assertEqual(official_filter["structure_id"], expected_value)

    def test_recent_free_chip_maps_to_official_recent_free_smart_tag(self) -> None:
        """所有带近期转免的频道都应映射到官方 smart_tag_v2。"""
        module, _settings = load_plugin_module()

        ui = module.IqiyiDiscover.iqiyi_filter_ui()
        shows = [
            TV_SHOW,
            SHORT_DRAMA_SHOW,
            MOVIE_SHOW,
            VARIETY_SHOW,
            ANIME_SHOW,
            CHILDREN_SHOW,
            COMIC_SHOW,
            DOCUMENTARY_SHOW,
        ]

        for show in shows:
            with self.subTest(show=show):
                pay_values = chip_values_for(ui, "资费", show)
                self.assertEqual(pay_values[0], "smart_tag_v2=近期转免")
                self.assertIn("is_purchase=0", pay_values)

    def test_tv_recent_free_legacy_mode_maps_to_official_smart_tag(self) -> None:
        """旧版 mode=24 近期转免值应兼容转换为官方 smart_tag_v2。"""
        module, _settings = load_plugin_module()
        captured = {}

        def fake_request(**kwargs):
            """记录进入缓存请求前的参数。"""
            captured.update(kwargs)
            return [
                {
                    "albumId": 1009,
                    "name": "近期转免样例",
                    "imageUrl": "http://pic5.iqiyipic.com/image/jm.jpg",
                    "period": "2025-04-28",
                }
            ]

        plugin = module.IqiyiDiscover()
        with patch.object(plugin, "_IqiyiDiscover__request", fake_request):
            medias = plugin.iqiyi_discover(
                mtype="tv",
                mode="11",
                is_purchase="mode=24",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["近期转免样例"])
        self.assertEqual(captured["mode"], "11")
        self.assertEqual(captured["is_purchase"], "")
        self.assertEqual(captured["recent_free"], "")
        self.assertEqual(captured["extra_params"], (("smart_tag_v2", "近期转免"),))

    def test_modern_recent_free_legacy_mode_maps_to_official_smart_tag(self) -> None:
        """新版片库频道旧版 mode=24 近期转免值也应兼容转换为官方 smart_tag_v2。"""
        module, _settings = load_plugin_module()
        captured = {}

        def fake_request(**kwargs):
            """记录进入请求前的参数。"""
            captured.update(kwargs)
            return [
                {
                    "album_id": 1010,
                    "title": "近期转免电影",
                    "image_url_normal": "http://pic5.iqiyipic.com/image/movie.jpg",
                    "showDate": "2026-06-20",
                }
            ]

        plugin = module.IqiyiDiscover()
        with patch.object(plugin, "_IqiyiDiscover__request", fake_request):
            medias = plugin.iqiyi_discover(
                mtype="movie",
                mode="11",
                is_purchase="mode=24",
                page=1,
                count=10,
            )

        self.assertEqual([media.title for media in medias], ["近期转免电影"])
        self.assertEqual(captured["mode"], "11")
        self.assertEqual(captured["is_purchase"], "")
        self.assertEqual(captured["recent_free"], "")
        self.assertEqual(captured["extra_params"], (("smart_tag_v2", "近期转免"),))

    def test_tv_recent_free_request_sends_official_smart_tag(self) -> None:
        """最终 HTTP 请求应按官方近期转免发法发送 smart_tag_v2。"""
        module, _settings = load_plugin_module()
        captured = {}

        def fake_get(url, **kwargs):
            """记录最终 HTTP 请求参数。"""
            captured["url"] = url
            captured.update(kwargs.get("params") or {})
            return FakeResponse({"code": "A00000", "data": {"list": []}})

        plugin = module.IqiyiDiscover()
        with patch.object(module.requests, "get", fake_get):
            plugin._IqiyiDiscover__request(
                page=1,
                mtype="tv",
                mode="11",
                is_purchase="",
                recent_free="",
                extra_params=(("smart_tag_v2", "近期转免"),),
            )

        self.assertEqual(captured["url"], "https://mesh.if.iqiyi.com/portal/videolib/data")
        self.assertEqual(captured["mode"], "11")
        self.assertEqual(captured["smart_tag_v2"], "近期转免")
        self.assertNotIn("is_purchase", captured)
        self.assertNotIn("recent_free", captured)
        self.assertNotIn("data_type", captured)

    def test_iqiyi_discover_request_uses_requested_count_as_ret_num(self) -> None:
        """分页请求应使用 MoviePilot 传入的 count，避免下一页跳过中间数据。"""
        module, _settings = load_plugin_module()
        captured = {}

        def fake_get(url, **kwargs):
            """记录最终 HTTP 请求参数。"""
            captured["url"] = url
            captured.update(kwargs.get("params") or {})
            return FakeResponse({"code": "A00000", "data": {"list": []}})

        plugin = module.IqiyiDiscover()
        with patch.object(module.requests, "get", fake_get):
            plugin._IqiyiDiscover__request(
                page=2,
                mtype="tv",
                mode="11",
                count=12,
                extra_params=(("smart_tag_v2", "近期转免"),),
            )

        self.assertEqual(captured["url"], "https://mesh.if.iqiyi.com/portal/videolib/data")
        self.assertEqual(captured["page_id"], "2")
        self.assertEqual(captured["ret_num"], "12")

    def test_init_plugin_adds_iqiyi_image_domains(self) -> None:
        """初始化时应补充爱奇艺图片安全域名。"""
        module, settings = load_plugin_module()
        plugin = module.IqiyiDiscover()

        plugin.init_plugin({"enabled": True})

        self.assertIn("iqiyipic.com", settings.SECURITY_IMAGE_DOMAINS)
        self.assertIn("pic0.iqiyipic.com", settings.SECURITY_IMAGE_DOMAINS)


if __name__ == "__main__":
    unittest.main()
