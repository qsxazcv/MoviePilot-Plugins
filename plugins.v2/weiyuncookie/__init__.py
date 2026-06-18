# -*- coding: utf-8 -*-
"""微云 Cookie 助手 MoviePilot V2 本地插件。

通过 Playwright 启动后端 Chromium 打开微云登录页，用户选择 QQ / 微信扫码登录后，
插件截图二维码、等待扫码后的自动跳转，并提取 weiyun.com / qq.com 相关 Cookie。
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from apscheduler.triggers.cron import CronTrigger
from fastapi import Response

from app.core.config import settings
from app.core.event import Event, eventmanager
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None

try:
    from cloakbrowser import launch_context as cloak_launch_context
except Exception:  # pragma: no cover
    cloak_launch_context = None


class weiyuncookie(_PluginBase):
    plugin_name = "微云Cookie助手"
    plugin_desc = "支持 QQ / 微信扫码登录微云，自动提取并保存 Cookie，可检测有效性并同步到 OpenList。"
    plugin_icon = "https://raw.githubusercontent.com/qsxazcv/MoviePilot-Plugins/main/icons/weiyuncookie.png"
    plugin_version = "0.1.31"
    plugin_author = "qsxazcv"
    author_url = "https://github.com/qsxazcv/MoviePilot-Plugins"
    plugin_config_prefix = "weiyuncookie_"
    plugin_order = 88
    auth_level = 1

    _enabled: bool = False
    _onlyonce: bool = False
    _headless: bool = True
    _login_type: str = "qq"
    _login_url: str = "https://www.weiyun.com/"
    _timeout_seconds: int = 180
    _include_qq_domain: bool = True
    _browser_mode: str = "playwright"
    _notify_enabled: bool = True
    _notify_login_result: bool = True
    _notify_openlist_result: bool = True
    _qrcode_public_base_url: str = ""
    _check_enabled: bool = False
    _check_notify: bool = True
    _check_onlyonce: bool = False
    _check_cron: str = "0 */6 * * *"
    _last_status: str = "未运行"
    _last_run: str = ""
    _last_cookie_count: int = 0
    _last_check: str = ""
    _last_check_status: str = "未检测"
    _openlist_enabled: bool = False
    _openlist_auto_sync: bool = False
    _openlist_sync_after_relogin: bool = True
    _openlist_sync_onlyonce: bool = False
    _openlist_url: str = "http://192.168.5.100:5244"
    _openlist_token: str = ""
    _openlist_storage_id: int = 2
    _last_openlist_sync: str = ""
    _last_openlist_sync_status: str = "未同步"
    _login_running: bool = False
    _login_thread: Optional[threading.Thread] = None

    def init_plugin(self, config: dict = None):
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._onlyonce = bool(config.get("onlyonce", False))
        self._headless = bool(config.get("headless", True))
        self._login_type = self.__normalize_login_type(config.get("login_type"))
        self._login_url = str(config.get("login_url") or "https://www.weiyun.com/").strip()
        self._timeout_seconds = self.__to_int(config.get("timeout_seconds"), 180, 30, 600)
        self._include_qq_domain = bool(config.get("include_qq_domain", True))
        self._browser_mode = self.__normalize_browser_mode(config.get("browser_mode"))
        self._notify_enabled = bool(config.get("notify_enabled", True))
        self._notify_login_result = bool(config.get("notify_login_result", True))
        self._notify_openlist_result = bool(config.get("notify_openlist_result", True))
        self._qrcode_public_base_url = str(config.get("qrcode_public_base_url") or "").strip().rstrip("/")
        self._check_enabled = bool(config.get("check_enabled", False))
        self._check_notify = bool(config.get("check_notify", True))
        self._check_onlyonce = bool(config.get("check_onlyonce", False))
        self._check_cron = str(config.get("check_cron") or "0 */6 * * *").strip()
        self._last_status = config.get("last_status") or self._last_status
        self._last_run = config.get("last_run") or self._last_run
        self._last_cookie_count = self.__to_int(config.get("last_cookie_count"), self._last_cookie_count, 0, 999)
        self._last_check = config.get("last_check") or self._last_check
        self._last_check_status = config.get("last_check_status") or self._last_check_status
        self._openlist_enabled = bool(config.get("openlist_enabled", False))
        self._openlist_auto_sync = bool(config.get("openlist_auto_sync", False))
        self._openlist_sync_after_relogin = bool(config.get("openlist_sync_after_relogin", True))
        self._openlist_sync_onlyonce = bool(config.get("openlist_sync_onlyonce", False))
        self._openlist_url = str(config.get("openlist_url") or "http://192.168.5.100:5244").strip().rstrip("/")
        self._openlist_token = str(config.get("openlist_token") or "").strip()
        self._openlist_storage_id = self.__to_int(config.get("openlist_storage_id"), 2, 1, 999999)
        self._last_openlist_sync = config.get("last_openlist_sync") or self._last_openlist_sync
        self._last_openlist_sync_status = config.get("last_openlist_sync_status") or self._last_openlist_sync_status
        logger.info(
            "微云 Cookie 助手初始化：enabled=%s, onlyonce=%s, login_type=%s, browser_mode=%s, headless=%s, timeout=%s, notify_enabled=%s, check_enabled=%s, check_cron=%s, openlist_enabled=%s, openlist_auto_sync=%s",
            self._enabled,
            self._onlyonce,
            self._login_type,
            self._browser_mode,
            self._headless,
            self._timeout_seconds,
            self._notify_enabled,
            self._check_enabled,
            self._check_cron,
            self._openlist_enabled,
            self._openlist_auto_sync,
        )
        if self._onlyonce:
            self._onlyonce = False
            self.__update_config()
            self.__start_login_thread(source="onlyonce")
        if self._check_onlyonce:
            self._check_onlyonce = False
            self.__update_config()
            threading.Thread(target=self.check_cookie_validity, name="WeiyunCookieCheckOnce", daemon=True).start()
        if self._openlist_sync_onlyonce:
            self._openlist_sync_onlyonce = False
            self.__update_config()
            threading.Thread(target=self.sync_cookie_to_openlist, name="WeiyunCookieOpenListSyncOnce", daemon=True).start()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [
            {
                "cmd": "/weiyun_login",
                "event": EventType.PluginAction,
                "desc": "微云扫码登录并推送二维码",
                "category": "微云",
                "data": {"action": "weiyun_login"},
            },
            {
                "cmd": "/weiyun_status",
                "event": EventType.PluginAction,
                "desc": "查询微云 Cookie 状态",
                "category": "微云",
                "data": {"action": "weiyun_status"},
            },
            {
                "cmd": "/weiyun_check",
                "event": EventType.PluginAction,
                "desc": "立即检测微云 Cookie 有效性",
                "category": "微云",
                "data": {"action": "weiyun_check"},
            },
        ]

    def get_service(self) -> List[Dict[str, Any]]:
        if self._enabled and self._check_enabled and self._check_cron:
            try:
                return [{
                    "id": "weiyuncookie_check",
                    "name": "微云 Cookie 有效性检测",
                    "trigger": CronTrigger.from_crontab(self._check_cron, timezone=settings.TZ),
                    "func": self.check_cookie_validity,
                    "kwargs": {},
                }]
            except Exception as err:
                logger.error("微云 Cookie 助手检测 Cron 配置错误：%s", err)
                self._last_check_status = f"检测 Cron 配置错误：{err}"
                self.__update_config()
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/start_login",
                "endpoint": self.__api_start_login,
                "methods": ["POST", "GET"],
                "auth": "bear",
                "summary": "启动微云扫码登录并提取 Cookie",
            },
            {
                "path": "/status",
                "endpoint": self.__api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "查询微云 Cookie 助手状态",
            },
            {
                "path": "/clear_cookie",
                "endpoint": self.__api_clear_cookie,
                "methods": ["POST", "GET"],
                "auth": "bear",
                "summary": "清除已保存的微云 Cookie",
            },
            {
                "path": "/check_cookie",
                "endpoint": self.__api_check_cookie,
                "methods": ["POST", "GET"],
                "auth": "bear",
                "summary": "立即检测微云 Cookie 是否有效",
            },
            {
                "path": "/sync_openlist",
                "endpoint": self.__api_sync_openlist,
                "methods": ["POST", "GET"],
                "auth": "bear",
                "summary": "将微云 Cookie 同步到 OpenList 腾讯微云存储",
            },
            {
                "path": "/qrcode_image",
                "endpoint": self.__api_qrcode_image,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "返回最近一次微云登录二维码图片",
            },
        ]


    def get_render_mode(self) -> Tuple[str, str]:
        """使用 Vue 联邦组件渲染配置页与详情页。"""
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """Vue 模式下配置页由联邦 Config 组件渲染；这里仅返回默认模型。"""
        return None, self.__build_form_model()

    def __build_form_model(self) -> Dict[str, Any]:
        return {
            "enabled": self._enabled,
            "onlyonce": False,
            "headless": self._headless,
            "login_type": self._login_type,
            "login_url": self._login_url,
            "browser_mode": self._browser_mode,
            "timeout_seconds": self._timeout_seconds,
            "include_qq_domain": self._include_qq_domain,
            "notify_enabled": self._notify_enabled,
            "notify_login_result": self._notify_login_result,
            "notify_openlist_result": self._notify_openlist_result,
            "qrcode_public_base_url": self._qrcode_public_base_url,
            "check_enabled": self._check_enabled,
            "check_notify": self._check_notify,
            "check_onlyonce": False,
            "check_cron": self._check_cron,
            "last_status": self._last_status,
            "last_run": self._last_run,
            "last_cookie_count": self._last_cookie_count,
            "last_check": self._last_check,
            "last_check_status": self._last_check_status,
            "openlist_enabled": self._openlist_enabled,
            "openlist_auto_sync": self._openlist_auto_sync,
            "openlist_sync_after_relogin": self._openlist_sync_after_relogin,
            "openlist_sync_onlyonce": False,
            "openlist_url": self._openlist_url,
            "openlist_token": self._openlist_token,
            "openlist_storage_id": self._openlist_storage_id,
            "last_openlist_sync": self._last_openlist_sync,
            "last_openlist_sync_status": self._last_openlist_sync_status,
        }

    def get_page(self) -> Optional[List[dict]]:
        """Vue 模式下详情页由联邦 Page 组件渲染。"""
        return None

    def __api_qrcode_image(self):
        qrcode = self.get_data("qrcode") or ""
        data, media_type = self.__decode_data_image(qrcode)
        if not data:
            return Response(
                content=b"qrcode not ready",
                media_type="text/plain",
                status_code=404,
                headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
            )
        return Response(
            content=data,
            media_type=media_type,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )

    @staticmethod
    def __decode_data_image(data_image: str) -> Tuple[Optional[bytes], str]:
        if not data_image or not str(data_image).startswith("data:image/"):
            return None, "image/png"
        try:
            header, raw = str(data_image).split(",", 1)
            media_type = "image/png"
            if ":" in header and ";" in header:
                media_type = header.split(":", 1)[1].split(";", 1)[0] or media_type
            return base64.b64decode(raw), media_type
        except Exception:
            return None, "image/png"

    @eventmanager.register(EventType.PluginAction)
    def plugin_action(self, event: Event):
        if not self._enabled:
            return
        event_data = event.event_data if event else None
        if not event_data:
            return
        action = event_data.get("action")
        if action == "weiyun_login":
            logger.info("微云 Cookie 助手收到远程命令：/weiyun_login")
            started = self.__start_login_thread(source="command")
            if started:
                self.__post_mp_notification(
                    title="微云登录已启动",
                    text="正在生成微云登录二维码，请稍候。",
                    enabled=self._notify_login_result,
                )
            else:
                self.__post_mp_notification(
                    title="微云登录任务正在运行",
                    text="已有微云扫码登录任务在运行，请稍后等待二维码或登录结果。",
                    enabled=self._notify_login_result,
                )
        elif action == "weiyun_status":
            logger.info("微云 Cookie 助手收到远程命令：/weiyun_status")
            cookie = self.get_data("cookie") or ""
            status_lines = [
                f"运行状态：{'运行中' if self._login_running else '空闲'}",
                f"登录方式：{'QQ' if self._login_type == 'qq' else '微信'}",
                f"Cookie 状态：{'已保存' if cookie else '未保存'}",
                f"Cookie 数量：{self._last_cookie_count}",
                f"上次登录：{self._last_run or '从未'}",
                f"上次检测：{self._last_check or '从未'}",
                f"检测结果：{self._last_check_status}",
                f"OpenList 同步：{self._last_openlist_sync_status}",
            ]
            self.__post_mp_notification(
                title="微云 Cookie 状态",
                text="\n".join(status_lines),
                enabled=True,
            )
        elif action == "weiyun_check":
            logger.info("微云 Cookie 助手收到远程命令：/weiyun_check")
            result = self.check_cookie_validity(source="command")
            valid = result.get("valid", False)
            message = result.get("message", "未知结果")
            self.__post_mp_notification(
                title=f"微云 Cookie {'有效' if valid else '失效'}",
                text=message,
                enabled=True,
            )

    def __api_start_login(self) -> Dict[str, Any]:
        logger.info("微云 Cookie 助手收到立即运行请求：login_type=%s", self._login_type)
        started = self.__start_login_thread(source="api")
        if not started:
            return {"success": False, "message": "扫码登录任务正在运行，请稍后刷新状态"}
        return {"success": True, "message": "已启动微云扫码登录，请刷新插件详情页查看二维码"}

    def __api_status(self) -> Dict[str, Any]:
        cookie = self.get_data("cookie") or ""
        qrcode = self.get_data("qrcode") or ""
        browser_mode = self._browser_mode or "playwright"
        return {
            "success": True,
            "enabled": self._enabled,
            "running": self._login_running,
            "login_type": self._login_type,
            "login_type_title": self.__login_type_title(),
            "browser_mode": browser_mode,
            "browser_mode_title": "兼容模式" if browser_mode == "cloakbrowser" else "插件内置",
            "last_status": self._last_status,
            "last_run": self._last_run,
            "cookie_count": self._last_cookie_count,
            "has_cookie": bool(cookie),
            "has_qrcode": bool(qrcode),
            "qrcode": qrcode,
            "last_check": self._last_check,
            "last_check_status": self._last_check_status,
            "check_cron": self._check_cron,
            "last_openlist_sync": self._last_openlist_sync,
            "last_openlist_sync_status": self._last_openlist_sync_status,
            "cookie": cookie,
        }

    def __api_clear_cookie(self) -> Dict[str, Any]:
        logger.info("微云 Cookie 助手收到清除 Cookie 请求")
        self.del_data("cookie")
        self.del_data("cookies_json")
        self.del_data("qrcode")
        self.del_data("cookie_invalid_notified")
        self.del_data("openlist_sync_after_relogin_pending")
        self._last_cookie_count = 0
        self._last_check_status = "未检测"
        self._last_status = "已清除 Cookie"
        self._last_run = self.__now()
        self.__update_config()
        logger.info("微云 Cookie 助手已清除 Cookie 数据")
        return {"success": True, "message": "已清除微云 Cookie"}

    def __api_check_cookie(self) -> Dict[str, Any]:
        logger.info("微云 Cookie 助手收到立即检测请求")
        result = self.check_cookie_validity(source="api")
        return {"success": True, **result}

    def __api_sync_openlist(self) -> Dict[str, Any]:
        logger.info("微云 Cookie 助手收到 OpenList 同步请求")
        result = self.sync_cookie_to_openlist(source="api")
        return {"success": result.get("success", False), **result}

    def sync_cookie_to_openlist(self, source: str = "manual") -> Dict[str, Any]:
        """将插件保存的完整 Cookie 写入 OpenList 指定存储。"""
        self._last_openlist_sync = self.__now()
        cookie = self.get_data("cookie") or ""
        if not self._openlist_enabled:
            self._last_openlist_sync_status = "未启用 OpenList 同步"
            self.__update_config()
            return {"success": False, "message": self._last_openlist_sync_status}
        if not cookie:
            self._last_openlist_sync_status = "未保存 Cookie，无法同步"
            self.__update_config()
            return {"success": False, "message": self._last_openlist_sync_status}
        if not self._openlist_url:
            self._last_openlist_sync_status = "未配置 OpenList 地址"
            self.__update_config()
            return {"success": False, "message": self._last_openlist_sync_status}
        if not self._openlist_token:
            self._last_openlist_sync_status = "未配置 OpenList Token"
            self.__update_config()
            return {"success": False, "message": self._last_openlist_sync_status}
        try:
            storage = self.__openlist_get_storage(self._openlist_storage_id)
            updated = self.__openlist_set_cookie_field(storage, cookie)
            self.__openlist_update_storage(updated)
            self._last_openlist_sync_status = f"同步成功：已更新 OpenList 存储 {self._openlist_storage_id} 的 Cookie"
            logger.info("微云 Cookie 助手 OpenList 同步成功：source=%s, storage_id=%s", source, self._openlist_storage_id)
            self.__post_mp_notification(
                title="微云 Cookie 已同步到 OpenList",
                text=f"已将最新微云 Cookie 写入 OpenList 存储 {self._openlist_storage_id}。",
                enabled=self._notify_openlist_result,
            )
            self.__update_config()
            return {"success": True, "message": self._last_openlist_sync_status}
        except Exception as err:
            self._last_openlist_sync_status = f"同步失败：{err}"
            logger.error("微云 Cookie 助手 OpenList 同步失败：%s\n%s", err, traceback.format_exc())
            self.__post_mp_notification(
                title="微云 Cookie 同步 OpenList 失败",
                text=f"同步到 OpenList 存储 {self._openlist_storage_id} 失败：{err}",
                enabled=self._notify_openlist_result,
            )
            self.__update_config()
            return {"success": False, "message": self._last_openlist_sync_status}

    def __openlist_headers(self) -> Dict[str, str]:
        return {
            "Authorization": self._openlist_token,
            "Content-Type": "application/json;charset=utf-8",
            "Accept": "application/json, text/plain, */*",
        }

    def __openlist_request(self, method: str, path: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        base = (self._openlist_url or "").rstrip("/")
        url = f"{base}{path}"
        body = None
        headers = self.__openlist_headers()
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=body, headers=headers, method=method.upper())
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

    def __openlist_get_storage(self, storage_id: int) -> Dict[str, Any]:
        candidates = [
            ("GET", f"/api/admin/storage/get?id={storage_id}", None),
            ("GET", f"/api/admin/storage/detail?id={storage_id}", None),
            ("POST", "/api/admin/storage/get", {"id": storage_id}),
            ("POST", "/api/admin/storage/detail", {"id": storage_id}),
        ]
        errors = []
        for method, path, data in candidates:
            try:
                result = self.__openlist_request(method, path, data)
                storage = result.get("data")
                if isinstance(storage, dict):
                    return storage
            except Exception as err:
                errors.append(str(err))
        raise RuntimeError("无法读取 OpenList 存储详情：" + " | ".join(errors[-2:]))

    def __openlist_update_storage(self, storage: Dict[str, Any]) -> None:
        storage_id = storage.get("id") or storage.get("ID") or self._openlist_storage_id
        candidates = [
            ("POST", "/api/admin/storage/update", storage),
            ("PUT", "/api/admin/storage/update", storage),
            ("POST", f"/api/admin/storage/update?id={storage_id}", storage),
        ]
        errors = []
        for method, path, data in candidates:
            try:
                self.__openlist_request(method, path, data)
                return
            except Exception as err:
                errors.append(str(err))
        raise RuntimeError("无法更新 OpenList 存储：" + " | ".join(errors[-2:]))

    def __openlist_set_cookie_field(self, storage: Dict[str, Any], cookie: str) -> Dict[str, Any]:
        updated = json.loads(json.dumps(storage, ensure_ascii=False))
        # OpenList/Alist 驱动配置常见字段：addition 是 JSON 字符串，可能包含 cookie/Cookie。
        for key in ("addition", "Addition"):
            if key in updated:
                addition = updated.get(key)
                if isinstance(addition, str):
                    try:
                        addition_obj = json.loads(addition or "{}")
                    except Exception:
                        addition_obj = {}
                    addition_obj = self.__set_cookie_in_mapping(addition_obj, cookie)
                    updated[key] = json.dumps(addition_obj, ensure_ascii=False)
                    return updated
                if isinstance(addition, dict):
                    updated[key] = self.__set_cookie_in_mapping(addition, cookie)
                    return updated
        updated = self.__set_cookie_in_mapping(updated, cookie)
        return updated

    @staticmethod
    def __set_cookie_in_mapping(mapping: Dict[str, Any], cookie: str) -> Dict[str, Any]:
        if not isinstance(mapping, dict):
            mapping = {}
        lower_map = {str(k).lower(): k for k in mapping.keys()}
        target = lower_map.get("cookie") or lower_map.get("cookies") or lower_map.get("ck") or "cookie"
        mapping[target] = cookie
        return mapping

    def check_cookie_validity(self, source: str = "scheduler") -> Dict[str, Any]:
        """检测已保存 Cookie 是否仍然有效，失效时只通知一次。"""
        cookie = self.get_data("cookie") or ""
        self._last_check = self.__now()
        logger.info("微云 Cookie 助手开始检测 Cookie 有效性：source=%s, has_cookie=%s", source, bool(cookie))
        if not cookie:
            self._last_check_status = "未保存 Cookie，请先扫码登录"
            self.__update_config()
            return {"valid": False, "message": self._last_check_status}
        try:
            valid, message = self.__probe_cookie(cookie)
            self._last_check_status = message
            if valid:
                self.del_data("cookie_invalid_notified")
                logger.info("微云 Cookie 助手检测通过：%s", message)
            else:
                logger.warning("微云 Cookie 助手检测到 Cookie 失效：%s", message)
                self._last_status = "Cookie 已失效，请重新登录"
                if self._openlist_enabled and self._openlist_sync_after_relogin:
                    self.save_data("openlist_sync_after_relogin_pending", True)
                self.__notify_cookie_invalid(message)
            self.__update_config()
            return {"valid": valid, "message": message}
        except Exception as err:
            self._last_check_status = f"检测失败：{err}"
            logger.error("微云 Cookie 助手检测失败：%s\n%s", err, traceback.format_exc())
            self.__update_config()
            return {"valid": False, "message": self._last_check_status}

    def __probe_cookie(self, cookie: str) -> Tuple[bool, str]:
        names = self.__cookie_names(cookie)
        if not names.intersection({"TOK", "wyctoken", "p_skey", "pt4_token", "skey", "uin", "uid", "weiyun_wx_access_token"}):
            return False, "Cookie 缺少微云登录关键字段"
        request = Request(
            "https://www.weiyun.com/disk",
            headers={
                "Cookie": cookie,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.1",
            },
        )
        with urlopen(request, timeout=20) as response:
            status = getattr(response, "status", 200)
            final_url = response.geturl() or ""
            body = response.read(512 * 1024).decode("utf-8", errors="ignore")
        low_url = final_url.lower()
        low_body = body.lower()
        if status in {401, 403}:
            return False, f"微云返回未授权状态：HTTP {status}"
        if "ptlogin" in low_url or "login" in low_url and "weiyun.com/disk" not in low_url:
            return False, f"访问微云时被跳转到登录页：{final_url}"
        invalid_markers = ["请登录", "登录微云", "扫码登录", "账号密码登录", "login_frame", "ptlogin"]
        if any(marker.lower() in low_body for marker in invalid_markers) and not ({"TOK", "wyctoken", "uid"}.intersection(names)):
            return False, "微云页面提示需要重新登录"
        return True, f"Cookie 有效，微云页面响应正常（HTTP {status}）"

    @staticmethod
    def __cookie_names(cookie: str) -> set:
        names = set()
        for part in str(cookie or "").split(";"):
            if "=" not in part:
                continue
            name = part.split("=", 1)[0].strip()
            if name:
                names.add(name)
        return names

    def __post_mp_notification(
            self,
            title: str,
            text: str,
            enabled: bool = True,
            image: Optional[str] = None,
            link: Optional[str] = None,
            file_path: Optional[str] = None) -> None:
        if not self._notify_enabled or not enabled:
            return
        try:
            self.post_message(
                mtype=NotificationType.Plugin,
                title=title,
                text=text,
                image=image,
                link=link,
                file_path=file_path,
            )
            logger.info("微云 Cookie 助手已发送 MP 通知：%s", title)
        except Exception as err:
            logger.error("微云 Cookie 助手发送 MP 通知失败：%s", err, exc_info=True)

    def __notify_qrcode(self, qrcode: str, login_type: str, source: str) -> None:
        if source not in {"command", "api", "onlyonce"}:
            return
        image_url = self.__qrcode_image_url(public=bool(self._qrcode_public_base_url))
        text = f"请使用{self.__login_type_title(login_type)}扫描下方二维码完成登录。登录成功后插件会自动保存 Cookie，并按配置同步到 OpenList。"
        if image_url:
            text = f"{text}\n\n如果图片无法显示，请点击链接查看二维码：\n{image_url}"
        # 将 base64 二维码保存为临时文件，通过 file_path 发送确保 TG 拿到正确图片
        qrcode_file = self.__save_qrcode_tempfile(qrcode)
        self.__post_mp_notification(
            title="微云扫码登录",
            text=text,
            enabled=self._notify_login_result,
            image=image_url or None,
            link=image_url or None,
            file_path=qrcode_file,
        )

    def __save_qrcode_tempfile(self, qrcode: str) -> Optional[str]:
        """将 base64 二维码保存为临时 PNG 文件，返回文件路径。"""
        if not qrcode:
            return None
        try:
            data, _ = self.__decode_data_image(qrcode)
            if not data:
                return None
            data_path = self.get_data_path()
            if data_path:
                temp_dir = Path(data_path) / "qrcache"
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_file = temp_dir / "qrcode.png"
                temp_file.write_bytes(data)
                logger.info("微云 Cookie 助手已保存二维码临时文件：%s", temp_file)
                return str(temp_file)
        except Exception as err:
            logger.error("微云 Cookie 助手保存二维码临时文件失败：%s", err)
        return None

    def __save_qrcode_tempfile(self, qrcode: str) -> Optional[str]:
        """将 base64 二维码保存为临时 PNG 文件，返回文件路径。"""
        if not qrcode:
            return None
        try:
            data, _ = self.__decode_data_image(qrcode)
            if not data:
                return None
            data_path = self.get_data_path()
            if data_path:
                temp_dir = Path(data_path) / "qrcache"
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_file = temp_dir / "qrcode.png"
                temp_file.write_bytes(data)
                logger.info("微云 Cookie 助手已保存二维码临时文件：%s", temp_file)
                return str(temp_file)
        except Exception as err:
            logger.error("微云 Cookie 助手保存二维码临时文件失败：%s", err)
        return None

    def __qrcode_image_url(self, public: bool = False) -> str:
        try:
            path = f"/api/v1/plugin/{self.__class__.__name__}/qrcode_image?apikey={settings.API_TOKEN}&ts={int(time.time())}"
            if public and self._qrcode_public_base_url:
                return f"{self._qrcode_public_base_url}{path}"
            port = getattr(settings, "PORT", 3001) or 3001
            return f"http://192.168.5.100:{port}{path}"
        except Exception:
            return ""

    def __qrcode_image_path(self) -> str:
        return f"/api/v1/plugin/{self.__class__.__name__}/qrcode_image?apikey={settings.API_TOKEN}"

    def __qrcode_auto_hide_html(self) -> str:
        image_path = self.__qrcode_image_path()
        src = f"{image_path}&ts={int(time.time())}"
        poll_src = image_path
        return f"""
