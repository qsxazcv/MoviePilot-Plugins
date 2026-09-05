"""IkuaiAssistant 数据格式化辅助函数。"""
from typing import Any


def format_rate(value: Any) -> str:
    """把字节每秒数值格式化为可读速率。"""
    try:
        rate = float(value or 0)
    except (TypeError, ValueError):
        return str(value)
    if rate >= 1024**2:
        return f"{rate / 1024**2:.1f} MB/s"
    if rate >= 1024:
        return f"{rate / 1024:.1f} KB/s"
    return f"{int(rate)} B/s"


def format_bytes(value: Any) -> str:
    """把字节数格式化为可读容量。"""
    try:
        size = float(value or 0)
    except (TypeError, ValueError):
        return str(value)
    if size >= 1024**3:
        return f"{size / 1024**3:.2f} GB"
    if size >= 1024**2:
        return f"{size / 1024**2:.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{int(size)} B"


def max_percent(value: Any) -> float:
    """从数字、字符串或列表中提取最大百分比。"""
    values = value if isinstance(value, list) else [value]
    result = []
    for item in values:
        try:
            result.append(float(str(item or "").strip().replace("%", "")))
        except (TypeError, ValueError):
            continue
    return max(result) if result else 0.0


def pick_value(client: dict[str, Any], keys: list[str]) -> str:
    """按候选键名不区分大小写提取客户端字段。"""
    lowered = {str(key).lower(): value for key, value in client.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, ""):
            return str(value)
    return ""


def pick_number(client: dict[str, Any], keys: list[str]) -> float:
    """按候选键名提取客户端数值字段。"""
    try:
        return float(pick_value(client, keys) or 0)
    except (TypeError, ValueError):
        return 0.0


def format_kib(value: Any) -> str:
    """把 KiB 数值格式化为 MiB 或 GiB。"""
    try:
        mib = float(value) / 1024
    except (TypeError, ValueError):
        return str(value)
    return f"{mib / 1024:.2f} GiB" if mib >= 1024 else f"{mib:.2f} MiB"


def find_first(payload: Any, keys: list[str]) -> Any:
    """从嵌套字典或列表中递归查找第一个非空字段。"""
    if isinstance(payload, dict):
        for key in keys:
            if payload.get(key) not in (None, ""):
                return payload[key]
        for value in payload.values():
            found = find_first(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = find_first(value, keys)
            if found not in (None, ""):
                return found
    return None
