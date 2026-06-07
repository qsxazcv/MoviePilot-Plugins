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

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import NotificationType

from app.plugins.programpreview import preview_core


class ProgramPreview(_PluginBase):
    plugin_name = "四大平台节目预告"
    plugin_desc = "抓取爱奇艺、腾讯视频、芒果TV、优酷即将上线/预约节目，支持爱奇艺搜索页兜底补齐漏项与预约数，并按 Cron 周期推送通知。"
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Plugins/main/icons/notice.png"
    plugin_version = "1.0.2"
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
        return []

    def get_service(self) -> List[Dict[str, Any]]:
        if self._enabled and self._cron:
            try:
                return [{
                    "id": "ProgramPreview",
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

    def run_preview(self):
        start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("开始执行四大平台节目预告")
        try:
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

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        version = getattr(settings, "VERSION_FLAG", "v1")
        cron_component = "VCronField" if version == "v2" else "VTextField"
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VSwitch", "props": {"model": "notify", "label": "开启通知"}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VSwitch", "props": {"model": "force_notify", "label": "每次强制推送"}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VSwitch", "props": {"model": "onlyonce", "label": "立即运行一次"}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [{"component": cron_component, "props": {"model": "cron", "label": "执行周期 Cron", "placeholder": "0 8 * * *", "hint": "例如：0 8 * * * 表示每天 08:00；30 21 * * * 表示每天 21:30", "persistent-hint": True}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VTextField", "props": {"model": "last_run", "label": "上次运行", "readonly": True}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VTextField", "props": {"model": "last_status", "label": "运行状态", "readonly": True}}]},
                            {"component": "VCol", "props": {"cols": 12}, "content": [{"component": "VAlert", "props": {"type": "info", "variant": "tonal", "text": "保存配置后，插件会按 Cron 自动执行。抓取规则沿用现有四大平台节目预告逻辑。"}}]},
                        ],
                    }
                ],
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "notify": True,
            "force_notify": True,
            "cron": "0 8 * * *",
            "last_run": self._last_run,
            "last_status": self._last_status,
        }

    @staticmethod
    def _read_latest_preview() -> str:
        """读取最近一次节目预告结果，用于插件详情页展示。"""
        try:
            path = getattr(preview_core, "OUT_FILE", Path("/config/plugins/programpreview/latest_preview.md"))
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

    def get_page(self) -> List[dict]:
        latest_preview = self._read_latest_preview()
        return [
            {
                "component": "VCard",
                "props": {"variant": "outlined", "class": "mb-3"},
                "content": [
                    {
                        "component": "VCardTitle",
                        "text": "四大平台节目预告结果",
                    },
                    {
                        "component": "VCardSubtitle",
                        "text": f"上次运行：{self._last_run or '未运行'}｜状态：{self._last_status or '未知'}",
                    },
                    {
                        "component": "VCardText",
                        "content": [
                            {
                                "component": "VTextarea",
                                "props": {
                                    "model-value": self._preview_to_textarea(latest_preview),
                                    "readonly": True,
                                    "auto-grow": True,
                                    "rows": 18,
                                    "variant": "outlined",
                                    "label": "最新节目预告",
                                },
                            }
                        ],
                    },
                ],
            }
        ]

    def stop_service(self) -> None:
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    getattr(self._scheduler, "shutdown")()
                self._scheduler = None
        except Exception as err:
            logger.error(f"退出四大平台节目预告插件失败：{err}")
