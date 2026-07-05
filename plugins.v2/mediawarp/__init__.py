import os
import platform
import tarfile
import tempfile
import shutil
from typing import Any, List, Dict, Tuple
from pathlib import Path
from datetime import datetime, timedelta

import pytz
import psutil
import requests
from ruamel.yaml import YAML
from ruamel.yaml.representer import RoundTripRepresenter
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.helper.mediaserver import MediaServerHelper
from app.log import logger
from app.plugins import _PluginBase


class MediaWarp(_PluginBase):
    """
    Emby/Jellyfin 中间件：优化 Strm 播放、自定义前端样式、允许访问客户端控制、脚本注入
    """

    # 插件名称
    plugin_name = "MediaWarp"
    # 插件描述
    plugin_desc = "EmbyServer/Jellyfin 中间件：优化播放 Strm 文件、自定义前端样式、自定义允许访问客户端、嵌入脚本。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Plugins/refs/heads/main/icons/cloud.png"
    # 插件版本
    plugin_version = "1.1.0"
    # 插件作者
    plugin_author = "DDSRem"
    # 作者主页
    author_url = "https://github.com/DDSRem"
    # 插件配置项ID前缀
    plugin_config_prefix = "mediawarp_"
    # 加载顺序
    plugin_order = 15
    # 可使用的用户级别
    auth_level = 1

    _mediaserver_helper = None
    _mediaserver = None
    _mediaservers = None
    _emby_server = None
    _emby_host = None
    _emby_apikey = None
    _server_type = None
    _server_addr = None
    _server_auth = None
    # 私有属性
    _scheduler = None
    process = None
    _enabled = False
    _port = None
    _media_strm_path = None
    _log_access_console = False
    _log_access_file = True
    _log_service_console = True
    _log_service_file = True
    _web_enable = False
    _web_custom = False
    _web_index = False
    _web_head = ""
    _web_robots = ""
    _crx = False
    _actor_plus = False
    _fanart_show = False
    _external_player_url = False
    _danmaku = False
    _video_together = False
    _client_enable = False
    _client_mode = "BlackList"
    _client_list = ""
    _srt2ass = False
    _subtitle_enable = True
    _subtitle_ass_style = ""
    _cache_enable = True
    _cache_http_strm_ttl = "1m"
    _cache_alist_api_ttl = "10m"
    _cache_image_ttl = "10m"
    _cache_subtitle_ttl = "2h"
    _http_strm_enable = True
    _http_strm_proxy = False
    _http_strm_final_url = True
    _http_strm_compatibility_mode = False
    _alist_strm_enable = True
    _alist_strm_proxy = True
    _alist_strm_raw_url = False
    _alist_strm_list = ""

    def __init__(self):
        """
        初始化
        """
        super().__init__()
        # 类名小写
        class_name = self.__class__.__name__.lower()
        # 二级制文件路径
        self.__mediawarp_path = settings.PLUGIN_DATA_PATH / class_name / "MediaWarp"
        # 配置文件路径
        self.__config_path = settings.PLUGIN_DATA_PATH / class_name / "config"
        # 日志路径
        self.__logs_dir = settings.PLUGIN_DATA_PATH / class_name / "logs"
        # 配置文件名
        self.__config_filename = "config.yaml"
        # 二级制文件版本
        self.__mediawarp_version = "0.2.4"
        self.__mediawarp_version_path = (
            settings.PLUGIN_DATA_PATH / class_name / "version.txt"
        )

    def init_plugin(self, config: dict = None):
        """
        初始化插件：读取配置，获取媒体服务器信息，启动代理服务

        :param config: 插件配置字典，包含 enabled、port、mediaservers 等
        """
        self._mediaserver_helper = MediaServerHelper()
        self._mediaserver = None

        if config:
            self._enabled = config.get("enabled")
            self._port = config.get("port")
            self._media_strm_path = config.get("media_strm_path")
            self._mediaservers = config.get("mediaservers") or []
            self._server_type = config.get("server_type") or self._server_type
            self._server_addr = config.get("server_addr") or self._server_addr
            self._server_auth = config.get("server_auth") or self._server_auth
            self._log_access_console = config.get("log_access_console", False)
            self._log_access_file = config.get("log_access_file", True)
            self._log_service_console = config.get("log_service_console", True)
            self._log_service_file = config.get("log_service_file", True)
            self._web_enable = config.get("web_enable", False)
            self._web_custom = config.get("web_custom", False)
            self._web_index = config.get("web_index", False)
            self._web_head = config.get("web_head") or ""
            self._web_robots = config.get("web_robots") or ""
            self._crx = config.get("crx")
            self._actor_plus = config.get("actor_plus")
            self._fanart_show = config.get("fanart_show")
            self._external_player_url = config.get("external_player_url")
            self._danmaku = config.get("danmaku")
            self._video_together = config.get("video_together")
            self._client_enable = config.get("client_enable", False)
            self._client_mode = config.get("client_mode") or "BlackList"
            self._client_list = config.get("client_list") or ""
            self._srt2ass = config.get("srt2ass")
            self._subtitle_enable = config.get("subtitle_enable", True)
            self._subtitle_ass_style = config.get("subtitle_ass_style") or ""
            self._cache_enable = config.get("cache_enable", True)
            self._cache_http_strm_ttl = config.get("cache_http_strm_ttl") or "1m"
            self._cache_alist_api_ttl = config.get("cache_alist_api_ttl") or "10m"
            self._cache_image_ttl = config.get("cache_image_ttl") or "10m"
            self._cache_subtitle_ttl = config.get("cache_subtitle_ttl") or "2h"
            self._http_strm_enable = config.get("http_strm_enable", True)
            self._http_strm_proxy = config.get("http_strm_proxy", False)
            self._http_strm_final_url = config.get("http_strm_final_url", True)
            self._http_strm_compatibility_mode = config.get(
                "http_strm_compatibility_mode", False
            )
            self._alist_strm_enable = config.get("alist_strm_enable", True)
            self._alist_strm_proxy = config.get("alist_strm_proxy", True)
            self._alist_strm_raw_url = config.get("alist_strm_raw_url", False)
            self._alist_strm_list = config.get("alist_strm_list") or ""

            # 获取媒体服务器
            if self._mediaservers:
                self._mediaserver = [self._mediaservers[0]]

        # 获取媒体服务信息
        if self._mediaserver:
            emby_servers = self._mediaserver_helper.get_services(
                name_filters=self._mediaserver
            )

            for _, emby_server in emby_servers.items():
                self._emby_server = emby_server.type
                self._emby_apikey = emby_server.config.config.get("apikey")
                self._emby_host = emby_server.config.config.get("host")
                if self._emby_host.endswith("/"):
                    self._emby_host = self._emby_host.rstrip("/")
                if not self._emby_host.startswith("http"):
                    self._emby_host = "http://" + self._emby_host
                self._server_type = (
                    "Jellyfin" if self._emby_server == "jellyfin" else "Emby"
                )
                self._server_addr = self._emby_host
                self._server_auth = self._emby_apikey

        self.stop_service()

        if self._enabled:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            logger.info("MediaWarp 服务启动中...")
            self._scheduler.add_job(
                func=self.__run_service,
                trigger="date",
                run_date=datetime.now(tz=pytz.timezone(settings.TZ))
                + timedelta(seconds=2),
                name="MediaWarp启动服务",
            )

            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def __update_config(self):
        self.update_config(
            {
                "enabled": self._enabled,
                "port": self._port,
                "media_strm_path": self._media_strm_path,
                "mediaservers": self._mediaservers,
                "server_type": self._server_type,
                "server_addr": self._server_addr,
                "server_auth": self._server_auth,
                "log_access_console": self._log_access_console,
                "log_access_file": self._log_access_file,
                "log_service_console": self._log_service_console,
                "log_service_file": self._log_service_file,
                "web_enable": self._web_enable,
                "web_custom": self._web_custom,
                "web_index": self._web_index,
                "web_head": self._web_head,
                "web_robots": self._web_robots,
                "crx": self._crx,
                "actor_plus": self._actor_plus,
                "fanart_show": self._fanart_show,
                "external_player_url": self._external_player_url,
                "danmaku": self._danmaku,
                "video_together": self._video_together,
                "client_enable": self._client_enable,
                "client_mode": self._client_mode,
                "client_list": self._client_list,
                "srt2ass": self._srt2ass,
                "subtitle_enable": self._subtitle_enable,
                "subtitle_ass_style": self._subtitle_ass_style,
                "cache_enable": self._cache_enable,
                "cache_http_strm_ttl": self._cache_http_strm_ttl,
                "cache_alist_api_ttl": self._cache_alist_api_ttl,
                "cache_image_ttl": self._cache_image_ttl,
                "cache_subtitle_ttl": self._cache_subtitle_ttl,
                "http_strm_enable": self._http_strm_enable,
                "http_strm_proxy": self._http_strm_proxy,
                "http_strm_final_url": self._http_strm_final_url,
                "http_strm_compatibility_mode": self._http_strm_compatibility_mode,
                "alist_strm_enable": self._alist_strm_enable,
                "alist_strm_proxy": self._alist_strm_proxy,
                "alist_strm_raw_url": self._alist_strm_raw_url,
                "alist_strm_list": self._alist_strm_list,
            }
        )

    def get_state(self) -> bool:
        """
        返回插件启用状态

        :return: True 表示插件已启用
        """
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        返回插件远程命令列表，本插件无远程命令

        :return: None
        """
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        """
        返回插件 API 端点列表，本插件无自定义 API

        :return: None
        """
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """

        web_ui = [
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "web_enable",
                                    "label": "启用Web修改",
                                    "hint": "MediaWarp Web 页面修改总开关",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "web_custom",
                                    "label": "自定义静态资源",
                                    "hint": "加载 custom 目录中的静态资源",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "web_index",
                                    "label": "自定义首页",
                                    "hint": "从 custom 目录读取 index.html",
                                    "persistent-hint": True,
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
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "crx",
                                    "label": "CRX美化",
                                    "hint": "crx 美化",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "actor_plus",
                                    "label": "头像过滤",
                                    "hint": "过滤没有头像的演员和制作人员",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "fanart_show",
                                    "label": "显示同人图",
                                    "hint": "显示同人图（fanart 图）",
                                    "persistent-hint": True,
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
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "external_player_url",
                                    "label": "外置播放器",
                                    "hint": "是否开启外置播放器（仅 Emby）",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "danmaku",
                                    "label": "Web弹幕",
                                    "hint": "Web 弹幕",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "video_together",
                                    "label": "共同观影",
                                    "hint": "共同观影",
                                    "persistent-hint": True,
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
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VTextarea",
                                "props": {
                                    "model": "web_head",
                                    "label": "Head注入内容",
                                    "rows": 5,
                                    "hint": "写入 web.head，可放 script/link/meta 等片段",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VTextarea",
                                "props": {
                                    "model": "web_robots",
                                    "label": "robots.txt",
                                    "rows": 4,
                                    "hint": "写入 web.robots，留空表示不修改",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                ],
            },
        ]

        subtitle = [
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "subtitle_enable",
                                    "label": "启用字幕处理",
                                    "hint": "启用 MediaWarp 字幕相关功能",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "srt2ass",
                                    "label": "SRT转ASS",
                                    "hint": "SRT 字幕转 ASS 字幕",
                                    "persistent-hint": True,
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
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VTextarea",
                                "props": {
                                    "model": "subtitle_ass_style",
                                    "label": "ASS样式",
                                    "rows": 4,
                                    "hint": "每行一条 ass_style，通常包含 Format 和 Style 两行",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    }
                ],
            },
        ]

        advanced = [
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 3},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "log_access_console",
                                    "label": "访问日志终端",
                                    "hint": "log.access.console",
                                    "persistent-hint": True,
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
                                    "model": "log_access_file",
                                    "label": "访问日志文件",
                                    "hint": "log.access.file",
                                    "persistent-hint": True,
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
                                    "model": "log_service_console",
                                    "label": "服务日志终端",
                                    "hint": "log.service.console",
                                    "persistent-hint": True,
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
                                    "model": "log_service_file",
                                    "label": "服务日志文件",
                                    "hint": "log.service.file",
                                    "persistent-hint": True,
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
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "client_enable",
                                    "label": "客户端过滤器",
                                    "hint": "启用 client 过滤器",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSelect",
                                "props": {
                                    "model": "client_mode",
                                    "label": "过滤模式",
                                    "items": [
                                        {"title": "黑名单", "value": "BlackList"},
                                        {"title": "白名单", "value": "WhiteList"},
                                    ],
                                    "hint": "对应 client.mode",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VTextarea",
                                "props": {
                                    "model": "client_list",
                                    "label": "客户端名单",
                                    "rows": 3,
                                    "hint": "一行一个客户端名称",
                                    "persistent-hint": True,
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
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "cache_enable",
                                    "label": "启用缓存",
                                    "hint": "启用 MediaWarp 内置缓存",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "http_strm_enable",
                                    "label": "HTTPStrm启用",
                                    "hint": "开启标准 HTTP URL STRM 重定向",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "http_strm_proxy",
                                    "label": "HTTPStrm代理",
                                    "hint": "允许流量经过媒体服务器",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "http_strm_final_url",
                                    "label": "获取最终链接",
                                    "hint": "减少客户端重定向次数",
                                    "persistent-hint": True,
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
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "http_strm_compatibility_mode",
                                    "label": "兼容模式",
                                    "hint": "使用更兼容但效率较低的最终链接获取方式",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "alist_strm_enable",
                                    "label": "AlistStrm启用",
                                    "hint": "开启 Alist 路径 STRM 重定向",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "alist_strm_proxy",
                                    "label": "AlistStrm代理",
                                    "hint": "允许 AlistStrm 流量经过媒体服务器",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "alist_strm_raw_url",
                                    "label": "使用RawURL",
                                    "hint": "直接响应 Alist 上游真实链接",
                                    "persistent-hint": True,
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
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VTextarea",
                                "props": {
                                    "model": "alist_strm_list",
                                    "label": "Alist服务列表",
                                    "rows": 8,
                                    "hint": "按 YAML 列表填写 addr/username/password/token/prefix_list",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    }
                ],
            },
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 3},
                        "content": [
                            {
                                "component": "VTextField",
                                "props": {
                                    "model": "cache_http_strm_ttl",
                                    "label": "HTTPStrm缓存",
                                    "hint": "示例：1m、2h；0 为关闭",
                                    "persistent-hint": True,
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
                                    "model": "cache_alist_api_ttl",
                                    "label": "Alist API缓存",
                                    "hint": "示例：10m",
                                    "persistent-hint": True,
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
                                    "model": "cache_image_ttl",
                                    "label": "图片缓存",
                                    "hint": "示例：10m",
                                    "persistent-hint": True,
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
                                    "model": "cache_subtitle_ttl",
                                    "label": "字幕缓存",
                                    "hint": "示例：2h",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                ],
            },
        ]

        return [
            {
                "component": "VCard",
                "props": {"variant": "outlined", "class": "mb-3"},
                "content": [
                    {
                        "component": "VCardTitle",
                        "props": {"class": "d-flex align-center"},
                        "content": [
                            {
                                "component": "VIcon",
                                "props": {
                                    "icon": "mdi-cog",
                                    "color": "primary",
                                    "class": "mr-2",
                                },
                            },
                            {"component": "span", "text": "基础设置"},
                        ],
                    },
                    {"component": "VDivider"},
                    {
                        "component": "VCardText",
                        "content": [
                            {
                                "component": "VForm",
                                "content": [
                                    {
                                        "component": "VRow",
                                        "content": [
                                            {
                                                "component": "VCol",
                                                "props": {"cols": 12, "md": 4},
                                                "content": [
                                                    {
                                                        "component": "VSwitch",
                                                        "props": {
                                                            "model": "enabled",
                                                            "label": "启用插件",
                                                        },
                                                    }
                                                ],
                                            },
                                            {
                                                "component": "VCol",
                                                "props": {"cols": 12, "md": 4},
                                                "content": [
                                                    {
                                                        "component": "VTextField",
                                                        "props": {
                                                            "model": "port",
                                                            "label": "端口",
                                                            "hint": "反代后媒体服务器访问端口",
                                                            "persistent-hint": True,
                                                        },
                                                    }
                                                ],
                                            },
                                            {
                                                "component": "VCol",
                                                "props": {"cols": 12, "md": 4},
                                                "content": [
                                                    {
                                                        "component": "VSelect",
                                                        "props": {
                                                            "multiple": True,
                                                            "chips": True,
                                                            "clearable": True,
                                                            "model": "mediaservers",
                                                            "label": "媒体服务器",
                                                            "items": [
                                                                {
                                                                    "title": config.name,
                                                                    "value": config.name,
                                                                }
                                                                for config in (
                                                                    self._mediaserver_helper.get_configs().values()
                                                                )
                                                                if config.type == "emby"
                                                                or config.type
                                                                == "jellyfin"
                                                            ],
                                                            "hint": "同时只能选择一个",
                                                            "persistent-hint": True,
                                                        },
                                                    }
                                                ],
                                            },
                                        ],
                                    },
                                ],
                            },
                            {
                                "component": "VRow",
                                "content": [
                                    {
                                        "component": "VCol",
                                        "props": {"cols": 12, "md": 4},
                                        "content": [
                                            {
                                                "component": "VSelect",
                                                "props": {
                                                    "model": "server_type",
                                                    "label": "服务端类型",
                                                    "items": [
                                                        {"title": "Emby", "value": "Emby"},
                                                        {"title": "Jellyfin", "value": "Jellyfin"},
                                                        {"title": "FNTV", "value": "FNTV"},
                                                    ],
                                                    "hint": "选择上方媒体服务器时会自动使用对应信息",
                                                    "persistent-hint": True,
                                                },
                                            }
                                        ],
                                    },
                                    {
                                        "component": "VCol",
                                        "props": {"cols": 12, "md": 4},
                                        "content": [
                                            {
                                                "component": "VTextField",
                                                "props": {
                                                    "model": "server_addr",
                                                    "label": "服务端地址",
                                                    "placeholder": "http://localhost:8096",
                                                    "hint": "未选择媒体服务器或使用 FNTV 时手动填写",
                                                    "persistent-hint": True,
                                                },
                                            }
                                        ],
                                    },
                                    {
                                        "component": "VCol",
                                        "props": {"cols": 12, "md": 4},
                                        "content": [
                                            {
                                                "component": "VTextField",
                                                "props": {
                                                    "model": "server_auth",
                                                    "label": "服务端认证",
                                                    "hint": "Emby/Jellyfin API Key；FNTV 可留空",
                                                    "persistent-hint": True,
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
                                        "props": {"cols": 12},
                                        "content": [
                                            {
                                                "component": "VTextarea",
                                                "props": {
                                                    "model": "media_strm_path",
                                                    "label": "Emby STRM 媒体库路径",
                                                    "rows": 5,
                                                    "placeholder": "一行一个",
                                                },
                                            },
                                        ],
                                    }
                                ],
                            },
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "info",
                                    "variant": "tonal",
                                    "density": "compact",
                                    "class": "mt-2",
                                },
                                "content": [
                                    {
                                        "component": "div",
                                        "text": "注意：",
                                    },
                                    {
                                        "component": "div",
                                        "text": "如果 MoviePilot 容器为 bridge 模式需要手动映射配置的端口",
                                    },
                                    {
                                        "component": "div",
                                        "text": "更多配置可以前往 MoviePilot 配置目录找到此插件的配置目录进行详细配置文件配置",
                                    },
                                ],
                            },
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "info",
                                    "variant": "tonal",
                                    "density": "compact",
                                    "class": "mt-2",
                                },
                                "content": [
                                    {
                                        "component": "div",
                                        "text": "目前支持 115网盘STRM助手，123云盘STRM助手，CloudMediaSync，OneStrm",
                                    },
                                    {
                                        "component": "div",
                                        "text": "Symedia，q115-strm 等软件生成的STRM文件",
                                    },
                                ],
                            },
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "info",
                                    "variant": "tonal",
                                    "density": "compact",
                                    "class": "mt-2",
                                },
                                "content": [
                                    {
                                        "component": "div",
                                        "text": "感谢项目作者：https://github.com/AkimioJR/MediaWarp",
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "component": "VCard",
                "props": {"variant": "outlined"},
                "content": [
                    {
                        "component": "VTabs",
                        "props": {"model": "tab", "grow": True, "color": "primary"},
                        "content": [
                            {
                                "component": "VTab",
                                "props": {"value": "web-ui"},
                                "content": [
                                    {
                                        "component": "VIcon",
                                        "props": {
                                            "icon": "mdi-file-move-outline",
                                            "start": True,
                                            "color": "#1976D2",
                                        },
                                    },
                                    {"component": "span", "text": "Web页面配置"},
                                ],
                            },
                            {
                                "component": "VTab",
                                "props": {"value": "subtitle"},
                                "content": [
                                    {
                                        "component": "VIcon",
                                        "props": {
                                            "icon": "mdi-sync",
                                            "start": True,
                                            "color": "#4CAF50",
                                        },
                                    },
                                    {"component": "span", "text": "字体相关设置"},
                                ],
                            },
                            {
                                "component": "VTab",
                                "props": {"value": "advanced"},
                                "content": [
                                    {
                                        "component": "VIcon",
                                        "props": {
                                            "icon": "mdi-tune",
                                            "start": True,
                                            "color": "#FF9800",
                                        },
                                    },
                                    {"component": "span", "text": "高级设置"},
                                ],
                            },
                        ],
                    },
                    {"component": "VDivider"},
                    {
                        "component": "VWindow",
                        "props": {"model": "tab"},
                        "content": [
                            {
                                "component": "VWindowItem",
                                "props": {"value": "web-ui"},
                                "content": [
                                    {
                                        "component": "VCardText",
                                        "content": web_ui,
                                    }
                                ],
                            },
                            {
                                "component": "VWindowItem",
                                "props": {"value": "subtitle"},
                                "content": [
                                    {"component": "VCardText", "content": subtitle}
                                ],
                            },
                            {
                                "component": "VWindowItem",
                                "props": {"value": "advanced"},
                                "content": [
                                    {"component": "VCardText", "content": advanced}
                                ],
                            },
                        ],
                    },
                ],
            },
        ], {
            "enabled": False,
            "port": "",
            "media_strm_path": "",
            "mediaservers": [],
            "server_type": "Emby",
            "server_addr": "",
            "server_auth": "",
            "log_access_console": False,
            "log_access_file": True,
            "log_service_console": True,
            "log_service_file": True,
            "web_enable": False,
            "web_custom": False,
            "web_index": False,
            "web_head": "",
            "web_robots": "",
            "crx": False,
            "actor_plus": False,
            "fanart_show": False,
            "external_player_url": False,
            "danmaku": False,
            "video_together": False,
            "client_enable": False,
            "client_mode": "BlackList",
            "client_list": "Fileball\nInfuse",
            "srt2ass": False,
            "subtitle_enable": True,
            "subtitle_ass_style": (
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
                "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
                "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
                "Alignment, MarginL, MarginR, MarginV, Encoding\n"
                "Style: Default,楷体,20,&H03FFFFFF,&H00FFFFFF,&H00000000,"
                "&H02000000,-1,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1"
            ),
            "cache_enable": True,
            "cache_http_strm_ttl": "1m",
            "cache_alist_api_ttl": "10m",
            "cache_image_ttl": "10m",
            "cache_subtitle_ttl": "2h",
            "http_strm_enable": True,
            "http_strm_proxy": False,
            "http_strm_final_url": True,
            "http_strm_compatibility_mode": False,
            "alist_strm_enable": True,
            "alist_strm_proxy": True,
            "alist_strm_raw_url": False,
            "alist_strm_list": "",
            "tab": "web-ui",
        }

    def get_page(self) -> List[dict]:
        """
        返回插件数据页面配置，本插件无数据页面

        :return: None
        """
        pass

    def __get_prefix_list(self) -> List[str]:
        """
        获取 HTTPStrm 前缀列表，过滤空行。
        """
        return [
            item.strip()
            for item in (self._media_strm_path or "").splitlines()
            if item.strip()
        ]

    def __get_text_lines(self, value: str) -> List[str]:
        """
        将多行文本转换为非空字符串列表。
        """
        return [item.strip() for item in (value or "").splitlines() if item.strip()]

    def __get_alist_strm_list(self) -> List[Dict[str, Any]]:
        """
        将 AlistStrm 服务列表文本转换为 MediaWarp 配置数组。
        """
        text = (self._alist_strm_list or "").strip()
        if not text:
            return []

        yaml = YAML()
        try:
            data = yaml.load(text)
        except Exception as err:
            logger.error(f"AlistStrm 服务列表解析失败：{err}")
            return []

        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            return [data]
        return []

    def __get_server_type(self) -> str:
        """
        获取符合 MediaWarp 配置要求的媒体服务器类型。
        """
        server_type = self._server_type or self._emby_server or "Emby"
        server_type_lower = str(server_type).lower()
        if server_type_lower == "jellyfin":
            return "Jellyfin"
        if server_type_lower == "fntv":
            return "FNTV"
        return "Emby"

    def __build_config_changes(self) -> Dict[str, Any]:
        """
        生成 MediaWarp v0.2.4 配置覆盖项。
        """
        return {
            "port": int(self._port) if str(self._port).isdigit() else self._port,
            "server.type": self.__get_server_type(),
            "server.addr": self._server_addr or self._emby_host,
            "server.auth": self._server_auth or self._emby_apikey,
            "log.access.console": bool(self._log_access_console),
            "log.access.file": bool(self._log_access_file),
            "log.service.console": bool(self._log_service_console),
            "log.service.file": bool(self._log_service_file),
            "cache.enable": bool(self._cache_enable),
            "cache.http_strm_ttl": self._cache_http_strm_ttl or "1m",
            "cache.alist_api_ttl": self._cache_alist_api_ttl or "10m",
            "cache.image_ttl": self._cache_image_ttl or "10m",
            "cache.subtitle_ttl": self._cache_subtitle_ttl or "2h",
            "web.enable": bool(self._web_enable),
            "web.custom": bool(self._web_custom),
            "web.index": bool(self._web_index),
            "web.head": self._web_head or "",
            "web.robots": self._web_robots or "",
            "web.crx": bool(self._crx),
            "web.actor_plus": bool(self._actor_plus),
            "web.fanart_show": bool(self._fanart_show),
            "web.danmaku": bool(self._danmaku),
            "web.external_player_url": bool(self._external_player_url),
            "web.video_together": bool(self._video_together),
            "client.enable": bool(self._client_enable),
            "client.mode": self._client_mode or "BlackList",
            "client.list": self.__get_text_lines(self._client_list),
            "http_strm.enable": bool(self._http_strm_enable),
            "http_strm.proxy": bool(self._http_strm_proxy),
            "http_strm.final_url": bool(self._http_strm_final_url),
            "http_strm.compatibility_mode": bool(
                self._http_strm_compatibility_mode
            ),
            "http_strm.prefix_list": self.__get_prefix_list(),
            "alist_strm.enable": bool(self._alist_strm_enable),
            "alist_strm.proxy": bool(self._alist_strm_proxy),
            "alist_strm.raw_url": bool(self._alist_strm_raw_url),
            "alist_strm.list": self.__get_alist_strm_list(),
            "subtitle.enable": bool(self._subtitle_enable),
            "subtitle.srt2ass": bool(self._srt2ass),
            "subtitle.ass_style": self.__get_text_lines(self._subtitle_ass_style),
        }

    def __run_service(self):
        """
        运行服务
        """
        if not Path(self.__mediawarp_path).exists():
            logger.info("尝试自动下载二级制文件中...")
            self.__download_and_extract()
            if not Path(self.__mediawarp_path).exists():
                logger.error("下载失败，MediaWarp 二级制文件不存在，无法启动插件")
                logger.info(
                    f"请将 MediaWarp 二级制文件放入 {settings.PLUGIN_DATA_PATH / self.__class__.__name__.lower()} 文件夹内"
                )
                self.__update_config()
                return

        if os.path.exists(self.__mediawarp_version_path):
            with open(self.__mediawarp_version_path, "r", encoding="utf-8") as f:
                version = f.read().strip()
            if version != self.__mediawarp_version:
                logger.info("尝试自动更新二级制文件中...")
                self.__download_and_extract()

        if not Path(self.__config_path / self.__config_filename).exists():
            logger.error("MediaWarp 配置文件不存在，无法启动插件")
            self.__update_config()
            return

        changes = self.__build_config_changes()
        self.__modify_config(Path(self.__config_path / self.__config_filename), changes)

        Path(self.__config_path).mkdir(parents=True, exist_ok=True)
        Path(self.__logs_dir).mkdir(parents=True, exist_ok=True)

        runtime_dir = Path(self.__mediawarp_path).parent
        self.process = psutil.Popen([str(self.__mediawarp_path)], cwd=str(runtime_dir))

        if self.process.is_running():
            logger.info("MediaWarp 服务成功启动！")

    def __modify_config(self, config_path, modifications):
        """
        修改配置文件

        :param config_path: 配置文件路径
        :param modifications: 要修改的配置项字典
        :return: None
        """
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.indent(mapping=2, sequence=4, offset=2)

        def represent_bool(self, data):
            """
            将 Python bool 序列化为 YAML 大写 True/False 字符串

            :param data: 布尔值
            :return: YAML 标量节点
            """
            if data:
                return self.represent_scalar("tag:yaml.org,2002:bool", "True")
            else:
                return self.represent_scalar("tag:yaml.org,2002:bool", "False")

        RoundTripRepresenter.add_representer(bool, represent_bool)

        with open(config_path, "r", encoding="utf-8") as file:
            config = yaml.load(file)

        for key, value in modifications.items():
            keys = key.split(".")
            current = config
            for k in keys[:-1]:
                current = current.setdefault(k, {})
            current[keys[-1]] = value

        with open(config_path, "w", encoding="utf-8") as file:
            yaml.dump(config, file)

    def __get_download_url(self):
        """
        获取下载链接
        """
        base_url = (
            "https://github.com/AkimioJR/MediaWarp/releases/"
            "download/v{version}/MediaWarp_{version}_{os}_{arch}.tar.gz"
        )

        machine = platform.machine().lower()
        if machine == "arm64" or machine == "aarch64":
            arch = "arm64"
        else:
            arch = "amd64"

        system = platform.system().lower()
        if system == "darwin":
            os_name = "darwin"
        else:
            os_name = "linux"

        return base_url.format(arch=arch, version=self.__mediawarp_version, os=os_name)

    def __download_and_extract(self):
        """
        下载并解压
        """
        url = self.__get_download_url()
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, "MediaWarp.tar.gz")

        try:
            Path(self.__config_path).mkdir(parents=True, exist_ok=True)

            logger.info(f"正在下载: {url}")
            response = requests.get(url, stream=True, proxies=settings.PROXY)
            response.raise_for_status()

            with open(temp_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info("正在解压文件...")
            with tarfile.open(temp_file, "r:gz") as tar:
                mediawarp_member = [
                    m for m in tar.getmembers() if m.name.endswith("MediaWarp")
                ]
                if mediawarp_member:
                    tar.extract(member=mediawarp_member[0], path=temp_dir)
                    extracted_path = Path(temp_dir) / mediawarp_member[0].name
                    extracted_path.chmod(0o755)
                    shutil.copy2(extracted_path, Path(self.__mediawarp_path))

                config_target = Path(self.__config_path / self.__config_filename)
                if not config_target.exists():
                    config_example_member = [
                        m
                        for m in tar.getmembers()
                        if m.name.endswith("config.yaml")
                        or m.name.endswith("config.yaml.example")
                    ]
                    if config_example_member:
                        tar.extract(member=config_example_member[0], path=temp_dir)
                        extracted_config = (
                            Path(temp_dir) / config_example_member[0].name
                        )
                        shutil.copy2(extracted_config, config_target)
                        logger.info(f"示例配置文件已保存到 {config_target}")

            with open(self.__mediawarp_version_path, "w", encoding="utf-8") as f:
                f.write(self.__mediawarp_version)
            logger.info(f"安装完成！MediaWarp 已安装到 {self.__mediawarp_path}")
        except Exception as e:
            logger.info(f"发生错误: {e}")
        finally:
            shutil.rmtree(temp_dir)

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
            if self.process:
                if self.process.is_running():
                    self.process.terminate()
        except Exception as e:
            logger.error(f"退出插件失败：{e}")
