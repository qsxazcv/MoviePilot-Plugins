"""IkuaiAssistant API 入口适配辅助函数。"""
from typing import Any, Callable


def api_cli(run: Callable[..., dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    """转发 CLI API 参数，保持入口层薄。"""
    return run(**kwargs)


def api_agent_skill(read: Callable[..., dict[str, Any]], name: str = "") -> dict[str, Any]:
    return read(name)


def api_agent_skills(list_fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    return list_fn()


def api_refresh_tools(refresh: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    return refresh()


def api_disabled(disabled: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """统一调用插件未启用响应。"""
    return disabled()


def api_page_limit(normalize: Callable[..., tuple[int, int]], page: int, limit: int) -> tuple[int, int]:
    """统一分页参数归一化入口。"""
    return normalize(page, limit)


def api_enabled(enabled: bool, disabled: Callable[[], dict[str, Any]]) -> dict[str, Any] | None:
    """为查询型 API 提供统一启用状态门面。"""
    return None if enabled else disabled()


def api_clients(fetch: Callable[..., Any], page: int, limit: int) -> dict[str, Any]:
    """转发在线客户端查询，避免入口层重复拼装参数。"""
    return {"ok": True, "clients": fetch(page=page, limit=limit)}


def api_rules(fetch: Callable[..., Any], page: int, limit: int) -> dict[str, Any]:
    """转发分流规则查询。"""
    return {"ok": True, "rules": fetch(page=page, limit=limit)}


def api_status(system: Callable[[], dict[str, Any]], interfaces: Callable[[], dict[str, Any]], base_url: str, token: str) -> dict[str, Any]:
    """查询系统与接口状态；调用方传入脱敏后的 token。"""
    system_data, interface_data = system(), interfaces()
    return {"ok": bool(system_data.get("ok")) and bool(interface_data.get("ok")), "base_url": base_url, "token": token, "system": system_data, "interfaces": interface_data}


def api_device(clients: Callable[..., Any], traffic: Callable[..., Any], protocols: Callable[..., Any], target_ip: str, target_mac: str, find: Callable[..., Any]) -> dict[str, Any]:
    """查询设备并在身份完整时补充流量和协议数据。"""
    rows = clients(limit=500)
    device = find(rows, ip=target_ip, mac=target_mac)
    if device and not target_ip: target_ip = str(device.get("ip_addr") or "").strip()
    if device and not target_mac: target_mac = str(device.get("mac") or "").strip()
    result = {"ok": True, "target_ip": target_ip, "target_mac": target_mac, "device": device}
    if target_ip and target_mac:
        result["traffic_load"] = traffic(target_ip, target_mac)
        result["protocols"] = protocols(target_ip, target_mac)
    return result


def api_analyze(system: Callable[[], Any], interfaces: Callable[[], Any], clients: Callable[..., Any], rules: Callable[..., Any], device: Callable[..., Any] | None = None, ip: str = "", mac: str = "") -> dict[str, Any]:
    """聚合只读系统、接口、终端和分流规则诊断结果。"""
    result = {"ok": True, "system": system(), "interfaces": interfaces(), "clients": clients(limit=200), "rules": rules(limit=200)}
    if ip or mac:
        result["device"] = device(ip=ip, mac=mac) if device else None
    return result


def require_write_confirmation(confirm: bool, **context: Any) -> dict[str, Any] | None:
    """写操作统一确认门面；不执行任何实际操作。"""
    if confirm:
        return None
    return {"ok": False, "error": "这是写操作，请传 confirm=true 后再执行", **context}


def api_set_rule_interface(update: Callable[..., Any], rule_id: int, interface: str, confirm: bool) -> dict[str, Any]:
    """在确认通过后转发规则出口修改。"""
    blocked = require_write_confirmation(confirm, rule_id=rule_id, interface=interface)
    if blocked:
        return blocked
    payload = update(rule_id, interface)
    return {"ok": bool(payload.get("ok", True)), "result": payload}


def api_toggle_rule(update: Callable[..., Any], rule_id: int, enabled: bool, confirm: bool) -> dict[str, Any]:
    """在确认通过后转发规则启停修改。"""
    blocked = require_write_confirmation(confirm, rule_id=rule_id, enabled=bool(enabled))
    if blocked:
        return blocked
    payload = update(rule_id, bool(enabled))
    return {"ok": bool(payload.get("ok", True)), "result": payload}
