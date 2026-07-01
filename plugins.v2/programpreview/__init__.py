# -*- coding: utf-8 -*-
"""四大平台节目预告 MoviePilot 本地插件。"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import asyncio
import threading
import traceback

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import BackgroundTasks

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import NotificationType



class programpreview(_PluginBase):
    plugin_name = "四大平台节目预告"
    plugin_desc = "聚合爱奇艺、腾讯视频、芒果TV、优酷新片预告，按上线日期排序，带类型标签推送即将上线/预约节目。"
    plugin_icon = "https://raw.githubusercontent.com/qsxazcv/MoviePilot-Plugins/main/icons/programpreview.png"
    plugin_version = "1.0.47"
    plugin_author = "qsxazcv"
    author_url = "https://github.com/qsxazcv/MoviePilot-Plugins"
    plugin_config_prefix = "programpreview_"
    plugin_order = 26
    auth_level = 1

    _enabled: bool = False
    _onlyonce: bool = False
    _notify: bool = True
    _force_notify: bool = True
    _cron: str = "0 8 * * *"
    _last_run: str = ""
    _last_status: str = "未运行"
    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):
        self.stop_service()
        if config:
            self._enabled = bool(config.get("enabled", False))
            self._onlyonce = bool(config.get("onlyonce", False))
            self._notify = bool(config.get("notify", True))
            self._force_notify = bool(config.get("force_notify", True))
            self._cron = config.get("cron") or "0 8 * * *"
            self._last_run = config.get("last_run") or ""
            self._last_status = config.get("last_status") or "未运行"

        if self._onlyonce:
            try:
                self._onlyonce = False
                self._last_status = "立即运行已触发"
                self._update_config()
                threading.Thread(
                    target=self.run_preview,
                    name="ProgramPreviewOnce",
                    daemon=True,
                ).start()
                logger.info("四大平台节目预告立即运行任务已提交")
            except Exception as err:
                logger.error(f"四大平台节目预告立即运行启动失败：{err}")
                self._last_status = f"立即运行启动失败：{err}"
                self._update_config()

    def get_state(self) -> bool:
        return self._enabled

    def _update_config(self):
        self.update_config({
            "enabled": self._enabled,
            "onlyonce": False,
            "notify": self._notify,
            "force_notify": self._force_notify,
            "cron": self._cron,
            "last_run": self._last_run,
            "last_status": self._last_status,
        })

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/status",
                "endpoint": self.__api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "查询四大平台节目预告状态",
            },
            {
                "path": "/run",
                "endpoint": self.__api_run,
                "methods": ["POST", "GET"],
                "auth": "bear",
                "summary": "立即执行四大平台节目预告",
            },
        ]

    def __api_status(self) -> Dict[str, Any]:
        return {
            "success": True,
            "enabled": self._enabled,
            "notify": self._notify,
            "force_notify": self._force_notify,
            "cron": self._cron,
            "last_run": self._last_run,
            "last_status": self._last_status,
            "latest_preview": self._read_latest_preview(),
        }

    def __api_run(self) -> Dict[str, Any]:
        threading.Thread(target=self.run_preview, name="ProgramPreviewApiRun", daemon=True).start()
        self._last_status = "立即运行已触发"
        self._update_config()
        return {"success": True, "message": "已提交四大平台节目预告任务"}

    def get_service(self) -> List[Dict[str, Any]]:
        if self._enabled and self._cron:
            try:
                return [{
                    "id": "programpreview",
                    "name": "四大平台节目预告",
                    "trigger": CronTrigger.from_crontab(self._cron),
                    "func": self.run_preview,
                    "kwargs": {},
                }]
            except Exception as err:
                logger.error(f"四大平台节目预告 Cron 配置错误：{err}")
                self._last_status = f"Cron 配置错误：{err}"
                self._update_config()
        return []

    @staticmethod
    def _load_preview_core():
        # 安装/重装时运行目录可能正在分批复制文件，热加载会抢在
        # preview_core.py 完整落盘前导入插件。使用 importlib 按完整模块名
        # 懒加载，避免 `from . import preview_core` 在包半初始化状态下
        # 被 Python 误判为 circular import。若遇到半初始化残留，清理后
        # 再尝试一次，保证插件主体加载不受影响。
        import importlib
        import sys
        module_name = f"{__package__}.preview_core"
        try:
            return importlib.import_module(module_name)
        except ImportError as err:
            if "partially initialized module" not in str(err) and "cannot import name 'preview_core'" not in str(err):
                raise
            sys.modules.pop(module_name, None)
            package = sys.modules.get(__package__)
            if package is not None and hasattr(package, "preview_core"):
                try:
                    delattr(package, "preview_core")
                except Exception:
                    pass
            return importlib.import_module(module_name)

    def run_preview(self):
        start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("开始执行四大平台节目预告")
        try:
            preview_core = self._load_preview_core()
            if self._notify:
                asyncio.run(preview_core.main(force_notify=bool(self._force_notify)))
            else:
                asyncio.run(preview_core.main(force_notify=False))
            self._last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._last_status = "执行成功"
            logger.info(f"四大平台节目预告执行完成，完成时间：{self._last_run}")
        except Exception as err:
            self._last_run = start
            self._last_status = f"执行失败：{err}"
            logger.error(f"四大平台节目预告执行失败：{err}\n{traceback.format_exc()}")
            if self._notify:
                self.post_message(
                    mtype=NotificationType.Plugin,
                    title="四大平台节目预告执行失败",
                    text=str(err),
                )
        finally:
            self._update_config()

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """使用 Vue 联邦组件渲染配置页与详情页。"""
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """Vue 模式下配置页由联邦 Config 组件渲染。"""
        return None, {
            "enabled": self._enabled,
            "onlyonce": False,
            "notify": self._notify,
            "force_notify": self._force_notify,
            "cron": self._cron,
            "last_run": self._last_run,
            "last_status": self._last_status,
        }

    def get_page(self) -> Optional[List[dict]]:
        """Vue 模式下详情页由联邦 Page 组件渲染。"""
        return None

    @classmethod
    def _read_latest_preview(cls) -> str:
        """读取最近一次节目预告结果，用于插件详情页展示。"""
        try:
            try:
                preview_core = cls._load_preview_core()
                path = getattr(preview_core, "OUT_FILE", Path("/config/plugins/programpreview/latest_preview.md"))
            except Exception:
                path = Path("/config/plugins/programpreview/latest_preview.md")
            path = Path(path)
            if not path.exists():
                return "暂无节目预告结果，请先点击“立即运行一次”或等待定时任务执行。"
            text = path.read_text("utf-8").strip()
            return text or "暂无节目预告结果，请先点击“立即运行一次”或等待定时任务执行。"
        except Exception as err:
            return f"读取节目预告结果失败：{err}"

    @staticmethod
    def _preview_to_textarea(text: str) -> str:
        """详情页使用只读文本域展示 Markdown 原文，避免组件不兼容。"""
        return text

    def stop_service(self) -> None:
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    getattr(self._scheduler, "shutdown")()
                self._scheduler = None
        except Exception as err:
            logger.error(f"退出四大平台节目预告插件失败：{err}")
