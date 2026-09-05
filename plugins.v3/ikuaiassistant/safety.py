"""ikuai-cli 命令安全策略与短期预览缓存。"""
from dataclasses import dataclass
import hashlib
import secrets
import time
from threading import Lock


@dataclass(frozen=True)
class CommandDecision:
    """表示 CLI 命令的安全判定结果。"""
    allowed: bool
    write: bool
    high_risk: bool
    requires_preview: bool
    reason: str


class PreviewStore:
    """保存五分钟内有效的一次性写操作预览。"""
    def __init__(self, ttl: int = 300):
        self._ttl = ttl
        self._items = {}
        self._lock = Lock()

    def create(self, args: list[str]) -> str:
        """创建命令预览并返回短期 ID。"""
        now = time.monotonic()
        digest = secrets.token_urlsafe(24)
        with self._lock:
            self._prune(now)
            if len(self._items) >= 256:
                self._items.pop(next(iter(self._items)))
            self._items[digest] = (tuple(args), now + self._ttl)
        return digest

    def consume(self, preview_id: str, args: list[str]) -> tuple[bool, str]:
        """校验并一次性消费命令预览。"""
        with self._lock:
            item = self._items.pop(str(preview_id or ""), None)
            if not item:
                return False, "预览不存在或已过期"
            expected, expires = item
            if time.monotonic() > expires:
                return False, "预览不存在或已过期"
            if expected != tuple(args):
                return False, "执行命令与预览内容不一致"
            return True, ""

    def _prune(self, now: float) -> None:
        """清理过期预览。"""
        for key, (_, expires) in list(self._items.items()):
            if expires <= now:
                self._items.pop(key, None)


def check_command(args: list[str]) -> dict:
    """按完整命令路径和参数白名单判定，未知路径或参数默认拒绝。"""
    denied = {"ok": False, "write": False, "error_type": "command_not_allowed", "error": "命令或参数未登记，禁止执行"}
    read_paths = {("version",), ("network", "dns", "get"), ("system", "get")}
    monitors = "system interfaces interfaces-traffic interfaces-config interfaces-physical interfaces-traffic-v6 cpu memory disk temp terminals connections network-load clients-online clients-offline clients-ip6-online clients-ip6-offline traffic-summary traffic-load client-protocols client-protocols-history client-app-protocols protocols protocols-history app-traffic-summary app-protocols-load app-protocols-history app-protocols-terminals wireless-stats wireless-score wireless-traffic ssid-clients channel-clients cameras switch".split()
    read_paths.update(("monitor", name) for name in monitors)
    for group in ("wan", "lan", "physical", "vlan", "nat", "dnat", "dmz", "dhcp", "dhcp6"):
        read_paths.add(("network", group, "list"))
    for kind in ("system", "pppoe"):
        read_paths.add(("log", kind, "list"))
    write_paths = set()
    for kind in ("five-tuple", "domain", "l7", "load-balance", "updown"):
        for action in ("list", "get"):
            read_paths.add(("routing", "stream", kind, action))
        # 第一版只开放有明确参数合同的启停；扩大写入面须先补参数测试。
        write_paths.add(("routing", "stream", kind, "toggle"))
    read_paths.update({("routing", "static", "list"), ("routing", "static", "get"), ("system", "backup", "list")})
    candidates = sorted(read_paths | write_paths, key=len, reverse=True)
    path = next((p for p in candidates if tuple(args[:len(p)]) == p), None)
    if path is None:
        return denied
    write = path in write_paths
    tail = list(args[len(path):])
    if write or path[-1] == "get" and path[:2] in (("routing", "static"), ("routing", "stream")):
        if not tail or not tail.pop(0).isdigit():
            return denied
    flags = {"--human-time", "--wide"}
    values = {"--page", "--page-size", "--limit", "--time-range", "--start-time", "--end-time", "--aggregate", "--ip", "--mac", "--order", "--order-by", "--columns", "--apmac", "--ssid", "--channel", "--format", "-f"}
    if write:
        flags = set()
        values = {"--enabled"}
    seen = set()
    while tail:
        flag = tail.pop(0)
        if flag in seen:
            return denied
        seen.add(flag)
        if flag in flags:
            continue
        if flag not in values or not tail:
            return denied
        value = tail.pop(0)
        if value.startswith("-"):
            return denied
        if flag in {"--format", "-f"} and value != "json":
            return denied
        if flag == "--enabled" and value not in {"yes", "no"}:
            return denied
        if flag in {"--page", "--page-size", "--limit"} and (not value.isdigit() or int(value) < 1 or (flag != "--page" and int(value) > 500)):
            return denied
    if write and "--enabled" not in seen:
        return denied
    return {"ok": True, "write": write}
