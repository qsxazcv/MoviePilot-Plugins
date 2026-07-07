# -*- coding: utf-8 -*-
"""MoviePilot 通知发送工具。"""

import sys


def _plugin_detail_link():
    path = "#/plugins?tab=installed&id=programpreview"
    try:
        from app.core.config import settings
        return settings.MP_DOMAIN(path)
    except Exception:
        return path


def notify(title, text):
    """通过 MoviePilot 内部链路发送通知，避免外部 API 认证问题。"""
    try:
        sys.path.insert(0, '/app')
        from app.chain import ChainBase
        from app.schemas import Notification
        from app.schemas.types import NotificationType
        ChainBase().post_message(
            Notification(
                mtype=NotificationType.Plugin,
                title=title,
                text=text,
                link=_plugin_detail_link(),
            )
        )
        return 1, 'MoviePilot notification posted'
    except Exception as e:
        return 0, repr(e)
