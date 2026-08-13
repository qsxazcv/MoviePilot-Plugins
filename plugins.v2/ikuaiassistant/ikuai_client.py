import json
import ssl
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


def normalize_base_url(base_url: str) -> str:
    """规范化爱快路由器地址，只保留协议、主机和端口。"""
    raw_url = str(base_url or "").strip().rstrip("/")
    if not raw_url:
        return ""
    if "://" not in raw_url:
        raw_url = f"http://{raw_url}"
    parts = urlsplit(raw_url)
    return urlunsplit((parts.scheme or "http", parts.netloc, "", "", "")).rstrip("/")


def mask_secret(secret: str) -> str:
    """脱敏展示 Token，避免在页面或日志中泄露完整凭据。"""
    text = str(secret or "")
    if len(text) < 12:
        return "***" if text else ""
    return f"{text[:4]}...{text[-4:]}"


def find_client(payload: Dict[str, Any], ip: str = "", mac: str = "") -> Optional[Dict[str, Any]]:
    """从在线终端响应中按 IP 或 MAC 查找目标设备。"""
    target_ip = str(ip or "").strip()
    target_mac = str(mac or "").strip().lower()
    for item in extract_items(payload):
        item_ip = str(item.get("ip_addr") or "").strip()
        item_mac = str(item.get("mac") or "").strip().lower()
        if target_ip and item_ip == target_ip:
            return item
        if target_mac and item_mac == target_mac:
            return item
    return None


def summarize_rule(payload: Dict[str, Any]) -> Dict[str, Any]:
    """提取分流规则的关键诊断字段。"""
    data = extract_items(payload)
    rule = data[0] if data else payload
    return {
        "id": rule.get("id"),
        "name": rule.get("tagname") or rule.get("name") or "",
        "enabled": rule.get("enabled"),
        "interface": rule.get("interface"),
        "mode": rule.get("mode"),
        "priority": rule.get("prio"),
    }


def extract_items(payload: Dict[str, Any]) -> list:
    """从 CLI 展开响应或 REST results 信封中提取列表数据。"""
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("data"), list):
        return payload.get("data") or []
    if isinstance(payload.get("data"), dict):
        return [payload.get("data") or {}]
    results = payload.get("results")
    if isinstance(results, dict) and isinstance(results.get("data"), list):
        return results.get("data") or []
    if isinstance(results, dict):
        return [results]
    return []


@dataclass
class IkuaiClient:
    """爱快 REST API 客户端。"""

    base_url: str
    token: str
    verify_ssl: bool = False
    timeout: int = 10

    def __post_init__(self) -> None:
        """初始化时规范化地址和超时时间。"""
        self.base_url = normalize_base_url(self.base_url)
        self.token = str(self.token or "").strip()
        if self.token.lower().startswith("bearer "):
            self.token = self.token[7:].strip()
        self.timeout = max(int(self.timeout or 10), 1)

    @property
    def ready(self) -> bool:
        """判断客户端是否已经具备请求爱快 API 的必要配置。"""
        return bool(self.base_url and self.token)

    def system(self) -> Dict[str, Any]:
        """获取爱快系统概览。"""
        return self.request("GET", "/api/v4.0/monitoring/system")

    def interfaces(self) -> Dict[str, Any]:
        """获取爱快线路检测和接口流量。"""
        return self.request("GET", "/api/v4.0/monitoring/interfaces-status")

    def clients_online(self, page: int = 1, limit: int = 50) -> Dict[str, Any]:
        """获取在线终端列表。"""
        query = urlencode({"page": page, "limit": limit})
        return self.request("GET", f"/api/v4.0/monitoring/clients-online?{query}")

    def traffic_load(self, ip: str, mac: str) -> Dict[str, Any]:
        """获取单终端 5 分钟流量负载。"""
        query = urlencode({"ip": ip, "mac": mac})
        return self.request("GET", f"/api/v4.0/monitoring/clients-traffic-load?{query}")

    def client_protocols(self, ip: str, mac: str) -> Dict[str, Any]:
        """获取单终端应用协议统计。"""
        query = urlencode({"ip": ip, "mac": mac})
        return self.request("GET", f"/api/v4.0/monitoring/clients/protocols?{query}")

    def five_tuple_rule(self, rule_id: int) -> Dict[str, Any]:
        """获取五元组分流规则。"""
        return self.request("GET", f"/api/v4.0/routing/five-tuple-rules/{int(rule_id)}")

    def five_tuple_rules(self, page: int = 1, limit: int = 100) -> Dict[str, Any]:
        """获取五元组分流规则列表。"""
        query = urlencode({"page": page, "limit": limit})
        return self.request("GET", f"/api/v4.0/routing/five-tuple-rules?{query}")

    def set_five_tuple_interface(self, rule_id: int, interface: str) -> Dict[str, Any]:
        """把已有五元组规则切换到指定出口接口并保持启用。"""
        current = self.five_tuple_rule(rule_id)
        items = extract_items(current)
        data = (items[0] if items else {}).copy()
        if not data:
            return {"ok": False, "error": f"未找到五元组规则 {rule_id}", "raw": current}
        data["interface"] = str(interface or "").strip()
        data["enabled"] = "yes"
        return self.request("PUT", f"/api/v4.0/routing/five-tuple-rules/{int(rule_id)}", data)

    def toggle_five_tuple_rule(self, rule_id: int, enabled: bool) -> Dict[str, Any]:
        """启用或停用已有五元组分流规则。"""
        return self.request(
            "PATCH",
            f"/api/v4.0/routing/five-tuple-rules/{int(rule_id)}",
            {"enabled": "yes" if enabled else "no"},
        )

    def request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行爱快 API 请求并解析 JSON 响应。"""
        if not self.ready:
            return {"ok": False, "error": "请先配置爱快地址和 API Token"}
        url = f"{self.base_url}{path}"
        data = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "User-Agent": "MoviePilot-IkuaiAssistant/1.0.0",
        }
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url=url, data=data, headers=headers, method=method.upper())
        try:
            context = None if self.verify_ssl else ssl._create_unverified_context()
            with urlopen(request, timeout=self.timeout, context=context) as response:
                text = response.read().decode("utf-8", errors="replace")
        except HTTPError as err:
            text = err.read().decode("utf-8", errors="replace")
            return {"ok": False, "status": err.code, "error": text or err.reason}
        except URLError as err:
            return {"ok": False, "error": str(err.reason)}
        except Exception as err:
            return {"ok": False, "error": str(err)}
        try:
            parsed = json.loads(text) if text else {}
        except json.JSONDecodeError:
            return {"ok": False, "error": "爱快返回了非 JSON 响应", "raw": text[:200]}
        if isinstance(parsed, dict):
            code = parsed.get("code")
            if code is not None:
                parsed["ok"] = code in (0, 200)
                if not parsed["ok"] and not parsed.get("error"):
                    parsed["error"] = parsed.get("message") or f"爱快 API 返回 code={code}"
            else:
                parsed.setdefault("ok", True)
            return parsed
        return {"ok": True, "data": parsed}
