# -*- coding: utf-8 -*-
"""微云 Cookie 助手的 OpenList 存储同步客户端。"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OpenListClient:
    """封装 OpenList 存储读取与更新接口。"""

    def __init__(self, base_url: str, token: str):
        """初始化 OpenList 客户端。"""
        self._base_url = (base_url or "").rstrip("/")
        self._token = token or ""

    def get_storage(self, storage_id: int) -> Dict[str, Any]:
        """读取指定 OpenList 存储详情。"""
        candidates = [
            ("GET", f"/api/admin/storage/get?id={storage_id}", None),
            ("GET", f"/api/admin/storage/detail?id={storage_id}", None),
            ("POST", "/api/admin/storage/get", {"id": storage_id}),
            ("POST", "/api/admin/storage/detail", {"id": storage_id}),
        ]
        errors = []
        for method, path, data in candidates:
            try:
                result = self.request(method, path, data)
                storage = result.get("data")
                if isinstance(storage, dict):
                    return storage
            except Exception as err:
                errors.append(str(err))
        raise RuntimeError("无法读取 OpenList 存储详情：" + " | ".join(errors[-2:]))

    def update_storage(self, storage: Dict[str, Any], default_storage_id: int) -> None:
        """更新 OpenList 存储配置。"""
        storage_id = storage.get("id") or storage.get("ID") or default_storage_id
        candidates = [
            ("POST", "/api/admin/storage/update", storage),
            ("PUT", "/api/admin/storage/update", storage),
            ("POST", f"/api/admin/storage/update?id={storage_id}", storage),
        ]
        errors = []
        for method, path, data in candidates:
            try:
                self.request(method, path, data)
                return
            except Exception as err:
                errors.append(str(err))
        raise RuntimeError("无法更新 OpenList 存储：" + " | ".join(errors[-2:]))

    def request(self, method: str, path: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """调用 OpenList 管理接口并解析 JSON 响应。"""
        url = f"{self._base_url}{path}"
        body = None
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=body, headers=self._headers(), method=method.upper())
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8", errors="ignore")
        except HTTPError as err:
            raw = err.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenList HTTP {err.code}: {raw[:300]}") from err
        except URLError as err:
            raise RuntimeError(f"OpenList 连接失败：{err.reason}") from err
        try:
            result = json.loads(raw or "{}")
        except Exception as err:
            raise RuntimeError(f"OpenList 返回非 JSON：{raw[:300]}") from err
        code = result.get("code")
        if code not in (200, 0, None):
            raise RuntimeError(result.get("message") or result.get("msg") or f"OpenList 返回 code={code}")
        return result

    def _headers(self) -> Dict[str, str]:
        """生成 OpenList 请求头。"""
        return {
            "Authorization": self._token,
            "Content-Type": "application/json;charset=utf-8",
            "Accept": "application/json, text/plain, */*",
        }


def set_cookie_field(storage: Dict[str, Any], cookie: str) -> Dict[str, Any]:
    """把 Cookie 写入 OpenList 存储配置副本。"""
    updated = json.loads(json.dumps(storage, ensure_ascii=False))
    for key in ("addition", "Addition"):
        if key in updated:
            addition = updated.get(key)
            if isinstance(addition, str):
                try:
                    addition_obj = json.loads(addition or "{}")
                except Exception:
                    addition_obj = {}
                addition_obj = set_cookie_in_mapping(addition_obj, cookie)
                updated[key] = json.dumps(addition_obj, ensure_ascii=False)
                return updated
            if isinstance(addition, dict):
                updated[key] = set_cookie_in_mapping(addition, cookie)
                return updated
    updated = set_cookie_in_mapping(updated, cookie)
    return updated


def set_cookie_in_mapping(mapping: Dict[str, Any], cookie: str) -> Dict[str, Any]:
    """在配置字典中按常见字段名写入 Cookie。"""
    if not isinstance(mapping, dict):
        mapping = {}
    lower_map = {str(k).lower(): k for k in mapping.keys()}
    target = lower_map.get("cookie") or lower_map.get("cookies") or lower_map.get("ck") or "cookie"
    mapping[target] = cookie
    return mapping
