import builtins
import json
import os
import shlex
import subprocess
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel, Field

from app.agent.tools.base import MoviePilotTool
from app.agent.tools.tags import ToolTag
from app.core.event import Event, eventmanager
from app.core.plugin import PluginManager
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType

from .ikuai_client import IkuaiClient, extract_items, find_client, mask_secret, summarize_rule


class IkuaiAssistant(_PluginBase):
    """ikuai-cli助手插件。"""

    plugin_name = "ikuai-cli助手"
    plugin_desc = "iKuai 路由器命令行工具 — 在终端管理网络、用户、VPN、防火墙等。"
    plugin_icon = "https://www.ikuai8.com/favicon.ico"
    plugin_version = "1.0.0"
    plugin_label = "网络,诊断,爱快"
    plugin_author = "qsxazcv"
    plugin_config_prefix = "ikuaiassistant_"
    plugin_order = 96
    auth_level = 1

    _enabled = False
    _base_url = ""
    _token = ""
    _verify_ssl = False
    _timeout = 10
    _cli_path = "ikuai-cli"
    _allow_cli_write = False

    def init_plugin(self, config: dict = None) -> None:
        """读取插件配置并初始化运行状态。"""
        config = config or {}
        was_enabled = bool(self._enabled)
        self._enabled = bool(config.get("enabled"))
        self._base_url = str(config.get("base_url") or "").strip()
        self._token = str(config.get("token") or "").strip()
        self._verify_ssl = bool(config.get("verify_ssl"))
        self._timeout = int(config.get("timeout") or 10)
        self._cli_path = str(config.get("cli_path") or "ikuai-cli").strip()
        self._allow_cli_write = bool(config.get("allow_cli_write"))
        if was_enabled and not self._enabled:
            logger.info(
                "ikuai-cli助手停止/关闭服务: "
                f"enabled={self._enabled}, base_url={self._base_url or '未配置'}, "
                f"allow_cli_write={self._allow_cli_write}"
            )
        if not self._enabled:
            if not was_enabled:
                logger.info(
                    "ikuai-cli助手配置已加载，插件保持关闭: "
                    f"enabled={self._enabled}, base_url={self._base_url or '未配置'}, "
                    f"token={'已配置' if bool(self._token) else '未配置'}, "
                    f"verify_ssl={self._verify_ssl}, timeout={self._timeout}, "
                    f"allow_cli_write={self._allow_cli_write}"
                )
            return
        self.__prune_stale_plugin_action_handlers()
        logger.info(
            "ikuai-cli助手启动/初始化: "
            f"enabled={self._enabled}, base_url={self._base_url or '未配置'}, "
            f"token={'已配置' if bool(self._token) else '未配置'}, "
            f"verify_ssl={self._verify_ssl}, timeout={self._timeout}, "
            f"allow_cli_write={self._allow_cli_write}"
        )

    def get_state(self) -> bool:
        """返回插件启用状态。"""
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """返回插件远程命令列表。"""
        return [
            {
                "cmd": "/ikuai_system",
                "event": EventType.PluginAction,
                "desc": "查询 ikuai-cli 系统状态",
                "category": "ikuai-cli",
                "data": {"action": "ikuai_system"},
            },
            {
                "cmd": "/ikuai_online",
                "event": EventType.PluginAction,
                "desc": "查询爱快在线设备列表",
                "category": "ikuai-cli",
                "data": {"action": "ikuai_online"},
            },
            {
                "cmd": "/ikuai_dns",
                "event": EventType.PluginAction,
                "desc": "查询爱快 DNS 配置",
                "category": "ikuai-cli",
                "data": {"action": "ikuai_dns"},
            },
            {
                "cmd": "/ikuai_logs",
                "event": EventType.PluginAction,
                "desc": "查询爱快系统日志",
                "category": "ikuai-cli",
                "data": {"action": "ikuai_logs"},
            },
            {
                "cmd": "/ikuai_who_busy",
                "event": EventType.PluginAction,
                "desc": "查询当前谁在占网",
                "category": "ikuai-cli",
                "data": {"action": "ikuai_who_busy"},
            },
            {
                "cmd": "/ikuai_routes",
                "event": EventType.PluginAction,
                "desc": "查询爱快分流和负载规则",
                "category": "ikuai-cli",
                "data": {"action": "ikuai_routes"},
            },
            {
                "cmd": "/ikuai_device",
                "event": EventType.PluginAction,
                "desc": "查询单设备详情，用法 /ikuai_device 192.168.5.14",
                "category": "ikuai-cli",
                "data": {"action": "ikuai_device"},
            },
            {
                "cmd": "/ikuai_diag",
                "event": EventType.PluginAction,
                "desc": "综合诊断单设备，用法 /ikuai_diag 192.168.5.14",
                "category": "ikuai-cli",
                "data": {"action": "ikuai_diag"},
            },
        ]

    @staticmethod
    def get_agent_tools() -> List[Type]:
        """返回 MoviePilot AI 可调用的爱快工具。"""
        return [IkuaiCliTool, IkuaiSkillTool]

    def get_api(self) -> List[Dict[str, Any]]:
        """注册爱快诊断 API。"""
        apis = [
            {
                "path": "/capabilities",
                "endpoint": self.__api_capabilities,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "获取 ikuai-cli 命令能力清单",
            },
            {
                "path": "/agent_skill",
                "endpoint": self.__api_agent_skill,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "读取 ikuai-cli 官方 Agent SKILL.md",
            },
            {
                "path": "/agent_skills",
                "endpoint": self.__api_agent_skills,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "列出 ikuai-cli 领域技能文件",
            },
            {
                "path": "/agent_skill_file",
                "endpoint": self.__api_agent_skill_file,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "读取指定 ikuai-cli 领域技能文件",
            },
            {
                "path": "/cli",
                "endpoint": self.__api_cli,
                "methods": ["GET", "POST"],
                "auth": "apikey",
                "summary": "执行受控 ikuai-cli 命令",
            },
            {
                "path": "/refresh_agent_tools",
                "endpoint": self.__api_refresh_agent_tools,
                "methods": ["POST", "GET"],
                "auth": "apikey",
                "summary": "刷新 MoviePilot MCP/AI 工具管理器",
            },
            {
                "path": "/status",
                "endpoint": self.__api_status,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "获取爱快系统和接口状态",
            },
            {
                "path": "/clients",
                "endpoint": self.__api_clients,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "获取在线终端列表",
            },
            {
                "path": "/device",
                "endpoint": self.__api_device,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "按 IP 或 MAC 查询指定终端诊断信息",
            },
            {
                "path": "/rules",
                "endpoint": self.__api_rules,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "获取五元组分流规则列表",
            },
            {
                "path": "/rule",
                "endpoint": self.__api_rule,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "获取指定五元组分流规则摘要",
            },
            {
                "path": "/analyze",
                "endpoint": self.__api_analyze,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "综合分析爱快系统、接口、在线终端和可选指定设备",
            },
            {
                "path": "/set_rule_interface",
                "endpoint": self.__api_set_rule_interface,
                "methods": ["POST", "GET"],
                "auth": "apikey",
                "summary": "切换指定五元组分流规则出口",
            },
            {
                "path": "/toggle_rule",
                "endpoint": self.__api_toggle_rule,
                "methods": ["POST", "GET"],
                "auth": "apikey",
                "summary": "启用或停用指定五元组分流规则",
            },
        ]
        # v3 兼容：保持插件自定义响应格式（{ok: ...}），
        # 绕过宿主 ResponseAPIRoute 的统一 envelope 自动包装
        for _api in apis:
            if isinstance(_api, dict) and "openapi_extra" not in _api:
                _api["openapi_extra"] = {"x-moviepilot-raw-response": True}
        return apis

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """返回插件配置表单与默认配置。"""
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VAlert",
                        "props": {
                            "type": "info",
                            "variant": "tonal",
                            "text": "这里只配置爱快连接和 CLI 桥接信息。设备 IP、MAC、规则 ID 在查询或操作时临时传入，不会固定写死。",
                        },
                    },
                    {
                        "component": "VRow",
                        "props": {"class": "mt-2"},
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                            "color": "primary",
                                            "inset": True,
                                            "hide-details": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "verify_ssl",
                                            "label": "校验 HTTPS 证书",
                                            "color": "primary",
                                            "inset": True,
                                            "hide-details": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "timeout",
                                            "label": "请求超时秒数",
                                            "type": "number",
                                            "min": 1,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "allow_cli_write",
                                            "label": "允许 CLI 写操作",
                                            "color": "warning",
                                            "inset": True,
                                            "hide-details": True,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "base_url",
                                            "label": "爱快地址",
                                            "placeholder": "http://192.168.5.1",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "token",
                                            "label": "API Token",
                                            "type": "password",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                ],
            }
        ], self.__default_config()

    def get_page(self) -> Optional[List[dict]]:
        """返回插件详情页。"""
        if not self._enabled:
            return [
                {
                    "component": "VAlert",
                    "props": {
                        "type": "warning",
                        "variant": "tonal",
                        "text": "插件未启用。请先填写爱快地址和 API Token。",
                    },
                }
            ]
        write_status = "已开启" if self._allow_cli_write else "已关闭"
        write_color = "warning" if self._allow_cli_write else "success"
        return [
            {
                "component": "VCard",
                "props": {"variant": "tonal", "class": "mb-3"},
                "content": [
                    {"component": "VCardTitle", "text": "ikuai-cli助手"},
                    {
                        "component": "VCardText",
                        "text": (
                            "iKuai 路由器命令行工具 — 在终端管理网络、用户、VPN、防火墙等。"
                            "默认按只读方式排查问题；修改路由、规则、用户和系统配置等写操作需要额外开启并二次确认。"
                        ),
                    },
                ],
            },
            {
                "component": "VRow",
                "props": {"class": "mb-3"},
                "content": [
                    self.__status_card("连接状态", "已配置", self._base_url or "未配置爱快地址", "success"),
                    self.__status_card("CLI 状态", "内置可用", "ikuai-cli v1.0.16", "success"),
                    self.__status_card("Agent Skill", "17 个领域", "monitor / network / routing / security", "info"),
                    self.__status_card("写操作保护", write_status, "默认拦截修改类命令", write_color),
                ],
            },
            {
                "component": "VCard",
                "props": {"variant": "outlined", "class": "mb-3"},
                "content": [
                    {"component": "VCardTitle", "text": "AI 可用能力"},
                    {
                        "component": "VCardText",
                        "content": [
                            {
                                "component": "VChip",
                                "props": {"class": "ma-1", "color": "primary", "variant": "tonal"},
                                "text": "系统监控",
                            },
                            {
                                "component": "VChip",
                                "props": {"class": "ma-1", "color": "primary", "variant": "tonal"},
                                "text": "在线设备",
                            },
                            {
                                "component": "VChip",
                                "props": {"class": "ma-1", "color": "primary", "variant": "tonal"},
                                "text": "WAN/路由",
                            },
                            {
                                "component": "VChip",
                                "props": {"class": "ma-1", "color": "primary", "variant": "tonal"},
                                "text": "分流规则",
                            },
                            {
                                "component": "VChip",
                                "props": {"class": "ma-1", "color": "primary", "variant": "tonal"},
                                "text": "安全策略",
                            },
                            {
                                "component": "VChip",
                                "props": {"class": "ma-1", "color": "primary", "variant": "tonal"},
                                "text": "日志分析",
                            },
                            {
                                "component": "VChip",
                                "props": {"class": "ma-1", "color": "primary", "variant": "tonal"},
                                "text": "VPN/无线/QoS",
                            },
                        ],
                    },
                ],
            },
            {
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "tonal",
                    "text": "你可以直接让 AI 分析爱快网络。AI 会先读取 ikuai_skill 官方领域说明，再通过 ikuai_cli 执行只读命令获取证据。",
                },
            },
            {
                "component": "VAlert",
                "props": {
                    "type": "warning",
                    "variant": "tonal",
                    "class": "mt-3",
                    "text": "修改配置、踢用户、启停规则等写操作默认关闭；即使开启，也必须在具体调用时传 confirm=true。",
                },
            },
        ]

    @staticmethod
    def __status_card(title: str, value: str, subtitle: str, color: str) -> Dict[str, Any]:
        """构建详情页状态卡片。"""
        return {
            "component": "VCol",
            "props": {"cols": 12, "sm": 6, "md": 3},
            "content": [
                {
                    "component": "VCard",
                    "props": {"variant": "outlined"},
                    "content": [
                        {
                            "component": "VCardText",
                            "content": [
                                {
                                    "component": "div",
                                    "props": {"class": "text-caption text-medium-emphasis mb-1"},
                                    "text": title,
                                },
                                {
                                    "component": "VChip",
                                    "props": {"color": color, "variant": "tonal", "size": "small", "class": "mb-2"},
                                    "text": value,
                                },
                                {
                                    "component": "div",
                                    "props": {"class": "text-body-2"},
                                    "text": subtitle,
                                },
                            ],
                        }
                    ],
                }
            ],
        }

    def stop_service(self) -> None:
        """停止插件服务。"""
        logger.info(
            "ikuai-cli助手停止/关闭服务: "
            f"enabled={self._enabled}, base_url={self._base_url or '未配置'}, "
            f"allow_cli_write={self._allow_cli_write}"
        )
        return None

    @eventmanager.register(EventType.PluginAction)
    def plugin_action(self, event: Event = None) -> None:
        """处理 Telegram/远程插件命令。"""
        event_data = event.event_data if event else None
        action = event_data.get("action") if event_data else None
        if action not in (
            "ikuai_system",
            "ikuai_online",
            "ikuai_dns",
            "ikuai_logs",
            "ikuai_who_busy",
            "ikuai_routes",
            "ikuai_device",
            "ikuai_diag",
        ):
            return
        if self.__is_duplicate_plugin_action(
            action=action,
            channel=event_data.get("channel"),
            user=event_data.get("user"),
        ):
            if self.__should_log_duplicate_plugin_action(
                action=action,
                channel=event_data.get("channel"),
                user=event_data.get("user"),
            ):
                logger.info(f"ikuai-cli助手忽略重复远程命令: /{action}")
            return
        title = self.__plugin_action_title(action)
        logger.info(f"ikuai-cli助手收到远程命令: /{action}")
        if action == "ikuai_system":
            text = self.__format_system_health_message(
                self.run_cli_command("monitor system"),
                self.run_cli_command("monitor interfaces"),
                self.run_cli_command("monitor clients-online --page-size 200"),
            )
        elif action == "ikuai_online":
            result = self.run_cli_command("monitor clients-online --page-size 200")
            text = self.__format_online_clients_message(result)
        elif action == "ikuai_dns":
            text = self.__format_dns_message(self.run_cli_command("network dns get"))
        elif action == "ikuai_logs":
            text = self.__format_logs_message(self.run_cli_command("log system list --human-time --page-size 20 --order desc --order-by id"))
        elif action == "ikuai_who_busy":
            text = self.__format_who_busy_message(self.run_cli_command("monitor clients-online --page-size 200"))
        elif action == "ikuai_routes":
            text = self.__format_routes_message(
                self.run_cli_command("routing stream five-tuple list --page-size 50"),
                self.run_cli_command("routing stream load-balance list --page-size 50"),
            )
        elif action == "ikuai_device":
            text = self.__handle_device_diagnostics(event_data.get("arg_str"))
        else:
            text = self.__handle_device_diagnostics(event_data.get("arg_str"), diag=True)
        self.post_message(
            channel=event_data.get("channel"),
            userid=event_data.get("user"),
            title=title,
            text=text,
        )

    @staticmethod
    def __is_duplicate_plugin_action(action: str, channel: Any = None, user: Any = None, window_seconds: float = 2.0) -> bool:
        """短时间内同来源的远程命令只处理一次，兜底热重载残留 handler。"""
        lock = getattr(builtins, "_ikuaiassistant_action_lock", None)
        if lock is None:
            lock = Lock()
            setattr(builtins, "_ikuaiassistant_action_lock", lock)
        recent = getattr(builtins, "_ikuaiassistant_recent_actions", None)
        if recent is None:
            recent = {}
            setattr(builtins, "_ikuaiassistant_recent_actions", recent)

        key = (str(action or ""), str(channel or ""), str(user or ""))
        now = time.monotonic()
        with lock:
            last_seen = recent.get(key)
            recent[key] = now
            for stale_key, seen_at in list(recent.items()):
                if now - seen_at > window_seconds * 3:
                    recent.pop(stale_key, None)
            return last_seen is not None and now - last_seen < window_seconds

    @staticmethod
    def __should_log_duplicate_plugin_action(action: str, channel: Any = None, user: Any = None, window_seconds: float = 2.0) -> bool:
        """同一轮重复远程命令只输出一条忽略日志，避免热重载残留 handler 刷屏。"""
        lock = getattr(builtins, "_ikuaiassistant_action_lock", None)
        if lock is None:
            lock = Lock()
            setattr(builtins, "_ikuaiassistant_action_lock", lock)
        duplicate_logs = getattr(builtins, "_ikuaiassistant_duplicate_logs", None)
        if duplicate_logs is None:
            duplicate_logs = {}
            setattr(builtins, "_ikuaiassistant_duplicate_logs", duplicate_logs)

        key = (str(action or ""), str(channel or ""), str(user or ""))
        now = time.monotonic()
        with lock:
            last_logged = duplicate_logs.get(key)
            if last_logged is not None and now - last_logged < window_seconds:
                return False
            duplicate_logs[key] = now
            for stale_key, seen_at in list(duplicate_logs.items()):
                if now - seen_at > window_seconds * 3:
                    duplicate_logs.pop(stale_key, None)
            return True

    @staticmethod
    def __prune_stale_plugin_action_handlers() -> None:
        """清理热重载残留的本插件 PluginAction handler，并保留当前版本一份。"""
        try:
            subscribers = getattr(eventmanager, "_EventManager__broadcast_subscribers", None)
            if not isinstance(subscribers, dict):
                return
            handlers = subscribers.get(EventType.PluginAction)
            if not isinstance(handlers, dict):
                return
            removed = 0
            for identifier in list(handlers.keys()):
                lowered = str(identifier).lower()
                if "ikuaiassistant" in lowered and "plugin_action" in lowered:
                    handlers.pop(identifier, None)
                    removed += 1
            add_listener = getattr(eventmanager, "add_event_listener", None)
            if callable(add_listener):
                add_listener(EventType.PluginAction, IkuaiAssistant.plugin_action)
            if removed > 1:
                logger.info(f"ikuai-cli助手清理重复事件处理器: removed={removed}, kept=1")
        except Exception as err:
            logger.warning(f"ikuai-cli助手清理重复事件处理器失败: {err}")

    def __default_config(self) -> Dict[str, Any]:
        """构建默认配置模型。"""
        return {
            "enabled": False,
            "base_url": "http://192.168.5.1",
            "token": "",
            "verify_ssl": False,
            "timeout": 10,
            "allow_cli_write": False,
        }

    def __client(self) -> IkuaiClient:
        """创建爱快 API 客户端。"""
        return IkuaiClient(
            base_url=self._base_url,
            token=self._token,
            verify_ssl=self._verify_ssl,
            timeout=self._timeout,
        )

    def __disabled(self) -> Dict[str, Any]:
        """返回未启用错误。"""
        return {"ok": False, "error": "插件未启用"}

    def run_cli_command(self, command: str, confirm: bool = False, raw: bool = False) -> Dict[str, Any]:
        """执行受控 ikuai-cli 命令，供 API 和 AI 工具共用。"""
        if not self._enabled:
            logger.warning("ikuai-cli助手执行 CLI 被拒绝: 插件未启用")
            return self.__disabled()
        args = shlex.split(str(command or ""), posix=True)
        if not args:
            logger.warning("ikuai-cli助手执行 CLI 被拒绝: command 为空")
            return {"ok": False, "error": "请传入 command，例如 monitor system"}
        safety = self.__check_cli_command(args)
        if not safety["ok"]:
            logger.warning(f"ikuai-cli助手执行 CLI 被拒绝: command={self.__safe_cli_command(args)}, reason={safety.get('error')}")
            return safety
        if safety["write"] and (not self._allow_cli_write or not confirm):
            logger.warning(
                "ikuai-cli助手拦截 CLI 写操作: "
                f"command={self.__safe_cli_command(args)}, allow_cli_write={self._allow_cli_write}, confirm={confirm}"
            )
            return {
                "ok": False,
                "error": "这是 CLI 写操作，请先在插件配置启用允许 CLI 写操作，并传 confirm=true",
                "command": args,
            }
        run_args = [self.__cli_executable(), *args]
        if "-f" not in args and "--format" not in args:
            run_args.extend(["-f", "json"])
        env = {
            "IKUAI_CLI_BASE_URL": self._base_url,
            "IKUAI_CLI_TOKEN": self.__cli_token(),
        }
        started = time.monotonic()
        try:
            completed = subprocess.run(
                run_args,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                env={**os.environ, **env},
                check=False,
            )
        except Exception as err:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            logger.error(
                "ikuai-cli助手 CLI 执行异常: "
                f"command={self.__safe_cli_command(args)}, elapsed_ms={elapsed_ms}, error={err}",
                exc_info=True,
            )
            return {"ok": False, "error": str(err), "command": args, "executable": run_args[0]}
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        parsed: Any = None
        if stdout and not raw:
            try:
                parsed = json.loads(stdout)
            except json.JSONDecodeError:
                parsed = stdout
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "ikuai-cli助手 CLI 执行完成: "
            f"command={self.__safe_cli_command(args)}, exit_code={completed.returncode}, "
            f"ok={completed.returncode == 0}, elapsed_ms={elapsed_ms}, "
            f"stdout_len={len(stdout)}, stderr_len={len(stderr)}"
        )
        return {
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "command": args,
            "stdout": stdout if raw else None,
            "stderr": stderr,
            "data": parsed,
        }

    def read_agent_skill(self, name: str = "") -> Dict[str, Any]:
        """读取 ikuai-cli 官方 Agent Skill 或领域技能文档。"""
        safe_name = str(name or "").strip().lower().replace("\\", "/").split("/")[-1]
        if not safe_name:
            logger.info("ikuai-cli助手读取 Agent Skill: SKILL.md")
            return self.__read_agent_guide("SKILL.md")
        if not safe_name.endswith(".md"):
            safe_name = f"{safe_name}.md"
        logger.info(f"ikuai-cli助手读取 Agent Skill: skills/{safe_name}")
        return self.__read_agent_guide(f"skills/{safe_name}")

    def list_agent_skills(self) -> Dict[str, Any]:
        """列出 ikuai-cli 官方领域技能文档。"""
        skills_dir = self.__agent_guide_dir() / "skills"
        if not skills_dir.exists():
            logger.warning("ikuai-cli助手列出 Agent Skills 失败: agent_guide/skills 不存在")
            return {"ok": False, "error": "agent_guide/skills 不存在"}
        files = sorted(path.name for path in skills_dir.glob("*.md") if path.is_file())
        logger.info(f"ikuai-cli助手列出 Agent Skills: count={len(files)}")
        return {"ok": True, "skills": files}

    def __cli_executable(self) -> str:
        """返回 ikuai-cli 可执行文件路径，默认优先使用插件内置二进制。"""
        configured = str(self._cli_path or "").strip()
        bundled = Path(__file__).resolve().parent / "bin" / "ikuai-cli"
        if (not configured or configured == "ikuai-cli") and bundled.exists():
            try:
                bundled.chmod(bundled.stat().st_mode | 0o755)
            except Exception as err:
                logger.warning(f"设置 ikuai-cli 执行权限失败: {err}")
            return str(bundled)
        return configured or "ikuai-cli"

    def __cli_token(self) -> str:
        """返回传给 ikuai-cli 的 Token，兼容用户粘贴 Bearer 前缀。"""
        token = str(self._token or "").strip()
        if token.lower().startswith("bearer "):
            return token[7:].strip()
        return token

    def __format_monitor_system_message(self, result: Dict[str, Any]) -> str:
        """把 monitor system 结果整理成适合 Telegram 阅读的摘要。"""
        if not result.get("ok"):
            error = result.get("error") or result.get("stderr") or "未知错误"
            return f"执行命令：monitor system\n执行结果：失败\n错误信息：{str(error)[:800]}"
        data = result.get("data")
        lines = ["执行命令：monitor system", "执行结果：成功"]
        for label, keys in [
            ("CPU", ["cpu", "cpu_usage", "cpu_percent", "cpu_used", "cpuload"]),
            ("内存", ["memory", "mem", "mem_usage", "memory_usage", "mem_percent"]),
            ("运行时间", ["uptime", "run_time", "runtime", "sys_uptime"]),
            ("IP", ["wan_ip", "wanip", "ip_addr", "ip", "external_ip"]),
        ]:
            value = self.__find_first_value(data, keys)
            if value not in (None, ""):
                lines.append(f"{label}：{self.__format_monitor_value(label, value)}")
        if len(lines) == 2:
            preview = json.dumps(data, ensure_ascii=False, indent=2, default=str) if data is not None else ""
            lines.append(f"原始结果：{preview[:1200] or '无数据'}")
        return "\n".join(lines)

    @staticmethod
    def __plugin_action_title(action: str) -> str:
        """返回远程命令回复标题。"""
        return {
            "ikuai_system": "ikuai-cli 系统状态",
            "ikuai_online": "ikuai-cli 在线设备",
            "ikuai_dns": "ikuai-cli DNS 配置",
            "ikuai_logs": "ikuai-cli 系统日志",
            "ikuai_who_busy": "ikuai-cli 谁在占网",
            "ikuai_routes": "ikuai-cli 分流规则",
            "ikuai_device": "ikuai-cli 单设备诊断",
            "ikuai_diag": "ikuai-cli 综合诊断",
        }.get(action, "ikuai-cli 助手")

    def __format_dns_message(self, result: Dict[str, Any]) -> str:
        """格式化 DNS 配置。"""
        if not result.get("ok"):
            return self.__format_generic_result("network dns get", result)
        items = self.__extract_cli_items(result.get("data"))
        config = items[0] if items and isinstance(items[0], dict) else {}
        lines = ["执行命令：network dns get", "执行结果：成功", ""]
        if not config:
            lines.append("无 DNS 配置数据")
            return "\n".join(lines)
        for label, keys in [
            ("启用", ["enabled"]),
            ("主 DNS", ["dns1"]),
            ("备用 DNS", ["dns2"]),
            ("DoH", ["query"]),
            ("强制 DNS", ["proxy_force_dns"]),
            ("缓存 TTL", ["cache_ttl"]),
        ]:
            value = self.__pick_client_value(config, keys)
            if value:
                lines.append(f"{label}：{value}")
        return "\n".join(lines)

    def __format_logs_message(self, result: Dict[str, Any]) -> str:
        """格式化系统日志。"""
        command = "log system list --human-time --page-size 20 --order desc --order-by id"
        if not result.get("ok"):
            return self.__format_generic_result(command, result)
        items = self.__extract_cli_items(result.get("data"))
        lines = [f"执行命令：{command}", "执行结果：成功", ""]
        if not items:
            lines.append("无系统日志")
            return "\n".join(lines)
        for item in items[:12]:
            if not isinstance(item, dict):
                lines.append(str(item)[:180])
                continue
            timestamp = self.__pick_client_value(item, ["timestamp", "time", "datetime", "date"])
            content = self.__pick_client_value(item, ["content", "message", "event", "msg"])
            level = self.__pick_client_value(item, ["level", "type"])
            prefix = "｜".join(part for part in [timestamp, level] if part)
            lines.append(f"{prefix}｜{content}" if prefix else (content or json.dumps(item, ensure_ascii=False, default=str)[:180]))
        if len(items) > 12:
            lines.append(f"仅显示前 12 条，共 {len(items)} 条。")
        return "\n".join(lines)

    def __format_who_busy_message(self, result: Dict[str, Any]) -> str:
        """格式化占网设备。"""
        if not result.get("ok"):
            return self.__format_generic_result("monitor clients-online --page-size 200", result)
        rows = [row for row in self.__extract_cli_items(result.get("data")) if isinstance(row, dict)]
        summaries = [self.__client_summary(row) for row in rows]
        summaries = sorted(summaries, key=lambda row: row["traffic_total"], reverse=True)
        lines = ["执行命令：monitor clients-online --page-size 200", "执行结果：成功", ""]
        if not summaries:
            lines.append("未取得终端流量数据。")
            return "\n".join(lines)
        active = [row for row in summaries if row["traffic_total"] > 0]
        for row in active[:10]:
            name = row["name"] or row["ip"] or "未知设备"
            parts = [name]
            if row["ip"]:
                parts.append(row["ip"])
            parts.append(self.__format_client_traffic(row))
            lines.append("｜".join(parts))
        if not active:
            lines.append("当前没有明显实时流量。")
        return "\n".join(lines)

    def __format_routes_message(self, five_tuple_result: Dict[str, Any], load_balance_result: Dict[str, Any]) -> str:
        """格式化分流和负载规则。"""
        lines = [
            "执行命令：routing stream five-tuple list --page-size 50",
            "执行命令：routing stream load-balance list --page-size 50",
            "执行结果：成功" if five_tuple_result.get("ok") and load_balance_result.get("ok") else "执行结果：部分失败",
            "",
            "五元组分流",
        ]
        lines.extend(self.__format_items_lines(five_tuple_result.get("data"), ["id", "name", "tagname", "interface", "mode", "enabled"], limit=8))
        lines.extend(["", "负载均衡"])
        lines.extend(self.__format_items_lines(load_balance_result.get("data"), ["id", "name", "tagname", "interface", "mode", "enabled"], limit=8))
        return "\n".join(lines)

    def __handle_device_diagnostics(self, arg_str: Any, diag: bool = False) -> str:
        """查询单设备详情和可选综合诊断。"""
        ip = str(arg_str or "").strip().split()[0] if str(arg_str or "").strip() else ""
        if not ip:
            command = "/ikuai_diag <ip>" if diag else "/ikuai_device <ip>"
            return f"请传入设备 IP，例如：{command.replace('<ip>', '192.168.5.14')}"
        clients_result = self.run_cli_command("monitor clients-online --page-size 200")
        clients = self.__extract_cli_items(clients_result.get("data"))
        target = find_client({"data": clients}, ip=ip) or {}
        if not target:
            return f"执行命令：monitor clients-online --page-size 200\n执行结果：成功\n未找到在线设备：{ip}"
        mac = self.__pick_client_value(target, ["mac", "mac_addr", "macaddr"])
        if not mac:
            return f"找到设备 {ip}，但没有 MAC，无法查询 5 分钟流量和协议分布。"
        traffic_result = self.run_cli_command(f"monitor traffic-load --ip {ip} --mac {mac}")
        protocols_result = self.run_cli_command(f"monitor client-protocols --ip {ip} --mac {mac}")
        text = self.__format_device_message(target, traffic_result, protocols_result)
        if diag:
            text += "\n\n诊断结论\n" + self.__format_device_conclusion(target, traffic_result, protocols_result)
        return text

    def __format_device_message(self, target: Dict[str, Any], traffic_result: Dict[str, Any], protocols_result: Dict[str, Any]) -> str:
        """格式化单设备诊断。"""
        row = self.__client_summary(target)
        lines = [
            f"设备：{row['name'] or row['ip']}",
            f"IP：{row['ip']}",
            f"MAC：{row['mac']}",
        ]
        details = [item for item in [row["client_type"], row["interface"], self.__format_client_traffic(row)] if item]
        if details:
            lines.append(f"状态：{'｜'.join(details)}")
        lines.extend(["", "5 分钟流量"])
        lines.extend(self.__format_traffic_load_lines(traffic_result.get("data")))
        lines.extend(["", "协议分布"])
        lines.extend(self.__format_protocol_lines(protocols_result.get("data")))
        return "\n".join(lines)

    def __format_device_conclusion(self, target: Dict[str, Any], traffic_result: Dict[str, Any], protocols_result: Dict[str, Any]) -> str:
        """生成不依赖重点设备配置的单设备诊断结论。"""
        row = self.__client_summary(target)
        if row["traffic_total"] <= 0:
            traffic = "当前实时流量较低。"
        elif row["traffic_total"] < 1024 * 1024:
            traffic = "当前有轻量实时流量。"
        else:
            traffic = "当前实时流量较高。"
        protocol_items = self.__extract_cli_items(protocols_result.get("data"))
        protocol_hint = "协议分布已取得，可结合应用名称判断是否是目标应用流量。" if protocol_items else "未取得明显协议分布。"
        return f"{traffic}\n{protocol_hint}\n若仍卡顿，下一步建议检查 DNS、出口线路和目标应用协议。"

    def __format_traffic_load_lines(self, payload: Any) -> List[str]:
        """格式化单设备 5 分钟流量采样。"""
        samples = []
        if isinstance(payload, dict) and isinstance(payload.get("terminal_stream_collect"), list):
            samples = payload.get("terminal_stream_collect") or []
        else:
            samples = self.__extract_cli_items(payload)
        if not samples:
            return ["无 5 分钟流量采样"]
        lines = []
        for item in samples[-5:]:
            if not isinstance(item, dict):
                continue
            upload = self.__pick_client_number(item, ["upload"])
            download = self.__pick_client_number(item, ["download"])
            conn = self.__pick_client_value(item, ["conn_num", "connect_num"])
            suffix = f"｜连接 {conn}" if conn else ""
            lines.append(f"↑{self.__format_rate(upload)} ↓{self.__format_rate(download)}{suffix}")
        return lines or ["无 5 分钟流量采样"]

    def __format_protocol_lines(self, payload: Any) -> List[str]:
        """格式化单设备协议分布。"""
        items = self.__extract_cli_items(payload)
        if not items:
            return ["无协议分布数据"]
        rows = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = self.__pick_client_value(item, ["proto_name", "app_name", "protocol", "name"]) or "未知协议"
            total = self.__pick_client_number(item, ["total", "download", "sum_total", "bytes"])
            rows.append((total, name))
        rows.sort(reverse=True)
        return [f"{name}｜{self.__format_bytes(total)}" for total, name in rows[:8]] or ["无协议分布数据"]

    def __format_generic_result(self, command: str, result: Dict[str, Any], preferred_keys: Optional[List[str]] = None, limit: int = 12) -> str:
        """通用格式化 CLI JSON 结果。"""
        if not result.get("ok"):
            error = result.get("error") or result.get("stderr") or "未知错误"
            return f"执行命令：{command}\n执行结果：失败\n错误信息：{str(error)[:800]}"
        lines = [f"执行命令：{command}", "执行结果：成功", ""]
        item_lines = self.__format_items_lines(result.get("data"), preferred_keys or [], limit=limit)
        lines.extend(item_lines)
        return "\n".join(lines)

    def __format_items_lines(self, payload: Any, preferred_keys: List[str], limit: int = 10) -> List[str]:
        """把列表/字典结果压成多行摘要。"""
        items = self.__extract_cli_items(payload if isinstance(payload, dict) else {"data": payload})
        if not items and isinstance(payload, dict):
            items = [payload]
        if not items:
            return ["无数据"]
        lines: List[str] = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                lines.append(str(item)[:160])
                continue
            parts = []
            for key in preferred_keys:
                value = self.__pick_client_value(item, [key])
                if value:
                    parts.append(value)
            if not parts:
                for key, value in list(item.items())[:5]:
                    if value not in (None, ""):
                        parts.append(f"{key}={value}")
            lines.append("｜".join(str(part) for part in parts if str(part))[:220] or json.dumps(item, ensure_ascii=False, default=str)[:220])
        if len(items) > limit:
            lines.append(f"仅显示前 {limit} 条，共 {len(items)} 条。")
        return lines

    @staticmethod
    def __extract_cli_items(payload: Any) -> List[Any]:
        """从 ikuai-cli 常见响应结构中提取列表。"""
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []
        for key in ("data", "terminal", "iface_check", "iface_stream", "results", "items", "list"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = IkuaiAssistant.__extract_cli_items(value)
                if nested:
                    return nested
        return []

    def __format_system_health_message(
        self,
        system_result: Dict[str, Any],
        interfaces_result: Dict[str, Any],
        clients_result: Dict[str, Any],
    ) -> str:
        """组合系统、线路和在线设备数据，生成全局体检报告。"""
        if not system_result.get("ok"):
            error = system_result.get("error") or system_result.get("stderr") or "未知错误"
            return f"执行命令：monitor system\n执行结果：失败\n错误信息：{str(error)[:800]}"

        system_data = system_result.get("data") if isinstance(system_result.get("data"), dict) else {}
        sysinfo = system_data.get("sysinfo") if isinstance(system_data.get("sysinfo"), dict) else system_data
        interfaces_data = interfaces_result.get("data") if isinstance(interfaces_result.get("data"), dict) else {}
        clients_data = clients_result.get("data") if isinstance(clients_result.get("data"), dict) else {}
        clients = self.__extract_cli_items(clients_data)

        hostname = self.__find_first_value(sysinfo, ["hostname"]) or "未知"
        version = self.__find_first_value(sysinfo, ["verstring", "version"]) or "未知"
        cpu = self.__find_first_value(sysinfo, ["cpu", "cpu_usage", "cpu_percent"]) or ""
        memory = self.__find_first_value(sysinfo, ["memory", "mem", "memory_usage"]) or ""
        uptime = self.__find_first_value(sysinfo, ["uptime", "run_time", "runtime"]) or ""
        online_count = self.__find_first_value(sysinfo, ["count"]) or self.__find_first_value(clients_data, ["total"]) or len(clients)
        stream = self.__find_first_value(sysinfo, ["stream"]) or {}
        connect_num = self.__find_first_value(stream, ["connect_num"]) if isinstance(stream, dict) else None
        tcp_num = self.__find_first_value(stream, ["tcp_connect_num"]) if isinstance(stream, dict) else None
        udp_num = self.__find_first_value(stream, ["udp_connect_num"]) if isinstance(stream, dict) else None
        icmp_num = self.__find_first_value(stream, ["icmp_connect_num"]) if isinstance(stream, dict) else None
        upload = self.__pick_client_number(stream, ["upload"]) if isinstance(stream, dict) else 0
        download = self.__pick_client_number(stream, ["download"]) if isinstance(stream, dict) else 0

        lines = [
            "执行命令：monitor system + monitor interfaces + monitor clients-online --page-size 200",
            "执行结果：成功",
            "",
            "系统概览",
            f"主机名：{hostname}",
            f"固件版本：{version}",
        ]
        if cpu not in (None, ""):
            lines.append(f"CPU：{self.__format_monitor_value('CPU', cpu)}")
        if memory not in (None, ""):
            lines.append(f"内存：{self.__format_monitor_value('内存', memory)}")
        if connect_num not in (None, ""):
            details = []
            if tcp_num not in (None, ""):
                details.append(f"TCP {tcp_num}")
            if udp_num not in (None, ""):
                details.append(f"UDP {udp_num}")
            if icmp_num not in (None, ""):
                details.append(f"ICMP {icmp_num}")
            suffix = f"（{' / '.join(details)}）" if details else ""
            lines.append(f"连接数：{connect_num}{suffix}")
        lines.append(f"在线设备：{online_count} 台")
        if uptime not in (None, ""):
            lines.append(f"运行时间：{self.__format_monitor_value('运行时间', uptime)}")

        iface_check = interfaces_data.get("iface_check") if isinstance(interfaces_data.get("iface_check"), list) else []
        iface_stream = interfaces_data.get("iface_stream") if isinstance(interfaces_data.get("iface_stream"), list) else []
        lines.extend(["", f"线路检测（{len(iface_check)} 条）"])
        failed_lines = []
        for item in iface_check[:8]:
            if not isinstance(item, dict):
                continue
            interface = self.__pick_client_value(item, ["interface"]) or "未知线路"
            comment = self.__pick_client_value(item, ["comment"]) or "-"
            ip_addr = self.__pick_client_value(item, ["ip_addr"]) or "-"
            result = self.__pick_client_value(item, ["result"])
            ok = result.lower() in ("success", "ok", "true", "1")
            status = "成功" if ok else (self.__pick_client_value(item, ["errmsg"]) or "异常")
            if not ok:
                failed_lines.append(interface)
            lines.append(f"{interface}｜{comment}｜{ip_addr}｜{status}")

        lines.extend(["", "实时流量"])
        lines.append(f"全网实时：↑{self.__format_rate(upload)} ↓{self.__format_rate(download)}")
        active_interfaces = [
            item for item in iface_stream
            if isinstance(item, dict) and self.__pick_client_number(item, ["upload"]) + self.__pick_client_number(item, ["download"]) > 0
        ]
        if active_interfaces:
            top_interface = max(
                active_interfaces,
                key=lambda item: self.__pick_client_number(item, ["upload"]) + self.__pick_client_number(item, ["download"]),
            )
            lines.append(
                "主力线路："
                f"{self.__pick_client_value(top_interface, ['interface']) or '未知'} "
                f"↑{self.__format_rate(self.__pick_client_number(top_interface, ['upload']))} "
                f"↓{self.__format_rate(self.__pick_client_number(top_interface, ['download']))}"
            )
        active_clients = sorted(
            [self.__client_summary(item) for item in clients if isinstance(item, dict) and self.__client_summary(item)["traffic_total"] > 0],
            key=lambda row: row["traffic_total"],
            reverse=True,
        )
        active_names = "、".join(row["name"] or row["ip"] for row in active_clients[:3])
        lines.append(f"活跃来源：{active_names or '未见明显活跃设备'}")

        cpu_percent = self.__max_percent(cpu)
        memory_percent = self.__max_percent(self.__find_first_value(memory, ["used"]) if isinstance(memory, dict) else memory)
        system_status = "正常"
        if cpu_percent >= 90 or memory_percent >= 90:
            system_status = "压力很高"
        elif cpu_percent >= 70 or memory_percent >= 80:
            system_status = "负载偏高"
        line_status = "全部在线" if not failed_lines and iface_check else (f"{len(failed_lines)} 条异常：{', '.join(failed_lines)}" if failed_lines else "未取得线路检测数据")
        traffic_status = "未见明显拥塞" if upload + download < 10 * 1024 * 1024 else "全网流量较高"
        lines.extend([
            "",
            "结论",
            f"健康度：{system_status}。",
            f"出口线路：{line_status}。",
            f"网络拥塞：{traffic_status}。",
            "下一步：若某台设备卡顿，建议用 /ikuai_online 找到它，再做单设备协议、DNS 或目标线路分析。",
        ])
        return "\n".join(lines)

    def __format_online_clients_message(self, result: Dict[str, Any]) -> str:
        """把 monitor clients-online 结果整理成适合 Telegram 阅读的在线设备列表。"""
        if not result.get("ok"):
            error = result.get("error") or result.get("stderr") or "未知错误"
            return f"执行命令：monitor clients-online --page-size 200\n执行结果：失败\n错误信息：{str(error)[:800]}"
        data = result.get("data")
        clients = self.__extract_cli_items(data if isinstance(data, dict) else {"data": data})
        total = self.__find_first_value(data, ["total"]) if isinstance(data, dict) else None
        rows = [self.__client_summary(client) for client in clients if isinstance(client, dict)]
        active_rows = [row for row in rows if row["traffic_total"] > 0]
        idle_count = max(len(rows) - len(active_rows), 0)
        lines = [
            "执行命令：monitor clients-online --page-size 200",
            "执行结果：成功",
            f"在线：{total or len(clients)} 台｜活跃：{len(active_rows)}｜空闲：{idle_count}",
        ]
        if not clients:
            preview = json.dumps(data, ensure_ascii=False, indent=2, default=str) if data is not None else ""
            lines.append(f"原始结果：{preview[:1200] or '无在线设备数据'}")
            return "\n".join(lines)

        lines.append("")
        for row in sorted(rows, key=self.__ip_sort_key)[:30]:
            lines.append(self.__format_client_list_row(row))
        if len(rows) > 30:
            lines.append(f"仅显示前 30 台，剩余 {len(rows) - 30} 台可在插件 API 查看。")
        return "\n".join(lines)

    def __client_summary(self, client: Dict[str, Any]) -> Dict[str, Any]:
        """提取在线设备的展示字段。"""
        ip = self.__pick_client_value(client, ["ip_addr", "ip", "ipaddr", "addr"])
        mac = self.__pick_client_value(client, ["mac", "mac_addr", "macaddr"])
        primary_name = self.__pick_client_value(client, ["termname", "hostname", "host", "name", "client_name"])
        comment = self.__pick_client_value(client, ["comment", "remark", "note", "alias"])
        name = self.__format_client_name(primary_name, comment)
        upload = self.__pick_client_number(client, ["upload", "up", "upload_rate", "up_rate", "uprate", "tx_rate", "sum_total_up", "total_up"])
        download = self.__pick_client_number(client, ["download", "down", "download_rate", "down_rate", "downrate", "rx_rate", "sum_total_down", "total_down"])
        interface = self.__pick_client_value(client, ["interface", "ifname"])
        client_type = self.__pick_client_value(client, ["client_type", "type"])
        is_watch = ip == "192.168.5.14" or any(word in name.lower() for word in ["mate80", "huawei", "华为"])
        return {
            "key": ip or mac or name,
            "ip": ip,
            "mac": mac,
            "name": name,
            "upload": upload,
            "download": download,
            "traffic_total": upload + download,
            "interface": interface,
            "client_type": "" if client_type.lower() == "unknown" else client_type,
            "is_watch": is_watch,
        }

    @staticmethod
    def __ip_sort_key(row: Dict[str, Any]) -> Tuple[int, int, int, int, str]:
        """按 IPv4 数字顺序排序，异常 IP 放到最后。"""
        parts = str(row.get("ip") or "").split(".")
        try:
            if len(parts) == 4:
                return tuple(int(part) for part in parts) + ("",)
        except ValueError:
            pass
        return (999, 999, 999, 999, str(row.get("ip") or row.get("name") or ""))

    @staticmethod
    def __format_client_name(primary_name: str, comment: str) -> str:
        """合并设备名和备注，重复时只显示一次。"""
        primary_name = str(primary_name or "").strip()
        comment = str(comment or "").strip()
        if primary_name and comment and primary_name != comment:
            return f"{primary_name}（{comment}）"
        return primary_name or comment

    def __format_client_row(self, row: Dict[str, Any]) -> List[str]:
        """格式化重点/活跃设备的两行展示。"""
        title = f"- {row['ip'] or '未知IP'}"
        if row["name"]:
            title += f"｜{row['name']}"
        details = [item for item in [row["client_type"], row["interface"], self.__format_client_traffic(row)] if item]
        lines = [title]
        if details:
            lines.append(f"  {'｜'.join(details)}")
        if row["mac"]:
            lines.append(f"  MAC {row['mac']}")
        return lines

    def __format_client_compact(self, row: Dict[str, Any]) -> str:
        """格式化其他设备的一行展示。"""
        name = f"｜{row['name']}" if row["name"] else ""
        return f"- {row['ip'] or '未知IP'}{name}｜{self.__format_client_traffic(row)}"

    def __format_client_list_row(self, row: Dict[str, Any]) -> str:
        """格式化纯 IP 排序清单的一行展示。"""
        parts = [row["ip"] or "未知IP"]
        if row["name"]:
            parts.append(row["name"])
        if row["client_type"]:
            parts.append(row["client_type"])
        parts.append(self.__format_client_traffic(row))
        return "｜".join(parts)

    def __format_client_traffic(self, row: Dict[str, Any]) -> str:
        """格式化实时上下行速率。"""
        if row["traffic_total"] <= 0:
            return "空闲"
        return f"↑{self.__format_rate(row['upload'])} ↓{self.__format_rate(row['download'])}"

    @staticmethod
    def __format_rate(value: Any) -> str:
        """把 B/s 数字转成可读速率。"""
        try:
            rate = float(value or 0)
        except (TypeError, ValueError):
            return str(value)
        if rate >= 1024 * 1024:
            return f"{rate / 1024 / 1024:.1f} MB/s"
        if rate >= 1024:
            return f"{rate / 1024:.1f} KB/s"
        return f"{int(rate)} B/s"

    @staticmethod
    def __format_bytes(value: Any) -> str:
        """把字节数转成可读容量。"""
        try:
            size = float(value or 0)
        except (TypeError, ValueError):
            return str(value)
        if size >= 1024 * 1024 * 1024:
            return f"{size / 1024 / 1024 / 1024:.2f} GB"
        if size >= 1024 * 1024:
            return f"{size / 1024 / 1024:.1f} MB"
        if size >= 1024:
            return f"{size / 1024:.1f} KB"
        return f"{int(size)} B"

    @staticmethod
    def __max_percent(value: Any) -> float:
        """从字符串、列表或数字中提取最大百分比。"""
        values = value if isinstance(value, list) else [value]
        percents: List[float] = []
        for item in values:
            text = str(item or "").strip().replace("%", "")
            try:
                percents.append(float(text))
            except (TypeError, ValueError):
                continue
        return max(percents) if percents else 0.0

    @staticmethod
    def __pick_client_value(client: Dict[str, Any], keys: List[str]) -> str:
        """按候选字段名提取在线设备字段。"""
        lowered = {str(key).lower(): value for key, value in client.items()}
        for key in keys:
            value = lowered.get(key.lower())
            if value not in (None, ""):
                return str(value)
        return ""

    @classmethod
    def __pick_client_number(cls, client: Dict[str, Any], keys: List[str]) -> float:
        """按候选字段名提取数值字段。"""
        raw = cls.__pick_client_value(client, keys)
        try:
            return float(raw or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def __format_monitor_value(label: str, value: Any) -> str:
        """格式化 monitor system 的常见字段。"""
        if label == "CPU" and isinstance(value, list):
            values = [str(item) for item in value if str(item).strip()]
            return " / ".join(values[:8])
        if label == "内存" and isinstance(value, dict):
            used = value.get("used")
            total = value.get("total")
            available = value.get("available")
            detail = []
            if used not in (None, ""):
                detail.append(f"使用 {used}")
            if total:
                detail.append(f"总计 {IkuaiAssistant.__format_kib(total)}")
            if available:
                detail.append(f"可用 {IkuaiAssistant.__format_kib(available)}")
            return "，".join(detail) if detail else json.dumps(value, ensure_ascii=False, default=str)
        if label == "运行时间":
            try:
                seconds = int(value)
                days, rem = divmod(seconds, 86400)
                hours, rem = divmod(rem, 3600)
                minutes, _ = divmod(rem, 60)
                parts = []
                if days:
                    parts.append(f"{days}天")
                if hours:
                    parts.append(f"{hours}小时")
                if minutes or not parts:
                    parts.append(f"{minutes}分钟")
                return "".join(parts)
            except (TypeError, ValueError):
                return str(value)
        return str(value)

    @staticmethod
    def __format_kib(value: Any) -> str:
        """把 KiB 数字格式化为 MiB/GiB。"""
        try:
            size = float(value)
        except (TypeError, ValueError):
            return str(value)
        mib = size / 1024
        if mib >= 1024:
            return f"{mib / 1024:.2f} GiB"
        return f"{mib:.2f} MiB"

    @classmethod
    def __find_first_value(cls, payload: Any, keys: List[str]) -> Any:
        """从嵌套 JSON 里按候选字段名查找第一个非空值。"""
        if isinstance(payload, dict):
            lowered = {str(key).lower(): value for key, value in payload.items()}
            for key in keys:
                value = lowered.get(key.lower())
                if value not in (None, ""):
                    return value
            for value in payload.values():
                found = cls.__find_first_value(value, keys)
                if found not in (None, ""):
                    return found
        elif isinstance(payload, list):
            for item in payload:
                found = cls.__find_first_value(item, keys)
                if found not in (None, ""):
                    return found
        return None

    @staticmethod
    def __safe_cli_command(args: List[str]) -> str:
        """返回适合写入日志的 CLI 命令摘要，避免泄露 token 等敏感参数。"""
        sensitive_flags = {"--token", "-t", "--password", "--passwd", "--secret", "--key", "--api-key"}
        safe_args: List[str] = []
        hide_next = False
        for part in args[:8]:
            lowered = part.lower()
            if hide_next:
                safe_args.append("***")
                hide_next = False
                continue
            if lowered in sensitive_flags:
                safe_args.append(part)
                hide_next = True
                continue
            if any(word in lowered for word in ["token=", "password=", "passwd=", "secret=", "api_key=", "apikey="]):
                key = part.split("=", 1)[0]
                safe_args.append(f"{key}=***")
                continue
            safe_args.append(part)
        if len(args) > len(safe_args):
            safe_args.append("...")
        return " ".join(safe_args)

    def __api_capabilities(self) -> Dict[str, Any]:
        """返回 ikuai-cli 主要命令能力清单。"""
        return {
            "ok": True,
            "read_commands": [
                "auth status",
                "monitor *",
                "log *",
                "network * get/list",
                "objects * list/get",
                "qos * list/get",
                "routing * list/get",
                "security * list/get",
                "system * get/list",
                "users online",
                "vpn * list/get/clients",
                "wireless * list/get",
                "version",
            ],
            "write_commands": [
                "auth set-url/set-token/clear",
                "network * create/update/delete/set",
                "objects * create/update/delete",
                "qos * create/update/delete",
                "routing * create/update/delete",
                "security * create/update/delete/set",
                "system set/upgrade/backup/ntp-sync",
                "users kick",
                "vpn * create/update/delete",
                "wireless * create/update/delete/set",
            ],
            "api": [
                "/agent_skill",
                "/agent_skills",
                "/agent_skill_file?name=monitor",
                "/cli?command=monitor system",
                "/cli?command=monitor clients-online --limit 200",
                "/cli?command=monitor client-protocols --ip 192.168.5.14 --mac d2:a3:07:2a:19:be",
                "/cli?command=routing stream list",
                "/analyze?ip=192.168.5.14",
            ],
            "write_guard": "CLI 写操作默认禁止；需要在配置启用 allow_cli_write，并传 confirm=true。",
        }

    def __api_agent_skill(self) -> Dict[str, Any]:
        """读取 ikuai-cli 官方 Agent SKILL.md。"""
        return self.read_agent_skill()

    def __api_agent_skills(self) -> Dict[str, Any]:
        """列出 ikuai-cli 领域技能文件。"""
        return self.list_agent_skills()

    def __api_agent_skill_file(self, name: str) -> Dict[str, Any]:
        """读取指定 ikuai-cli 领域技能文件。"""
        if not str(name or "").strip():
            return {"ok": False, "error": "请传入 name，例如 monitor"}
        return self.read_agent_skill(name)

    @staticmethod
    def __agent_guide_dir() -> Path:
        """返回打包在插件内的 ikuai-cli Agent 指南目录。"""
        return Path(__file__).resolve().parent / "agent_guide"

    def __read_agent_guide(self, relative_path: str) -> Dict[str, Any]:
        """读取插件内置的 ikuai-cli Agent 指南文件。"""
        root = self.__agent_guide_dir().resolve()
        target = (root / relative_path).resolve()
        if not str(target).startswith(str(root)) or not target.is_file():
            return {"ok": False, "error": "指定技能文件不存在"}
        return {"ok": True, "path": relative_path, "content": target.read_text(encoding="utf-8")}

    def __api_cli(self, command: str, confirm: bool = False, raw: bool = False) -> Dict[str, Any]:
        """执行受控 ikuai-cli 命令。"""
        return self.run_cli_command(command=command, confirm=confirm, raw=raw)

    def __api_refresh_agent_tools(self) -> Dict[str, Any]:
        """刷新 MoviePilot MCP/AI 工具管理器。"""
        try:
            from app.agent.tools.manager import moviepilot_tool_manager

            moviepilot_tool_manager._load_tools()
            tool_names = [tool.name for tool in moviepilot_tool_manager.tools]
            logger.info(
                "ikuai-cli助手刷新 MoviePilot AI 工具: "
                f"tool_count={len(tool_names)}, "
                f"has_ikuai_cli={'ikuai_cli' in tool_names}, "
                f"has_ikuai_skill={'ikuai_skill' in tool_names}"
            )
            return {
                "ok": True,
                "tool_count": len(tool_names),
                "has_ikuai_cli": "ikuai_cli" in tool_names,
                "has_ikuai_skill": "ikuai_skill" in tool_names,
            }
        except Exception as err:
            logger.error(f"刷新 MoviePilot AI 工具失败: {err}", exc_info=True)
            return {"ok": False, "error": str(err)}

    @staticmethod
    def __check_cli_command(args: List[str]) -> Dict[str, Any]:
        """检查 ikuai-cli 命令是否允许执行。"""
        blocked = {"repl", "completion", "help"}
        write_words = {
            "set",
            "create",
            "update",
            "delete",
            "remove",
            "clear",
            "kick",
            "upgrade",
            "backup",
            "restore",
            "ntp-sync",
            "set-url",
            "set-token",
            "advanced-set",
            "secondary-route-set",
        }
        if args[0] in blocked:
            return {"ok": False, "error": f"不允许通过插件执行 {args[0]} 命令"}
        is_write = any(part in write_words for part in args)
        return {"ok": True, "write": is_write}

    def __api_status(self) -> Dict[str, Any]:
        """返回爱快系统与接口状态。"""
        if not self._enabled:
            logger.warning("ikuai-cli助手状态查询被拒绝: 插件未启用")
            return self.__disabled()
        client = self.__client()
        logger.info(f"ikuai-cli助手查询状态: base_url={client.base_url}")
        return {
            "ok": True,
            "base_url": client.base_url,
            "token": mask_secret(self._token),
            "system": client.system(),
            "interfaces": client.interfaces(),
        }

    def __api_clients(self, page: int = 1, limit: int = 100) -> Dict[str, Any]:
        """返回在线终端列表。"""
        if not self._enabled:
            logger.warning("ikuai-cli助手在线设备查询被拒绝: 插件未启用")
            return self.__disabled()
        limit = min(max(int(limit or 100), 1), 500)
        logger.info(f"ikuai-cli助手查询在线设备: page={int(page or 1)}, limit={limit}")
        return {"ok": True, "clients": self.__client().clients_online(page=int(page or 1), limit=limit)}

    def __api_device(self, ip: str = "", mac: str = "") -> Dict[str, Any]:
        """返回指定终端的诊断信息。"""
        if not self._enabled:
            logger.warning("ikuai-cli助手设备诊断被拒绝: 插件未启用")
            return self.__disabled()
        target_ip = str(ip or "").strip()
        target_mac = str(mac or "").strip()
        if not target_ip and not target_mac:
            logger.warning("ikuai-cli助手设备诊断参数缺失: ip/mac 为空")
            return {"ok": False, "error": "请传入 ip 或 mac"}
        client = self.__client()
        logger.info(
            "ikuai-cli助手查询设备: "
            f"ip={target_ip or '未传'}, mac={mask_secret(target_mac) if target_mac else '未传'}"
        )
        clients = client.clients_online(limit=500)
        device = find_client(clients, ip=target_ip, mac=target_mac)
        if device and not target_ip:
            target_ip = str(device.get("ip_addr") or "").strip()
        if device and not target_mac:
            target_mac = str(device.get("mac") or "").strip()
        result: Dict[str, Any] = {"ok": True, "target_ip": target_ip, "target_mac": target_mac, "device": device}
        if target_ip and target_mac:
            result["traffic_load"] = client.traffic_load(target_ip, target_mac)
            result["protocols"] = client.client_protocols(target_ip, target_mac)
        return result

    def __api_rules(self, page: int = 1, limit: int = 100) -> Dict[str, Any]:
        """返回五元组分流规则列表。"""
        if not self._enabled:
            logger.warning("ikuai-cli助手分流规则查询被拒绝: 插件未启用")
            return self.__disabled()
        limit = min(max(int(limit or 100), 1), 500)
        logger.info(f"ikuai-cli助手查询分流规则: page={int(page or 1)}, limit={limit}")
        return {"ok": True, "rules": self.__client().five_tuple_rules(page=int(page or 1), limit=limit)}

    def __api_rule(self, rule_id: int) -> Dict[str, Any]:
        """返回指定五元组分流规则摘要。"""
        if not self._enabled:
            logger.warning("ikuai-cli助手规则详情查询被拒绝: 插件未启用")
            return self.__disabled()
        target_rule_id = int(rule_id or 0)
        if target_rule_id <= 0:
            logger.warning("ikuai-cli助手规则详情参数无效: rule_id 为空")
            return {"ok": False, "error": "请传入 rule_id"}
        logger.info(f"ikuai-cli助手查询规则详情: rule_id={target_rule_id}")
        payload = self.__client().five_tuple_rule(target_rule_id)
        return {"ok": True, "rule": summarize_rule(payload), "raw": payload}

    def __api_analyze(self, ip: str = "", mac: str = "") -> Dict[str, Any]:
        """返回爱快综合诊断信息。"""
        if not self._enabled:
            logger.warning("ikuai-cli助手综合分析被拒绝: 插件未启用")
            return self.__disabled()
        client = self.__client()
        logger.info(
            "ikuai-cli助手执行综合分析: "
            f"ip={str(ip or '').strip() or '未传'}, mac={mask_secret(str(mac or '').strip()) if mac else '未传'}"
        )
        result: Dict[str, Any] = {
            "ok": True,
            "base_url": client.base_url,
            "system": client.system(),
            "interfaces": client.interfaces(),
            "clients": client.clients_online(limit=200),
            "rules": client.five_tuple_rules(limit=200),
        }
        if ip or mac:
            result["device"] = self.__api_device(ip=ip, mac=mac)
        return result

    def __api_set_rule_interface(self, rule_id: int, interface: str, confirm: bool = False) -> Dict[str, Any]:
        """切换指定五元组规则出口接口。"""
        if not self._enabled:
            logger.warning("ikuai-cli助手切换规则出口被拒绝: 插件未启用")
            return self.__disabled()
        target_rule_id = int(rule_id or 0)
        target_interface = str(interface or "").strip()
        if target_rule_id <= 0 or not target_interface:
            logger.warning(
                "ikuai-cli助手切换规则出口参数无效: "
                f"rule_id={target_rule_id}, interface={target_interface or '未传'}"
            )
            return {"ok": False, "error": "请传入 rule_id 和 interface"}
        if not confirm:
            logger.warning(
                "ikuai-cli助手拦截切换规则出口: "
                f"rule_id={target_rule_id}, interface={target_interface}, confirm={confirm}"
            )
            return {
                "ok": False,
                "error": "这是写操作，请传 confirm=true 后再执行",
                "rule_id": target_rule_id,
                "interface": target_interface,
            }
        logger.info(f"ikuai-cli助手切换规则 {target_rule_id} 出口为 {target_interface}")
        payload = self.__client().set_five_tuple_interface(target_rule_id, target_interface)
        return {"ok": bool(payload.get("ok", True)), "result": payload}

    def __api_toggle_rule(self, rule_id: int, enabled: bool, confirm: bool = False) -> Dict[str, Any]:
        """启用或停用指定五元组规则。"""
        if not self._enabled:
            logger.warning("ikuai-cli助手切换规则启用状态被拒绝: 插件未启用")
            return self.__disabled()
        target_rule_id = int(rule_id or 0)
        if target_rule_id <= 0:
            logger.warning("ikuai-cli助手切换规则启用状态参数无效: rule_id 为空")
            return {"ok": False, "error": "请传入 rule_id"}
        if not confirm:
            logger.warning(
                "ikuai-cli助手拦截切换规则启用状态: "
                f"rule_id={target_rule_id}, enabled={bool(enabled)}, confirm={confirm}"
            )
            return {
                "ok": False,
                "error": "这是写操作，请传 confirm=true 后再执行",
                "rule_id": target_rule_id,
                "enabled": bool(enabled),
            }
        logger.info(f"ikuai-cli助手切换规则 {target_rule_id} 启用状态为 {enabled}")
        payload = self.__client().toggle_five_tuple_rule(target_rule_id, bool(enabled))
        return {"ok": bool(payload.get("ok", True)), "result": payload}


class IkuaiCliInput(BaseModel):
    """ikuai-cli AI 工具输入参数。"""

    command: str = Field(
        ...,
        description="ikuai-cli subcommand without the executable name, for example: monitor system, monitor clients-online --limit 200, routing stream list.",
    )
    confirm: bool = Field(
        False,
        description="Set true only for confirmed write operations. Read commands should keep false.",
    )
    raw: bool = Field(
        False,
        description="Return raw stdout instead of parsed JSON when needed.",
    )


class IkuaiCliTool(MoviePilotTool):
    """供 MoviePilot AI 调用 ikuai-cli 的工具。"""

    name: str = "ikuai_cli"
    tags: list[str] = [ToolTag.Read, ToolTag.Admin]
    description: str = (
        "Run a controlled ikuai-cli command against the configured iKuai router. "
        "Use ikuai_skill first to read the official domain skill, then call this tool. "
        "Write commands are blocked unless the plugin config allows CLI writes and confirm=true is provided."
    )
    require_admin: bool = True
    args_schema: Type[BaseModel] = IkuaiCliInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        """生成工具调用提示。"""
        return f"执行 ikuai-cli: {kwargs.get('command', '')}"

    async def run(self, command: str, confirm: bool = False, raw: bool = False, **kwargs) -> str:
        """执行 ikuai-cli 命令并返回结构化结果。"""
        plugin = PluginManager().running_plugins.get("IkuaiAssistant")
        if not plugin:
            return json.dumps({"ok": False, "error": "IkuaiAssistant 插件未运行"}, ensure_ascii=False)
        result = plugin.run_cli_command(command=command, confirm=confirm, raw=raw)
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)


class IkuaiSkillInput(BaseModel):
    """ikuai-cli 官方 Agent Skill 读取工具输入参数。"""

    name: str = Field(
        "",
        description="Skill name to read, such as monitor, network, routing, security, vpn, users. Empty returns the root SKILL.md.",
    )
    list_only: bool = Field(
        False,
        description="Set true to list available domain skill files instead of reading content.",
    )


class IkuaiSkillTool(MoviePilotTool):
    """供 MoviePilot AI 读取 ikuai-cli 官方 Agent Skill 的工具。"""

    name: str = "ikuai_skill"
    tags: list[str] = [ToolTag.Read, ToolTag.Admin]
    description: str = (
        "Read the bundled official ikuai-cli Agent SKILL.md or domain skill files. "
        "Use this before ikuai_cli so the agent follows the official command guidance."
    )
    require_admin: bool = True
    args_schema: Type[BaseModel] = IkuaiSkillInput

    def get_tool_message(self, **kwargs) -> Optional[str]:
        """生成工具调用提示。"""
        if kwargs.get("list_only"):
            return "列出 ikuai-cli 官方领域技能"
        return f"读取 ikuai-cli 官方技能: {kwargs.get('name') or 'SKILL.md'}"

    async def run(self, name: str = "", list_only: bool = False, **kwargs) -> str:
        """读取官方 Agent Skill 文档。"""
        plugin = PluginManager().running_plugins.get("IkuaiAssistant")
        if not plugin:
            return json.dumps({"ok": False, "error": "IkuaiAssistant 插件未运行"}, ensure_ascii=False)
        result = plugin.list_agent_skills() if list_only else plugin.read_agent_skill(name)
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)
