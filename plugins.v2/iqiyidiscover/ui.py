"""MoviePilot ???????? UI?"""

from typing import Dict, List

from .constants import (
    ADVANCED_FILTER_MODELS,
    CHANNEL_PARAMS,
    FILTER_EXPAND_COLLAPSED_VALUE,
    FILTER_EXPAND_EXPANDED_VALUE,
    FILTER_EXPAND_MODEL,
    MODE_PARAMS,
    SORT_GROUPS,
    _with_filter_expand,
)
from .filters import (
    FILTER_GROUPS,
)

def iqiyi_filter_ui() -> List[dict]:
    """
    返回探索页筛选 UI。
    """
    def chip_row(label: str, model: str, items: Dict[str, str], show: str = None) -> dict:
        """
        构造探索页 VChipGroup 行。
        """
        props = {"class": "flex justify-start items-center"}
        if show:
            props["show"] = show
        return {
            "component": "div",
            "props": props,
            "content": [
                {
                    "component": "div",
                    "props": {"class": "mr-5"},
                    "content": [{"component": "VLabel", "text": label}],
                },
                {
                    "component": "VChipGroup",
                    "props": {"model": model},
                    "content": [
                        {
                            "component": "VChip",
                            "props": {
                                "filter": True,
                                "tile": True,
                                "value": key,
                            },
                            "text": value,
                        }
                        for key, value in items.items()
                    ],
                },
            ],
        }

    def toggle_row(mtype: str) -> dict:
        """
        构造高级筛选展开/收起控制行。
        """
        return {
            "component": "div",
            "props": {
                "class": "flex justify-start items-center",
                "show": "{{mtype == '" + mtype + "'}}",
            },
            "content": [
                {
                    "component": "VChipGroup",
                    "props": {"model": FILTER_EXPAND_MODEL},
                    "content": [
                        {
                            "component": "VChip",
                            "props": {
                                "filter": True,
                                "tile": True,
                                "value": FILTER_EXPAND_EXPANDED_VALUE,
                            },
                            "text": "展开",
                        },
                        {
                            "component": "VChip",
                            "props": {
                                "filter": True,
                                "tile": True,
                                "value": FILTER_EXPAND_COLLAPSED_VALUE,
                            },
                            "text": "收起",
                        },
                    ],
                }
            ],
        }

    ui = [
        {
            "component": "div",
            "props": {"class": "flex justify-start items-center"},
            "content": [
                {
                    "component": "div",
                    "props": {"class": "mr-5"},
                    "content": [{"component": "VLabel", "text": "种类"}],
                },
                {
                    "component": "VChipGroup",
                    "props": {"model": "mtype"},
                    "content": [
                        {
                            "component": "VChip",
                            "props": {
                                "filter": True,
                                "tile": True,
                                "value": key,
                            },
                            "text": value["name"],
                        }
                        for key, value in CHANNEL_PARAMS.items()
                    ],
                },
            ],
        },
    ]
    for mtype, groups in FILTER_GROUPS.items():
        show = "{{mtype == '" + mtype + "'}}"
        has_advanced_rows = any(group["model"] in ADVANCED_FILTER_MODELS for group in groups)
        for group in groups:
            group_show = group.get("show") or show
            if group["model"] in ADVANCED_FILTER_MODELS:
                group_show = _with_filter_expand(group_show, expanded=True)
            ui.append(
                chip_row(
                    label=group["label"],
                    model=group["model"],
                    items=group["items"],
                    show=group_show,
                )
            )
        ui.append(
            chip_row(
                label="排序",
                model="mode",
                items=SORT_GROUPS.get(mtype, MODE_PARAMS),
                show=show,
            )
        )
        if has_advanced_rows:
            ui.append(toggle_row(mtype))
    return ui
