# -*- coding: utf-8 -*-
"""微云 Cookie 助手的浏览器启动辅助工具。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List


def browser_args() -> List[str]:
    """返回后端浏览器启动参数。"""
    return [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--lang=zh-CN",
    ]


def prepare_cloakbrowser_env(logger=None) -> None:
    """兼容 MoviePilot 容器内置的 /core/.cloakbrowser 内核目录。"""
    if os.environ.get("CLOAKBROWSER_CACHE_DIR") or os.environ.get("CLOAKBROWSER_BINARY_PATH"):
        return
    for cache_dir in (Path("/core/.cloakbrowser"), Path("/moviepilot/.cloakbrowser")):
        if not cache_dir.exists():
            continue
        binaries = sorted(cache_dir.glob("chromium-*/chrome"), reverse=True)
        if binaries:
            os.environ["CLOAKBROWSER_CACHE_DIR"] = str(cache_dir)
            if logger:
                logger.info("微云 Cookie 助手已适配 CloakBrowser 内核目录：%s", cache_dir)
            return
