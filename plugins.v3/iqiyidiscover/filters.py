"""?????????????????"""

import json
from pathlib import Path
from typing import Dict, List

from app.log import logger

from .constants import (
    FILTER_GROUPS as FALLBACK_FILTER_GROUPS,
    MODE_PARAMS,
    MODEL_DEFAULT_QUERY_PARAM,
    OFFICIAL_FILTER_JSON_KEYS,
    OFFICIAL_FILTER_JSON_MODELS,
    OFFICIAL_FILTER_JSON_MODEL_KEYS,
    OFFICIAL_FILTER_JSON_TRIGGER_KEYS,
    RECENT_FREE_SMART_TAG_VALUE,
    SORT_GROUPS,
    TV_SUBGENRE_PARAMS_BY_GENRE,
)

def __load_official_filter_groups() -> Dict[str, List[dict]]:
    """
    Load verified filter params captured from iQIYI's official videolib tag API.
    """
    path = Path(__file__).with_name("official_filters.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        filters = payload.get("filters") or {}
        return {
            str(channel): [
                {
                    "label": str(group["label"]),
                    "model": str(group["model"]),
                    "items": dict(group.get("items") or {}),
                }
                for group in groups
                if isinstance(group, dict) and group.get("label") and group.get("model")
            ]
            for channel, groups in filters.items()
            if isinstance(groups, list)
        }
    except Exception as err:
        logger.warning(f"加载爱奇艺官方筛选参数失败，使用内置兜底参数：{err}")
        return {}


def __load_official_linked_subgenres() -> Dict[str, Dict[str, Dict[str, str]]]:
    """
    读取官方类型到细选的联动参数。
    """
    path = Path(__file__).with_name("official_filters.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        linked_subgenres = payload.get("linked_subgenres") or {}
        normalized: Dict[str, Dict[str, Dict[str, str]]] = {}
        for channel, channel_mapping in linked_subgenres.items():
            if not isinstance(channel_mapping, dict):
                continue
            normalized_channel: Dict[str, Dict[str, str]] = {}
            for genre_param, subgenre_items in channel_mapping.items():
                if not isinstance(subgenre_items, dict) or not subgenre_items:
                    continue
                normalized_channel[str(genre_param)] = {
                    str(param): str(text)
                    for param, text in subgenre_items.items()
                }
            if normalized_channel:
                normalized[str(channel)] = normalized_channel
        return normalized
    except Exception as err:
        logger.warning(f"加载爱奇艺官方联动细选失败，使用内置兜底参数：{err}")
        return {}



def subgenre_show(mtype: str, genre_param: str = "") -> str:
    """
    返回指定频道细选行的显示条件。
    """
    if genre_param:
        return "{{mtype == '" + mtype + "' && genre == '" + genre_param + "'}}"
    return "{{mtype == '" + mtype + "' && !genre}}"


def expand_linked_subgenre_groups(
    filter_groups: Dict[str, List[dict]],
    linked_subgenres: Dict[str, Dict[str, Dict[str, str]]],
) -> Dict[str, List[dict]]:
    """
    将官方细选从全量平铺扩展为跟随类型切换。
    """
    if not linked_subgenres:
        return filter_groups

    expanded_groups = dict(filter_groups)
    for channel, channel_subgenres in linked_subgenres.items():
        channel_groups = filter_groups.get(channel) or []
        genre_group = next((group for group in channel_groups if group.get("model") == "genre"), None)
        subgenre_group = next((group for group in channel_groups if group.get("model") == "subgenre"), None)
        if not genre_group or not subgenre_group:
            continue

        expanded_channel_groups = []
        for group in channel_groups:
            if group.get("model") == "subgenre":
                continue
            expanded_channel_groups.append(group)
            if group.get("model") != "genre":
                continue

            default_items = channel_subgenres.get("")
            if default_items:
                expanded_channel_groups.append(
                    {
                        "label": "细选",
                        "model": "subgenre",
                        "items": dict(default_items),
                        "show": subgenre_show(channel),
                    }
                )
            for genre_param in (genre_group.get("items") or {}):
                subgenre_items = channel_subgenres.get(genre_param)
                if not subgenre_items:
                    continue
                expanded_channel_groups.append(
                    {
                        "label": "细选",
                        "model": "subgenre",
                        "items": dict(subgenre_items),
                        "show": subgenre_show(channel, genre_param),
                    }
                )
        expanded_groups[channel] = expanded_channel_groups
    return expanded_groups


OFFICIAL_LINKED_SUBGENRES = __load_official_linked_subgenres()
if not OFFICIAL_LINKED_SUBGENRES:
    OFFICIAL_LINKED_SUBGENRES = {"tv": TV_SUBGENRE_PARAMS_BY_GENRE}

FILTER_GROUPS = expand_linked_subgenre_groups(
    __load_official_filter_groups() or FALLBACK_FILTER_GROUPS,
    OFFICIAL_LINKED_SUBGENRES,
)


def filter_items(channel: str, model: str) -> Dict[str, str]:
    """
    按筛选模型读取官方筛选项，避免 UI 行插入后固定下标失效。
    """
    for group in FILTER_GROUPS.get(channel, []):
        if group.get("model") == model:
            return group["items"]
    return {}


TV_GENRE_PARAMS = filter_items("tv", "genre")
TV_SUBGENRE_PARAMS = filter_items("tv", "subgenre")
TV_REGION_PARAMS = filter_items("tv", "region")
TV_HALL_PARAMS = filter_items("tv", "hall")
TV_SPEC_PARAMS = filter_items("tv", "spec")
TV_AWARD_PARAMS = filter_items("tv", "award")
TV_THEATER_PARAMS = filter_items("tv", "theater")
TV_ACTOR_PARAMS = filter_items("tv", "actor")
TV_RECOMMEND_PARAMS = filter_items("tv", "recommend")


def normalize_mode(mtype: str, mode: str = "11", allow_recent: bool = False) -> str:
    """
    按频道限制排序值，避免请求 UI 不暴露的历史排序。
    """
    mode = str(mode or "").strip()
    if allow_recent and mode == "24":
        return mode
    allowed_modes = SORT_GROUPS.get(mtype, MODE_PARAMS)
    return mode if mode in allowed_modes else "11"


def selected_category_ids(*values: str) -> str:
    """
    将地区、类型、题材等三级分类筛选合并为爱奇艺接口支持的逗号格式。
    """
    selected = []
    for value in values:
        value = str(value or "").strip()
        if value and value not in selected:
            selected.append(value)
    return ",".join(selected)

def append_query_param(params: Dict[str, List[str]], key: str, value: str) -> None:
    """
    将筛选参数追加到待请求参数中，并保持同一参数去重。
    """
    key = str(key or "").strip()
    value = str(value or "").strip()
    if not key or not value:
        return
    values = params.setdefault(key, [])
    if value not in values:
        values.append(value)

def filter_query_params(mtype: str = "tv", **filters: str) -> Dict[str, str]:
    """
    将探索页筛选模型转换为爱奇艺接口查询参数。
    """
    params: Dict[str, List[str]] = {}
    official_filter_params: Dict[str, List[str]] = {}
    mtype_key = str(mtype or "").strip()
    official_filter_models = OFFICIAL_FILTER_JSON_MODELS.get(mtype_key, ())
    official_filter_model_keys = OFFICIAL_FILTER_JSON_MODEL_KEYS.get(mtype_key, {})
    for model, raw_value in filters.items():
        raw_value = str(raw_value or "").strip()
        if not raw_value:
            continue
        default_key = MODEL_DEFAULT_QUERY_PARAM.get(model, "three_category_id")
        for token in raw_value.split(","):
            token = token.strip()
            if not token:
                continue
            if "=" in token:
                key, value = token.split("=", 1)
            else:
                key, value = default_key, token
            if key == "mode" and model == "is_purchase" and value == "24":
                append_query_param(params, "smart_tag_v2", RECENT_FREE_SMART_TAG_VALUE)
                continue
            if key == "smart_tag_v2" and model == "is_purchase":
                append_query_param(params, "smart_tag_v2", RECENT_FREE_SMART_TAG_VALUE)
                continue
            if key == "mode":
                continue
            official_filter_keys = official_filter_model_keys.get(model)
            if official_filter_keys is None and model in official_filter_models:
                official_filter_keys = OFFICIAL_FILTER_JSON_KEYS
            if official_filter_keys and key in official_filter_keys:
                append_query_param(official_filter_params, key, value)
                continue
            append_query_param(params, key, value)
    query_params = {key: ",".join(values) for key, values in params.items()}
    if official_filter_params:
        official_filter = {key: ",".join(values) for key, values in official_filter_params.items()}
        query_params["filter"] = json.dumps(official_filter, ensure_ascii=False, separators=(",", ":"))
    return query_params

def apply_official_filter_json(query_params: Dict[str, str]) -> None:
    """
    将爱奇艺官方规格筛选合并到 filter JSON，避免顶层参数被接口忽略。
    """
    if not any(str(query_params.get(key) or "").strip() for key in OFFICIAL_FILTER_JSON_TRIGGER_KEYS):
        return

    official_filter: Dict[str, str] = {}
    existing_filter = str(query_params.pop("filter", "") or "").strip()
    if existing_filter:
        try:
            parsed_filter = json.loads(existing_filter)
        except (TypeError, ValueError):
            parsed_filter = {}
        if isinstance(parsed_filter, dict):
            for key, value in parsed_filter.items():
                key = str(key or "").strip()
                value = str(value or "").strip()
                if key and value:
                    official_filter[key] = value

    for key in OFFICIAL_FILTER_JSON_KEYS:
        value = str(query_params.pop(key, "") or "").strip()
        if value:
            official_filter[key] = value

    if official_filter:
        query_params["filter"] = json.dumps(official_filter, ensure_ascii=False, separators=(",", ":"))