<div id=\"weiyun-qrcode-box\" style=\"text-align:center;margin:16px 0;\">
  <img id=\"weiyun-qrcode-img\" src=\"{src}\" alt=\"微云登录二维码\"
       style=\"max-width:320px;width:100%;background:#fff;\"
       onload=\"if(!window.__weiyunQrTimer){{window.__weiyunQrTimer=setInterval(function(){{var box=document.getElementById('weiyun-qrcode-box');var img=document.getElementById('weiyun-qrcode-img');if(!box||!img){{clearInterval(window.__weiyunQrTimer);window.__weiyunQrTimer=null;return;}}var probe=new Image();probe.onload=function(){{img.src='{poll_src}&ts='+Date.now();}};probe.onerror=function(){{box.style.display='none';clearInterval(window.__weiyunQrTimer);window.__weiyunQrTimer=null;}};probe.src='{poll_src}&ts='+Date.now();}},3000);}}\" />
</div>
"""

    def __notify_cookie_invalid(self, reason: str) -> None:
        if not self._check_notify:
            return
        if self.get_data("cookie_invalid_notified"):
            logger.info("微云 Cookie 助手已提醒过 Cookie 失效，本次不重复通知")
            return
        self.__post_mp_notification(
            title="微云 Cookie 已失效",
            text=f"检测到微云 Cookie 可能已失效。你可以在机器人里发送 /weiyun_login 重新扫码登录。\n原因：{reason}",
            enabled=self._check_notify,
        )
        self.save_data("cookie_invalid_notified", True)

    def __start_login_thread(self, source: str = "manual") -> bool:
        if self._login_running:
            logger.warning("微云 Cookie 助手扫码登录任务已在运行，忽略本次请求：source=%s", source)
            return False
        logger.info("微云 Cookie 助手准备启动扫码登录线程：source=%s, login_type=%s", source, self._login_type)
        self._login_thread = threading.Thread(
            target=self.__run_login_flow,
            kwargs={"source": source, "login_type": self._login_type},
            name="WeiyunCookieLogin",
            daemon=True,
        )
        self._login_thread.start()
        return True

    def __run_login_flow(self, source: str = "manual", login_type: str = "qq") -> None:
        logger.info("微云 Cookie 助手扫码登录流程开始：source=%s, login_type=%s", source, login_type)
        self._login_running = True
        self._last_run = self.__now()
        self._last_status = "正在启动 Chromium 浏览器"
        self.del_data("qrcode")
        self.__update_config()
        browser = None
        context = None
        playwright = None
        try:
            if self._browser_mode == "cloakbrowser":
                context = self.__launch_cloakbrowser_context()
            else:
                if sync_playwright is None:
                    raise RuntimeError("当前环境未安装 Playwright，无法启动后端浏览器")
                logger.info("微云 Cookie 助手启动 Playwright Chromium：headless=%s", self._headless)
                playwright = sync_playwright().start()
                browser = playwright.chromium.launch(headless=bool(self._headless), args=self.__browser_args())
                context = browser.new_context(locale="zh-CN", viewport={"width": 1280, "height": 900})
            page = context.new_page()
            logger.info("微云 Cookie 助手打开登录页：%s", self._login_url)
            page.goto(self._login_url, wait_until="domcontentloaded", timeout=60000)
            logger.info("微云 Cookie 助手登录页加载完成：url=%s", page.url)
            self.__select_login_type(page, login_type)
            self.__wait_qrcode_ready(page, login_type)
            qrcode = self.__capture_qrcode(page)
            self.save_data("qrcode", qrcode)
            logger.info("微云 Cookie 助手已生成二维码截图，等待扫码：timeout=%s 秒", self._timeout_seconds)
            self.__notify_qrcode(qrcode, login_type, source)
            self._last_status = f"已生成{self.__login_type_title(login_type)}二维码，请扫码登录"
            self.__update_config()

            deadline = datetime.now() + timedelta(seconds=self._timeout_seconds)
            extracted: List[Dict[str, Any]] = []
            last_url = page.url
            while datetime.now() < deadline:
                cookies = context.cookies()
                extracted = self.__filter_cookies(cookies)
                cookie_names = {c.get("name") for c in extracted}
                if page.url != last_url:
                    logger.info("微云 Cookie 助手检测到页面跳转：%s -> %s", last_url, page.url)
                    last_url = page.url
                if self.__looks_logged_in(cookie_names, page.url):
                    logger.info("微云 Cookie 助手检测到疑似登录 Cookie：count=%s, url=%s", len(extracted), page.url)
                    break
                try:
                    if page.locator("text=退出").count() or page.locator("text=上传").count():
                        logger.info("微云 Cookie 助手检测到登录后页面元素")
                        break
                except Exception:
                    pass
                time.sleep(2)
            else:
                raise TimeoutError("等待扫码登录超时，未检测到有效微云登录 Cookie")

            extracted = self.__filter_cookies(context.cookies())
            cookie_string = self.__cookies_to_header(extracted)
            if not cookie_string:
                raise RuntimeError("已结束等待，但未提取到 weiyun.com/qq.com Cookie")
            logger.info(
                "微云 Cookie 助手准备保存 Cookie：count=%s, names=%s",
                len(extracted),
                ",".join([str(c.get("name")) for c in extracted[:30]]),
            )
            self.save_data("cookie", cookie_string)
            self.save_data("cookies_json", extracted)
            self.del_data("qrcode")
            self.del_data("cookie_invalid_notified")
            self._last_cookie_count = len(extracted)
            self._last_check = self.__now()
            self._last_check_status = "扫码后 Cookie 已刷新"
            self._last_status = f"Cookie 提取成功，共 {len(extracted)} 项"
            logger.info("微云 Cookie 提取成功，已保存到插件数据")
            relogin_pending = bool(self.get_data("openlist_sync_after_relogin_pending"))
            if self._openlist_enabled and (self._openlist_auto_sync or (self._openlist_sync_after_relogin and relogin_pending)):
                result = self.sync_cookie_to_openlist(source="relogin_success" if relogin_pending else "login_success")
                if result.get("success"):
                    self.del_data("openlist_sync_after_relogin_pending")
            self.__post_mp_notification(
                title="微云 Cookie 提取成功",
                text=f"已通过{self.__login_type_title(login_type)}提取并保存微云 Cookie，共 {len(extracted)} 项。",
                enabled=self._notify_login_result,
            )
        except Exception as err:
            self._last_status = f"Cookie 提取失败：{err}"
            logger.error("微云 Cookie 提取失败：%s", err, exc_info=True)
            self.__post_mp_notification(
                title="微云 Cookie 提取失败",
                text=f"{self.__login_type_title(login_type)}流程失败：{err}",
                enabled=self._notify_login_result,
            )
        finally:
            try:
                if context:
                    context.close()
                elif browser:
                    browser.close()
                if playwright:
                    playwright.stop()
            except Exception:
                pass
            self._login_running = False
            logger.info("微云 Cookie 助手扫码登录流程结束：status=%s", self._last_status)
            self.__update_config()


    def __launch_cloakbrowser_context(self):
        if cloak_launch_context is None:
            raise RuntimeError("当前环境未安装 CloakBrowser，无法使用 MP CloakBrowser 兼容模式")
        self.__prepare_cloakbrowser_env()
        logger.info("微云 Cookie 助手启动 MP CloakBrowser：headless=%s, cache_dir=%s", self._headless, os.environ.get("CLOAKBROWSER_CACHE_DIR"))
        context = cloak_launch_context(
            headless=bool(self._headless),
            args=self.__browser_args(),
            locale="zh-CN",
            viewport={"width": 1280, "height": 900},
            stealth_args=True,
        )
        try:
            context.set_extra_http_headers({"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.1"})
        except Exception as err:
            logger.debug("微云 Cookie 助手设置 CloakBrowser 请求头失败：%s", err)
        return context

    @staticmethod
    def __browser_args() -> List[str]:
        return [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--lang=zh-CN",
        ]

    @staticmethod
    def __prepare_cloakbrowser_env() -> None:
        """兼容 MoviePilot 容器内置的 /core/.cloakbrowser 内核目录。"""
        if os.environ.get("CLOAKBROWSER_CACHE_DIR") or os.environ.get("CLOAKBROWSER_BINARY_PATH"):
            return
        for cache_dir in (Path("/core/.cloakbrowser"), Path("/moviepilot/.cloakbrowser")):
            if not cache_dir.exists():
                continue
            binaries = sorted(cache_dir.glob("chromium-*/chrome"), reverse=True)
            if binaries:
                os.environ["CLOAKBROWSER_CACHE_DIR"] = str(cache_dir)
                logger.info("微云 Cookie 助手已适配 CloakBrowser 内核目录：%s", cache_dir)
                return

    def __select_login_type(self, page, login_type: str) -> None:
        logger.info("微云 Cookie 助手尝试切换登录方式：%s", login_type)
        candidates = ["QQ登录", "QQ 登录", "帐号密码登录"] if login_type == "qq" else ["微信登录", "微信 登录", "微信扫码"]
        for text in candidates:
            try:
                locator = page.get_by_text(text, exact=False).first
                if locator.count():
                    locator.click(timeout=3000)
                    logger.info("微云 Cookie 助手已点击登录入口：%s", text)
                    time.sleep(1)
                    return
            except Exception as err:
                logger.debug("微云 Cookie 助手点击登录入口失败：%s, err=%s", text, err)
        logger.info("微云 Cookie 助手未找到明确登录入口，保留当前页面二维码")

    def __wait_qrcode_ready(self, page, login_type: str) -> None:
        """等待二维码元素就绪后再截图，避免截到未加载完成的页面。"""
        logger.info("微云 Cookie 助手等待二维码就绪：login_type=%s", login_type)
        deadline = datetime.now() + timedelta(seconds=15)
        while datetime.now() < deadline:
            try:
                if login_type == "qq":
                    qr_selectors = ["img[src*='ptqrshow']", "img[src*='qrcode']", "img[src*='qr']"]
                else:
                    qr_selectors = ["img[src*='qrcode']", "img[src*='qr']", "canvas"]
                for selector in qr_selectors:
                    locator = page.locator(selector).first
                    if locator.count() and locator.bounding_box():
                        logger.info("微云 Cookie 助手二维码元素已就绪：selector=%s", selector)
                        time.sleep(0.5)
                        return
                iframe_selectors = ["iframe[src*='ptlogin']", "iframe"]
                for selector in iframe_selectors:
                    locator = page.locator(selector).first
                    if locator.count() and locator.bounding_box():
                        logger.info("微云 Cookie 助手 iframe 登录框已就绪：selector=%s", selector)
                        time.sleep(0.5)
                        return
                time.sleep(0.5)
            except Exception:
                time.sleep(0.5)
        logger.warning("微云 Cookie 助手等待二维码就绪超时，将使用当前页面截图")

    def __capture_qrcode(self, page) -> str:
        selectors = [
            "img[src*='ptqrshow']",
            "img[src*='qr']",
            "canvas",
        ]
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if locator.count():
                    data = locator.screenshot(type="png", timeout=5000)
                    logger.info("微云 Cookie 助手二维码截图命中选择器：%s", selector)
                    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
            except Exception as err:
                logger.debug("微云 Cookie 助手二维码选择器截图失败：%s, err=%s", selector, err)
        frame_selectors = ["iframe[src*='ptlogin']", "iframe"]
        for selector in frame_selectors:
            try:
                locator = page.locator(selector).first
                if locator.count():
                    box = locator.bounding_box()
                    if box:
                        pad = 18
                        clip = {
                            "x": max(box["x"] + box["width"] / 2 - 120, 0),
                            "y": max(box["y"] + box["height"] / 2 - 120, 0),
                            "width": 240,
                            "height": 240,
                        }
                        data = page.screenshot(type="png", clip=clip)
                        logger.info("微云 Cookie 助手二维码截图从 iframe 中心裁剪：%s", selector)
                        return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
            except Exception as err:
                logger.debug("微云 Cookie 助手 iframe 二维码裁剪失败：%s, err=%s", selector, err)
        data = page.screenshot(type="png", clip={"x": 440, "y": 180, "width": 360, "height": 360})
        logger.info("微云 Cookie 助手未命中二维码元素，已裁剪页面中心区域")
        return "data:image/png;base64," + base64.b64encode(data).decode("ascii")

    def __filter_cookies(self, cookies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for cookie in cookies or []:
            domain = str(cookie.get("domain") or "").lstrip(".").lower()
            if domain.endswith("weiyun.com") or (self._include_qq_domain and domain.endswith("qq.com")):
                result.append(cookie)
        return result

    @staticmethod
    def __cookies_to_header(cookies: List[Dict[str, Any]]) -> str:
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

    @staticmethod
    def __looks_logged_in(cookie_names: set, url: str) -> bool:
        important = {"uin", "skey", "p_skey", "pt4_token", "wxuin", "wxsid", "qqmusic_uin"}
        if cookie_names.intersection(important) and "login" not in str(url).lower():
            return True
        return False

    def __update_config(self):
        self.update_config({
            "enabled": self._enabled,
            "onlyonce": False,
            "headless": self._headless,
            "login_type": self._login_type,
            "login_url": self._login_url,
            "browser_mode": self._browser_mode,
            "timeout_seconds": self._timeout_seconds,
            "include_qq_domain": self._include_qq_domain,
            "notify_enabled": self._notify_enabled,
            "notify_login_result": self._notify_login_result,
            "notify_openlist_result": self._notify_openlist_result,
            "qrcode_public_base_url": self._qrcode_public_base_url,
            "check_enabled": self._check_enabled,
            "check_notify": self._check_notify,
            "check_onlyonce": False,
            "check_cron": self._check_cron,
            "last_status": self._last_status,
            "last_run": self._last_run,
            "last_cookie_count": self._last_cookie_count,
            "last_check": self._last_check,
            "last_check_status": self._last_check_status,
            "openlist_enabled": self._openlist_enabled,
            "openlist_auto_sync": self._openlist_auto_sync,
            "openlist_sync_after_relogin": self._openlist_sync_after_relogin,
            "openlist_sync_onlyonce": False,
            "openlist_url": self._openlist_url,
            "openlist_token": self._openlist_token,
            "openlist_storage_id": self._openlist_storage_id,
            "last_openlist_sync": self._last_openlist_sync,
            "last_openlist_sync_status": self._last_openlist_sync_status,
        })

    @staticmethod
    def __to_int(value: Any, default: int, min_value: int, max_value: int) -> int:
        try:
            number = int(value)
        except Exception:
            number = default
        return max(min_value, min(max_value, number))

    @staticmethod
    def __normalize_login_type(value: Any) -> str:
        value = str(value or "qq").strip().lower()
        if value in {"wechat", "wx", "weixin", "微信"}:
            return "wechat"
        return "qq"

    def __login_type_title(self, login_type: Optional[str] = None) -> str:
        login_type = self.__normalize_login_type(login_type or self._login_type)
        return "微信扫码登录" if login_type == "wechat" else "QQ扫码登录"

    @staticmethod
    def __normalize_browser_mode(value: Any) -> str:
        value = str(value or "playwright").strip().lower()
        if value in {"cloak", "cloakbrowser", "mp", "mp_cloakbrowser"}:
            return "cloakbrowser"
        return "playwright"

    @staticmethod
    def __now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def stop_service(self) -> None:
        pass
