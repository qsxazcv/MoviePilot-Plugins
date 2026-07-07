# -*- coding: utf-8 -*-
"""微云 Cookie 助手的浏览器启动辅助工具。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional


PLAYWRIGHT_EXECUTABLE_CANDIDATE_ROOTS = (
    Path("/moviepilot/.cache/ms-playwright"),
    Path("/moviepilot/.cloakbrowser"),
    Path("/core/.cloakbrowser"),
)
CLOAKBROWSER_CACHE_DIRS = (
    Path("/moviepilot/.cloakbrowser"),
    Path("/core/.cloakbrowser"),
)
PLAYWRIGHT_EXECUTABLE_PATTERNS = (
    "chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
    "chromium-*/chrome-linux64/chrome",
    "chromium-*/chrome-linux/chrome",
    "chromium-*/chrome",
)
CLOAKBROWSER_EXECUTABLE_PATTERNS = (
    "chromium-*/chrome",
    "chromium-*/chrome-linux64/chrome",
    "chromium-*/chrome-linux/chrome",
)


def browser_args() -> List[str]:
    """返回后端浏览器启动参数。"""
    return [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--lang=zh-CN",
    ]


def _first_existing_executable(root: Optional[Path], patterns) -> Optional[str]:
    if not root:
        return None
    root = Path(root)
    if not root.exists():
        return None
    for pattern in patterns:
        for executable in sorted(root.glob(pattern), reverse=True):
            if executable.exists():
                return str(executable)
    return None


def existing_browser_executable() -> Optional[str]:
    """查找 MoviePilot 容器中已存在的 Chromium 可执行文件。"""
    for env_name in (
        "WEIYUN_COOKIE_BROWSER_EXECUTABLE",
        "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH",
        "CLOAKBROWSER_BINARY_PATH",
    ):
        executable = os.environ.get(env_name)
        if executable and Path(executable).exists():
            return executable
    for root in PLAYWRIGHT_EXECUTABLE_CANDIDATE_ROOTS:
        executable = _first_existing_executable(root, PLAYWRIGHT_EXECUTABLE_PATTERNS)
        if executable:
            return executable
    return None


def playwright_launch_kwargs(headless: bool = True) -> dict:
    """返回 Playwright Chromium 启动参数，优先直连已有浏览器内核。"""
    kwargs = {
        "headless": bool(headless),
        "args": browser_args(),
    }
    executable = existing_browser_executable()
    if executable:
        kwargs["executable_path"] = executable
    return kwargs


def _cloakbrowser_chrome_in_cache(cache_dir) -> Optional[str]:
    return _first_existing_executable(Path(cache_dir) if cache_dir else None, CLOAKBROWSER_EXECUTABLE_PATTERNS)


def prepare_cloakbrowser_env(logger=None) -> Optional[str]:
    """兼容 MoviePilot 容器内置的 /moviepilot/.cloakbrowser 内核目录。"""
    binary = os.environ.get("CLOAKBROWSER_BINARY_PATH")
    if binary and Path(binary).exists():
        return binary

    cache_env = os.environ.get("CLOAKBROWSER_CACHE_DIR")
    binary = _cloakbrowser_chrome_in_cache(cache_env)
    if binary:
        os.environ["CLOAKBROWSER_BINARY_PATH"] = binary
        return binary

    for cache_dir in CLOAKBROWSER_CACHE_DIRS:
        if not cache_dir.exists():
            continue
        binary = _cloakbrowser_chrome_in_cache(cache_dir)
        if binary:
            os.environ["CLOAKBROWSER_CACHE_DIR"] = str(cache_dir)
            os.environ["CLOAKBROWSER_BINARY_PATH"] = binary
            if logger:
                logger.info("微云 Cookie 助手已直连 CloakBrowser 内核：%s", binary)
            return binary
    return None
