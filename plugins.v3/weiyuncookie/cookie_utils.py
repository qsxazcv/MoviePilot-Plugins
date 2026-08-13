# -*- coding: utf-8 -*-
"""微云 Cookie 助手的 Cookie 解析与判断工具。"""

from __future__ import annotations

from typing import Any, Dict, List, Set


def filter_relevant_cookies(cookies: List[Dict[str, Any]], include_qq_domain: bool) -> List[Dict[str, Any]]:
    """筛选微云登录需要保存的 Cookie。"""
    result: List[Dict[str, Any]] = []
    for cookie in cookies or []:
        domain = str(cookie.get("domain") or "").lstrip(".").lower()
        if domain.endswith("weiyun.com") or (include_qq_domain and domain.endswith("qq.com")):
            result.append(cookie)
    return result


def cookies_to_header(cookies: List[Dict[str, Any]]) -> str:
    """将浏览器 Cookie 列表转换为 HTTP Cookie 头。"""
    pairs = []
    seen = set()
    for cookie in cookies:
        name = str(cookie.get("name") or "").strip()
        value = str(cookie.get("value") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        pairs.append(f"{name}={value}")
    return "; ".join(pairs)


def cookie_names(cookie: str) -> Set[str]:
    """从 Cookie 头中提取字段名集合。"""
    names = set()
    for part in str(cookie or "").split(";"):
        if "=" not in part:
            continue
        name = part.split("=", 1)[0].strip()
        if name:
            names.add(name)
    return names


def looks_logged_in(names: Set[str], url: str) -> bool:
    """根据关键 Cookie 字段和当前 URL 判断是否可能已登录。"""
    important = {"uin", "skey", "p_skey", "pt4_token", "wxuin", "wxsid", "qqmusic_uin"}
    if names.intersection(important) and "login" not in str(url).lower():
        return True
    return False
