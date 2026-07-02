from datetime import datetime, timedelta
from threading import Lock
import re
import traceback

try:
    from version import APP_VERSION
except Exception:
    APP_VERSION = ""

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter

from app.core.config import settings
from app.core.plugin import PluginManager
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.plugin import PluginHelper
from app.plugins import _PluginBase
from typing import Any, List, Dict, Tuple, Optional
from app.log import logger
from app.schemas.types import SystemConfigKey
from app.schemas import NotificationType
from app.scheduler import Scheduler
from app.schemas.types import EventType
from app.core.event import eventmanager, Event

router = APIRouter()


class PluginAutoUpdate(_PluginBase):
    # 插件名称
    plugin_name = "插件更新管理"
    # 插件描述
    plugin_desc = "监测已安装插件，推送更新提醒，可配置自动更新"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/thsrite/MoviePilot-Plugins/main/icons/pluginupdate.png"
    # 插件版本
    plugin_version = "2.0.5"
    # 插件作者
    plugin_author = "thsrite"
    # 作者主页
    author_url = "https://github.com/thsrite/MoviePilot-Plugins"
    # 插件配置项ID前缀
    plugin_config_prefix = "pluginautoupdate_"
    # 加载顺序
    plugin_order = 97
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    # 任务执行间隔
    _cron = None
    _onlyonce = False
    _update = False
    _notify = False
    _msgtype = None
    _update_ids = []
    _exclude_ids = []

    # 定时器
    _scheduler: Optional[BackgroundScheduler] = None
    _plugin_version = {}
    _update_lock = Lock()
    _waiting_notified = set()
    _waiting_updates_data_key = "waiting_updates"

    def init_plugin(self, config: dict = None):
        # 停止现有任务
        self.stop_service()

        if config:
            self._enabled = config.get("enabled")
            self._cron = config.get("cron")
            self._onlyonce = config.get("onlyonce")
            self._update = config.get("update")
            self._notify = config.get("notify")
            self._msgtype = config.get("msgtype")
            self._update_ids = config.get("update_ids")
            self._exclude_ids = config.get("exclude_ids")

        if self._enabled:
            # 定时服务
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)

            if self._cron:
                try:
                    self._scheduler.add_job(func=self.plugin_update,
                                            trigger=CronTrigger.from_crontab(self._cron),
                                            id="pluginautoupdate_cron",
                                            name="插件自动更新",
                                            replace_existing=True,
                                            max_instances=1,
                                            coalesce=True)
                except Exception as err:
                    logger.error(f"定时任务配置错误：{str(err)}")

            if self._onlyonce:
                logger.info(f"插件自动更新服务启动，立即运行一次")
                # 关闭一次性开关
                self._onlyonce = False
                self.update_config({
                    "onlyonce": self._onlyonce,
                    "cron": self._cron,
                    "enabled": self._enabled,
                    "update": self._update,
                    "notify": self._notify,
                    "msgtype": self._msgtype,
                    "update_ids": self._update_ids,
                    "exclude_ids": self._exclude_ids,
                })

                self._scheduler.add_job(func=self.plugin_update, trigger='date',
                                        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=1),
                                        id="pluginautoupdate_once",
                                        name="插件自动更新",
                                        replace_existing=True,
                                        max_instances=1)

            # 启动任务
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    @eventmanager.register(EventType.PluginAction)
    def plugin_update(self, event: Event = None):
        """
        插件自动更新
        """
        if not self._enabled:
            logger.error("插件未开启")
            return

        update_forced: bool = False
        if event:
            event_data = event.event_data
            if not event_data or event_data.get("action") != "plugin_update":
                return
            logger.info("收到命令，开始插件更新 ...")
            update_forced = True
            self.post_message(channel=event.event_data.get("channel"),
                              title="开始插件更新 ...",
                              userid=event.event_data.get("user"))

        if not self._update_lock.acquire(blocking=False):
            logger.warning("已有插件更新任务正在运行，本次跳过，避免重复更新和重复通知")
            return

        logger.info("插件更新任务开始")
        try:
            self.__plugin_update(event=event, update_forced=update_forced)
        except Exception as err:
            logger.error(f"插件更新任务异常：{str(err)} - {traceback.format_exc()}")
        finally:
            self._update_lock.release()

    def __plugin_update(self, event: Event = None, update_forced: bool = False):
        # 已安装插件
        install_plugins = SystemConfigOper().get(SystemConfigKey.UserInstalledPlugins) or []

        # 在线插件
        online_plugins = PluginManager().get_online_plugins()
        if not online_plugins:
            logger.error("未获取到在线插件，停止运行")
            return

        # 使用字典来存储每个插件的最大版本号
        max_versions = {}
        for plugin in online_plugins:
            if plugin.id not in max_versions or plugin.plugin_version > max_versions[plugin.id]:
                max_versions[plugin.id] = plugin.plugin_version
        # 根据最大版本号来筛选数据
        online_plugins = [plugin for plugin in online_plugins if
                          plugin.plugin_version == max_versions[plugin.id]]

        # 已安装插件版本
        self.__get_install_plugin_version()

        # 系统运行的服务
        schedulers = Scheduler().list()
        running_scheduler = []
        for scheduler in schedulers:
            if scheduler.status == "正在运行":
                running_scheduler.append(scheduler.id)

        title = None
        current_system_version = self._get_current_system_version()
        # 支持更新的插件自动更新
        for plugin in online_plugins:
            # 只处理已安装的插件
            if str(plugin.id) in install_plugins:
                # 有更新 或者 本地未安装的
                if plugin.has_update or not plugin.installed:
                    # 已安装插件版本
                    install_plugin_version = self._plugin_version.get(str(plugin.id))
                    if not install_plugin_version or str(install_plugin_version) == "None":
                        continue

                    version_text = f"更新版本：v{install_plugin_version} -> v{plugin.plugin_version}"

                    # 自动更新
                    if self._update or update_forced:
                        # 判断是否是排除插件
                        if self._exclude_ids and str(plugin.id) in self._exclude_ids:
                            logger.info(f"插件 {plugin.plugin_name} 已被排除自动更新，跳过")
                            continue
                        # 判断是否是已选择插件
                        if self._update_ids and str(plugin.id) not in self._update_ids:
                            logger.info(f"插件 {plugin.plugin_name} 不在自动更新列表中，跳过")
                            continue
                        if not self._is_system_version_compatible(plugin, current_system_version):
                            waiting = self._build_waiting_update(plugin, install_plugin_version,
                                                                 current_system_version)
                            title = waiting["title"]
                            logger.warning(waiting["log"])
                            self.__send_waiting_notify(waiting)
                            continue
                        waiting_dedupe_key = None
                        waiting_entry = None
                        if self._get_system_version_requirement(plugin)[1]:
                            waiting_for_success = self._build_waiting_update(plugin, install_plugin_version,
                                                                              current_system_version)
                            waiting_dedupe_key = waiting_for_success.get("dedupe_key")
                            waiting_entry = self.__get_waiting_update(waiting_dedupe_key)
                        # 判断当前要升级的插件是否正在运行，正在运行则暂不更新
                        if plugin.id in running_scheduler:
                            msg = f"插件 {plugin.plugin_name} 正在运行，跳过自动升级，最新版本 v{plugin.plugin_version}"
                            logger.info(msg)
                            title = msg
                            continue
                        else:
                            # 下载安装
                            state, msg = PluginHelper().install(pid=plugin.id,
                                                                repo_url=plugin.repo_url)
                            # 安装失败
                            if not state:
                                waiting = self._build_waiting_update_from_install_message(
                                    plugin=plugin,
                                    install_plugin_version=install_plugin_version,
                                    current_system_version=current_system_version,
                                    install_message=msg
                                )
                                if waiting:
                                    title = waiting["title"]
                                    logger.warning(waiting["log"])
                                    self.__send_waiting_notify(waiting)
                                    continue
                                title = f"插件 {plugin.plugin_name} 更新失败"
                                logger.error(f"{title} {version_text}，原因：{msg}")
                            else:
                                title = f"插件 {plugin.plugin_name} 更新成功"
                                logger.info(f"{title} {version_text}")

                                if waiting_entry:
                                    self.__send_recovered_notify(plugin=plugin,
                                                                 install_plugin_version=install_plugin_version,
                                                                 waiting_entry=waiting_entry)
                                    self.__clear_waiting_update(waiting_dedupe_key)
                                else:
                                    self.__send_notify(title=title, plugin=plugin, version_text=version_text)

                                # 加载插件到内存
                                PluginManager().reload_plugin(plugin.id)
                                # 注册插件服务
                                Scheduler().update_plugin_job(plugin.id)
                                # 注册插件API
                                self.register_plugin_api(plugin.id)
                    else:
                        title = f"插件 {plugin.plugin_name} 有更新啦"
                        logger.info(f"{title} {version_text}")
                        self.__send_notify(title=title, plugin=plugin, version_text=version_text)

        # 重载插件管理器
        if not title:
            logger.info("所有插件已是最新版本")
            if event:
                event_data = event.event_data
                if not event_data or event_data.get("action") != "plugin_update":
                    return
                self.post_message(channel=event.event_data.get("channel"),
                                  title="所有插件已是最新版本",
                                  userid=event.event_data.get("user"))

        else:
            if '正在运行，跳过自动升级' in title:
                if event:
                    event_data = event.event_data
                    if not event_data or event_data.get("action") != "plugin_update":
                        return
                    self.post_message(channel=event.event_data.get("channel"),
                                      title=title,
                                      userid=event.event_data.get("user"))

    @staticmethod
    def _get_current_system_version() -> str:
        for attr in ("VERSION", "APP_VERSION", "FRONTEND_VERSION"):
            version = getattr(settings, attr, None)
            if version:
                return str(version)
        if APP_VERSION:
            return str(APP_VERSION)
        version_flag = str(getattr(settings, "VERSION_FLAG", "") or "")
        match = re.search(r"MoviePilot/([0-9][0-9A-Za-z.\-_]*)", version_flag)
        if match:
            return f"v{match.group(1)}"
        return ""

    @staticmethod
    def _normalize_version(version) -> List[int]:
        """提取版本号数字，用于比较 v2.13.16 与 2.13.17 这类格式。"""
        if not version:
            return []
        return [int(item) for item in re.findall(r"\d+", str(version))]

    @classmethod
    def _get_system_version_requirement(cls, plugin) -> Tuple[str, str]:
        """解析 MoviePilot 版本约束，兼容 2.13.17、>=2.13.17、>2.13.16 和提示文本。"""
        candidates = [
            str(getattr(plugin, "system_version", "") or "").strip(),
            str(getattr(plugin, "system_version_message", "") or "").strip(),
        ]
        for candidate in candidates:
            if not candidate:
                continue
            match = re.search(r"(>=|<=|>|<|==|=)\s*v?([0-9][0-9A-Za-z.\-_]*)", candidate)
            if match:
                operator = "==" if match.group(1) == "=" else match.group(1)
                return operator, match.group(2)
            match = re.search(r"v?([0-9]+(?:[.\-_][0-9A-Za-z]+)*)", candidate)
            if match:
                return ">=", match.group(1)
        return "", ""

    @staticmethod
    def _format_system_version_requirement(operator: str, version: str) -> str:
        if not version:
            return "当前 MoviePilot 版本不满足插件要求"
        return f"MoviePilot {operator or '>='} {version}"

    @classmethod
    def _compare_version(cls, current, required) -> int:
        current_parts = cls._normalize_version(current)
        required_parts = cls._normalize_version(required)
        length = max(len(current_parts), len(required_parts))
        current_parts += [0] * (length - len(current_parts))
        required_parts += [0] * (length - len(required_parts))
        if current_parts == required_parts:
            return 0
        return 1 if current_parts > required_parts else -1

    @classmethod
    def _is_system_version_compatible(cls, plugin, current_system_version) -> bool:
        if getattr(plugin, "system_version_compatible", None) is False:
            return False
        operator, required = cls._get_system_version_requirement(plugin)
        if not required:
            return True
        compare_result = cls._compare_version(current_system_version, required)
        if operator == ">":
            return compare_result > 0
        if operator == "<":
            return compare_result < 0
        if operator == "<=":
            return compare_result <= 0
        if operator == "==":
            return compare_result == 0
        return compare_result >= 0

    @classmethod
    def _build_waiting_update(cls, plugin, install_plugin_version, current_system_version,
                              system_version_requirement: str = None) -> Dict[str, str]:
        if system_version_requirement:
            operator, required = cls._get_system_version_requirement(
                type("PluginRequirement", (), {
                    "system_version": system_version_requirement,
                    "system_version_message": ""
                })()
            )
        else:
            operator, required = cls._get_system_version_requirement(plugin)
        requirement_text = cls._format_system_version_requirement(operator, required)
        current = str(current_system_version or "").lstrip("v")
        target = str(getattr(plugin, "plugin_version", "") or "").lstrip("v")
        current_plugin = str(install_plugin_version or "").lstrip("v")
        plugin_name = getattr(plugin, "plugin_name", getattr(plugin, "id", "未知插件"))
        plugin_id = getattr(plugin, "id", plugin_name)
        version_text = f"更新版本：v{current_plugin} -> v{target}"
        text = (
            f"检测到 {plugin_name} 新版本 v{target}，但该版本要求 {requirement_text}。\n\n"
            f"当前 MoviePilot 版本：{current}\n"
            f"当前插件版本：v{current_plugin}\n"
            f"待更新版本：v{target}\n\n"
            "已暂缓本次更新。MoviePilot 升级到兼容版本后，将在下次自动更新任务中继续更新。"
        )
        dedupe_requirement = f"{operator or '>='}{required}" if required else "incompatible"
        return {
            "title": f"插件更新暂缓：{plugin_name}",
            "text": text,
            "log": (
                f"插件 {plugin_name} 暂缓更新：v{current_plugin} -> v{target}，"
                f"要求 {requirement_text}，当前版本 {current}，等待 MoviePilot 版本兼容后自动更新"
            ),
            "dedupe_key": f"{plugin_id}:{target}:mp{dedupe_requirement}",
            "plugin_id": str(plugin_id),
            "plugin_name": str(plugin_name),
            "current_plugin_version": current_plugin,
            "target_plugin_version": target,
            "system_requirement": requirement_text,
            "current_system_version": current,
            "version_text": version_text,
        }

    @classmethod
    def _build_waiting_update_from_install_message(
            cls,
            plugin,
            install_plugin_version,
            current_system_version,
            install_message: str
    ) -> Optional[Dict[str, str]]:
        if not install_message:
            return None
        match = re.search(r"MoviePilot\s*版本\s*(>=|<=|>|<|==|=)\s*v?([0-9][0-9A-Za-z.\-_]*)",
                          str(install_message))
        if not match:
            return None
        operator = "==" if match.group(1) == "=" else match.group(1)
        return cls._build_waiting_update(
            plugin,
            install_plugin_version,
            current_system_version,
            system_version_requirement=f"{operator}{match.group(2)}"
        )

    @staticmethod
    def __now_text() -> str:
        return datetime.now(tz=pytz.timezone(settings.TZ)).strftime("%Y-%m-%d %H:%M:%S")

    def __load_waiting_updates(self) -> Dict[str, Dict[str, Any]]:
        try:
            data = self.get_data(self._waiting_updates_data_key) or {}
        except Exception as err:
            logger.warning(f"读取暂缓更新记录失败：{str(err)}")
            return {}
        if not isinstance(data, dict):
            return {}
        return data

    def __save_waiting_updates(self, updates: Dict[str, Dict[str, Any]]):
        try:
            self.save_data(self._waiting_updates_data_key, updates)
        except Exception as err:
            logger.warning(f"保存暂缓更新记录失败：{str(err)}")

    def __get_waiting_update(self, dedupe_key: str) -> Optional[Dict[str, Any]]:
        if not dedupe_key:
            return None
        return self.__load_waiting_updates().get(dedupe_key)

    def __clear_waiting_update(self, dedupe_key: str):
        if not dedupe_key:
            return
        updates = self.__load_waiting_updates()
        if dedupe_key in updates:
            updates.pop(dedupe_key, None)
            self.__save_waiting_updates(updates)
        self._waiting_notified.discard(dedupe_key)

    def __send_waiting_notify(self, waiting: Dict[str, str]):
        dedupe_key = waiting.get("dedupe_key")
        updates = self.__load_waiting_updates()
        now = self.__now_text()
        entry = updates.get(dedupe_key) or {}
        already_notified = bool(entry.get("notified")) or dedupe_key in self._waiting_notified
        entry.update({
            "plugin_id": waiting.get("plugin_id"),
            "plugin_name": waiting.get("plugin_name"),
            "current_plugin_version": waiting.get("current_plugin_version"),
            "target_plugin_version": waiting.get("target_plugin_version"),
            "system_requirement": waiting.get("system_requirement"),
            "first_system_version": entry.get("first_system_version") or waiting.get("current_system_version"),
            "last_system_version": waiting.get("current_system_version"),
            "first_seen": entry.get("first_seen") or now,
            "last_seen": now,
            "notified": bool(entry.get("notified")),
        })
        updates[dedupe_key] = entry
        self.__save_waiting_updates(updates)

        if already_notified:
            return
        if self._notify:
            mtype = NotificationType.Manual
            if self._msgtype:
                mtype = NotificationType.__getitem__(str(self._msgtype)) or NotificationType.Manual
            self.post_message(title=waiting["title"], mtype=mtype, text=waiting["text"])
            entry["notified"] = True
            entry["notified_at"] = now
            updates[dedupe_key] = entry
            self.__save_waiting_updates(updates)
            self._waiting_notified.add(dedupe_key)

    def __send_recovered_notify(self, plugin, install_plugin_version, waiting_entry: Dict[str, Any] = None):
        if not self._notify:
            return
        plugin_name = getattr(plugin, "plugin_name", getattr(plugin, "id", "未知插件"))
        target = str(getattr(plugin, "plugin_version", "") or "").lstrip("v")
        current_plugin = str(install_plugin_version or "").lstrip("v")
        current_system_version = self._get_current_system_version().lstrip("v")
        requirement = (waiting_entry or {}).get("system_requirement") or "MoviePilot 版本要求"
        first_system_version = (waiting_entry or {}).get("first_system_version")
        text = (
            f"{plugin_name} 已恢复更新并安装成功：v{current_plugin} -> v{target}\n\n"
            "之前因 MoviePilot 版本不兼容暂缓更新。\n"
            f"兼容要求：{requirement}\n"
            f"当前 MoviePilot 版本：{current_system_version}"
        )
        if first_system_version:
            text += f"\n首次暂缓时 MoviePilot 版本：{first_system_version}"
        mtype = NotificationType.Manual
        if self._msgtype:
            mtype = NotificationType.__getitem__(str(self._msgtype)) or NotificationType.Manual
        self.post_message(title=f"插件恢复更新成功：{plugin_name}", mtype=mtype, text=text)

    def __send_notify(self, title: str, plugin, version_text: str):
        # 发送通知
        if self._notify:
            mtype = NotificationType.Manual
            if self._msgtype:
                mtype = NotificationType.__getitem__(str(self._msgtype)) or NotificationType.Manual
            plugin_icon = plugin.plugin_icon
            if not str(plugin_icon).startswith("http"):
                plugin_icon = f"https://raw.githubusercontent.com/jxxghp/MoviePilot-Plugins/main/icons/{plugin_icon}"
            if plugin.history:
                for verison in plugin.history.keys():
                    if str(verison).replace("v", "") == str(plugin.plugin_version).replace("v", ""):
                        version_text += f"\n更新记录：{plugin.history[verison]}"
            self.post_message(title=title,
                              mtype=mtype,
                              text=version_text,
                              image=plugin_icon)

    def __get_install_plugin_version(self):
        """
        获取已安装插件版本
        """
        # 本地插件
        local_plugins = PluginManager().get_local_plugins()
        for plugin in local_plugins:
            self._plugin_version[plugin.id] = plugin.plugin_version

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [{
            "cmd": "/plugin_update",
            "event": EventType.PluginAction,
            "desc": "插件更新",
            "category": "",
            "data": {
                "action": "plugin_update"
            }
        }]

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    @staticmethod
    def register_plugin_api(plugin_id: str = None):
        """
        注册插件API（先删除后新增）
        """
        try:
            from app.api.endpoints.plugin import register_plugin_api as register_api

            register_api(plugin_id)
            return
        except Exception as err:
            logger.warning(f"调用系统插件API注册失败，尝试兼容注册：{err}")

        apis: List[Dict[str, Any]] = []
        for api in PluginManager().get_plugin_apis():
            if plugin_id in api.get("path"):
                apis.append(api)

        for api in apis:
            for r in router.routes:
                if r.path == api.get("path"):
                    router.routes.remove(r)
                    break
            route_api = dict(api)
            route_api.pop("allow_anonymous", None)
            route_api.pop("auth", None)
            router.add_api_route(**route_api)

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        # 编历 NotificationType 枚举，生成消息类型选项
        MsgTypeOptions = []
        for item in NotificationType:
            MsgTypeOptions.append({
                "title": item.value,
                "value": item.name
            })

        # 已安装插件
        local_plugins = PluginManager().get_local_plugins()
        # 编历 local_plugins，生成插件类型选项
        pluginOptions = []

        for plugin in local_plugins:
            if not plugin.installed:
                continue
            pluginOptions.append({
                "title": f"{plugin.plugin_name} v{plugin.plugin_version}",
                "value": plugin.id
            })
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'update',
                                            'label': '自动更新',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'notify',
                                            'label': '发送通知',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cron',
                                            'label': '监测周期',
                                            'placeholder': '5位cron表达式'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'multiple': False,
                                            'chips': True,
                                            'model': 'msgtype',
                                            'label': '消息类型',
                                            'items': MsgTypeOptions
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'multiple': True,
                                            'chips': True,
                                            'model': 'update_ids',
                                            'label': '更新插件',
                                            'items': pluginOptions
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'multiple': True,
                                            'chips': True,
                                            'model': 'exclude_ids',
                                            'label': '排除插件',
                                            'items': pluginOptions
                                        }
                                    }
                                ]
                            },
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '已安装的插件自动更新最新版本。'
                                                    '如未开启自动更新则发送更新通知。'
                                                    '如更新插件正在运行，则本次跳过更新。'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '所有已安装插件均会检查更新，发送通知。'
                                                    '更新插件/排除插件仅针对于自动更新场景。'
                                                    '如未选择更新插件，则默认为自动更新所有。'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "update": False,
            "notify": False,
            "cron": "",
            "msgtype": "",
            "update_ids": [],
            "exclude_ids": [],
        }

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        """
        退出插件
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            pass
            # logger.error("退出插件失败：%s" % str(e))
