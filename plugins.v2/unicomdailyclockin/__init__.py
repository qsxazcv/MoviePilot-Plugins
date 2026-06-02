# -*- coding: utf-8 -*-
"""联通签到立减金 MoviePilot 本地插件。

支持单账号配置和多账号 JSON 配置。敏感登录态不要写入记忆文件；可以填写在插件配置页，
也可以留空后读取容器环境变量。
"""

from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional
import json
import re
import os
import traceback
import urllib.parse
import urllib.request

from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import NotificationType


class UnicomDailyClockin(_PluginBase):
    plugin_name = "联通签到立减金"
    plugin_desc = "每天自动执行中国联通立减金签到，支持多账号、立即运行、Cron 定时和通知结果。"
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Plugins/main/icons/notice.png"
    plugin_version = "1.1.9"
    plugin_author = "qsxazcv"
    author_url = "https://github.com/jxxghp/MoviePilot"
    plugin_config_prefix = "unicomdailyclockin_"
    plugin_order = 27
    auth_level = 1

    BASE = "https://epay.10010.com"
    REFERER = "https://epay.10010.com/ci-mcss-party-web/clockIn/?bizFrom=226&bizChannelCode=226&channelType=FX"
    UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 MicroMessenger/8.0.49 Mobile Safari/604.1"

    _enabled: bool = False
    _onlyonce: bool = False
    _notify: bool = True
    _cron: str = "5 6 * * *"
    _accounts_json: str = ""
    _auth_info: str = ""
    _tokenid: str = ""
    _biz_channel_info: str = ""
    _cookie: str = ""
    _last_run: str = ""
    _last_status: str = "未运行"
    _last_result: str = ""

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = bool(config.get("enabled", False))
            self._onlyonce = bool(config.get("onlyonce", False))
            self._notify = bool(config.get("notify", True))
            self._cron = config.get("cron") or "5 6 * * *"
            self._accounts_json = config.get("accounts_json") or ""
            self._auth_info = config.get("auth_info") or ""
            self._tokenid = config.get("tokenid") or ""
            self._biz_channel_info = config.get("biz_channel_info") or ""
            self._cookie = config.get("cookie") or ""
            self._last_run = config.get("last_run") or ""
            self._last_status = config.get("last_status") or "未运行"
            self._last_result = config.get("last_result") or ""

        if self._onlyonce:
            try:
                self._onlyonce = False
                self._last_status = "立即运行已触发"
                self._update_config()
                self.run_checkin()
            except Exception as err:
                logger.error(f"联通签到立减金立即运行失败：{err}\n{traceback.format_exc()}")
                self._last_status = f"立即运行失败：{err}"
                self._update_config()

    def get_state(self) -> bool:
        return self._enabled

    def _update_config(self):
        self.update_config({
            "enabled": self._enabled,
            "onlyonce": False,
            "notify": self._notify,
            "cron": self._cron,
            "accounts_json": self._accounts_json,
            "auth_info": self._auth_info,
            "tokenid": self._tokenid,
            "biz_channel_info": self._biz_channel_info,
            "cookie": self._cookie,
            "last_run": self._last_run,
            "last_status": self._last_status,
            "last_result": self._last_result,
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
                    "id": "UnicomDailyClockin",
                    "name": "联通签到立减金",
                    "trigger": CronTrigger.from_crontab(self._cron),
                    "func": self.run_checkin,
                    "kwargs": {},
                }]
            except Exception as err:
                logger.error(f"联通签到立减金 Cron 配置错误：{err}")
                self._last_status = f"Cron 配置错误：{err}"
                self._update_config()
        return []

    @staticmethod
    def _env(name: str) -> str:
        return os.environ.get(name, "").strip()

    @staticmethod
    def _pick(item: Dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = item.get(key)
            if value:
                return str(value).strip()
        return ""

    def _load_accounts(self) -> List[Dict[str, str]]:
        """加载账号。优先使用多账号配置；支持标准 JSON，也支持未转义的宽松文本。"""
        accounts: List[Dict[str, str]] = []
        raw = (self._accounts_json or "").strip()
        if raw:
            try:
                data = json.loads(raw)
            except Exception:
                data = self._parse_relaxed_accounts(raw)
            if not isinstance(data, list):
                raise RuntimeError("多账号配置必须是 JSON 数组，或使用：账号名/authInfo/bizChannelInfo/tokenid/cookie 的宽松文本格式")
            for idx, item in enumerate(data, start=1):
                if not isinstance(item, dict):
                    raise RuntimeError(f"第 {idx} 个账号不是对象")
                account = {
                    "name": self._pick(item, "name", "account", "remark") or f"账号{idx}",
                    "auth_info": self._pick(item, "auth_info", "authInfo"),
                    "tokenid": self._pick(item, "tokenid", "tokenId", "tokenID"),
                    "biz_channel_info": self._pick(item, "biz_channel_info", "bizChannelInfo"),
                    "cookie": self._pick(item, "cookie", "Cookie"),
                }
                self._validate_account(account)
                accounts.append(account)
            if not accounts:
                raise RuntimeError("多账号配置为空")
            return accounts

        account = {
            "name": "默认账号",
            "auth_info": (self._auth_info or self._env("UNICOM_CLOCKIN_AUTHINFO")).strip(),
            "tokenid": (self._tokenid or self._env("UNICOM_CLOCKIN_TOKENID")).strip(),
            "biz_channel_info": (self._biz_channel_info or self._env("UNICOM_CLOCKIN_BIZCHANNELINFO")).strip(),
            "cookie": (self._cookie or self._env("UNICOM_CLOCKIN_COOKIE")).strip(),
        }
        self._validate_account(account)
        return [account]

    @staticmethod
    def _extract_balanced_json(text: str, start: int) -> Tuple[str, int]:
        """从 start 位置提取一个平衡的 JSON 对象/数组文本，容忍外层多包一层大括号。"""
        pos = start
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos < len(text) and text[pos] in '"\'':
            pos += 1
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text) or text[pos] not in "{[":
            return "", start
        open_ch = text[pos]
        close_ch = "}" if open_ch == "{" else "]"
        depth = 0
        in_str = False
        esc = False
        for i in range(pos, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    value = text[pos:i + 1].strip()
                    if value.startswith("{{") and value.endswith("}}"):
                        inner = value[1:-1].strip()
                        try:
                            json.loads(inner)
                            value = inner
                        except Exception:
                            pass
                    return value, i + 1
        return text[pos:].strip(), len(text)

    @staticmethod
    def _skip_wrapper_quote(text: str, pos: int) -> int:
        if pos < len(text) and text[pos] in '"\'':
            probe = pos + 1
            while probe < len(text) and text[probe].isspace():
                probe += 1
            if probe < len(text) and text[probe] in "{[":
                return probe
        return pos

    @staticmethod
    def _clean_relaxed_value(value: str, field: str = "") -> str:
        """清理宽松解析出来的字段值，避免请求头带入伪 JSON 的收尾符号。"""
        value = (value or "").strip()
        value = re.sub(r'^[\s,]+', '', value).strip()
        if value.startswith(('"', "'")):
            value = value[1:].strip()
        changed = True
        while changed and value:
            old_value = value
            value = value.rstrip()
            if value.endswith(','):
                value = value[:-1].rstrip()
            if value.endswith(('"', "'")):
                value = value[:-1].rstrip()
            # 只清理伪 JSON 字段外层残留；不要移除 Cookie 内部 br-session-cache 的 ] 或 }。
            if field == "tokenid":
                value = re.sub(r'\s*[}\]]\s*$', '', value).rstrip()
            changed = value != old_value
        return value.strip()

    @staticmethod
    def _strip_wrapped_json(value: str) -> str:
        value = UnicomDailyClockin._clean_relaxed_value(value)
        if value.startswith("{{") and value.endswith("}}"):
            inner = value[1:-1].strip()
            try:
                json.loads(inner)
                return inner
            except Exception:
                return inner
        return value

    @staticmethod
    def _find_next_field(segment: str, pos: int, fields: List[str]) -> int:
        """查找下一个账号字段位置，忽略 Cookie 值内部的 JSON key。"""
        positions = []
        for next_field in fields:
            pattern = re.compile(rf'(?i)(?:^|[,\s{{])"?{re.escape(next_field)}"?\s*[:：]')
            m = pattern.search(segment, pos)
            if m:
                positions.append(m.start())
        return min(positions) if positions else len(segment)

    @staticmethod
    def _extract_field_value(segment: str, field: str) -> str:
        pattern = re.compile(rf'(?i)(?:"?{re.escape(field)}"?\s*[:：])')
        matches = list(pattern.finditer(segment))
        if not matches:
            return ""
        # tokenId 会出现在 authInfo 内部；宽松解析时取最后一个 tokenid 字段才是账号请求头。
        match = matches[-1] if field == "tokenid" else matches[0]
        pos = match.end()
        while pos < len(segment) and segment[pos].isspace():
            pos += 1
        if field in ("authInfo", "bizChannelInfo"):
            pos = UnicomDailyClockin._skip_wrapper_quote(segment, pos)
            value, _ = UnicomDailyClockin._extract_balanced_json(segment, pos)
            return UnicomDailyClockin._strip_wrapped_json(value)
        if pos < len(segment) and segment[pos] in '"\'':
            pos += 1
        next_fields = ["authInfo", "bizChannelInfo", "tokenid", "cookie", "name"]
        end = UnicomDailyClockin._find_next_field(segment, pos, [f for f in next_fields if f != field])
        value = segment[pos:end].strip()
        if field == "cookie":
            value = re.sub(r'\s*"\s*}\s*,\s*{\s*$', '', value).strip()
            value = re.sub(r'\s*"\s*[,}]\s*$', '', value).strip()
            value = re.sub(r'\s*"\s*}\s*]\s*$', '', value).strip()
        return UnicomDailyClockin._clean_relaxed_value(value, field)

    @staticmethod
    def _parse_relaxed_accounts(raw: str) -> List[Dict[str, str]]:
        """解析未转义的账号配置文本。支持插件页里类似 JSON 但内层未转义的写法。"""
        name_matches = list(re.finditer(r'(?im)(?:"name"\s*[:：]\s*"([^"]+)"|^\s*(账号\s*[:：]?\s*[^\s,，]+))', raw))
        if not name_matches:
            raise RuntimeError("多账号配置解析失败：未找到账号名称，请使用 账号:xxx + authInfo/bizChannelInfo/tokenid/cookie 格式")
        accounts: List[Dict[str, str]] = []
        for idx, match in enumerate(name_matches):
            start = match.start()
            end = name_matches[idx + 1].start() if idx + 1 < len(name_matches) else len(raw)
            segment = raw[start:end]
            name = (match.group(1) or match.group(2) or f"账号{idx + 1}").strip()
            accounts.append({
                "name": name,
                "authInfo": UnicomDailyClockin._extract_field_value(segment, "authInfo"),
                "bizChannelInfo": UnicomDailyClockin._extract_field_value(segment, "bizChannelInfo"),
                "tokenid": UnicomDailyClockin._extract_field_value(segment, "tokenid"),
                "cookie": UnicomDailyClockin._extract_field_value(segment, "cookie"),
            })
        return accounts

    @staticmethod
    def _validate_account(account: Dict[str, str]) -> None:
        missing = []
        if not account.get("auth_info"):
            missing.append("authInfo")
        if not account.get("tokenid"):
            missing.append("tokenid")
        if not account.get("biz_channel_info"):
            missing.append("bizChannelInfo")
        if not account.get("cookie"):
            missing.append("Cookie")
        if missing:
            raise RuntimeError(f"{account.get('name') or '账号'} 缺少登录态配置：" + "、".join(missing))

    def _headers(self, account: Dict[str, str]) -> Dict[str, str]:
        return {
            "User-Agent": self.UA,
            "Referer": self.REFERER,
            "Origin": self.BASE,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Cookie": account["cookie"],
            "bizChannelInfo": account["biz_channel_info"],
            "authInfo": account["auth_info"],
            "tokenid": account["tokenid"],
        }

    def _post(self, account: Dict[str, str], path: str, data: dict) -> dict:
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(self.BASE + path, data=body, headers=self._headers(account), method="POST")
        text = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        return json.loads(text)


    @staticmethod
    def _pick_first(data: Dict[str, Any], keys: List[str]) -> Any:
        for key in keys:
            if key in data and data.get(key) not in (None, ""):
                return data.get(key)
        return None

    @staticmethod
    def _format_money(value: Any) -> str:
        if value in (None, ""):
            return "未知"
        try:
            return f"{float(value):.2f}"
        except Exception:
            return str(value)

    @staticmethod
    def _format_available_amount(value: Any) -> str:
        if value in (None, ""):
            return "未知"
        text = str(value).strip()
        try:
            amount = float(text)
            # queryAvailable.availableAmount 返回单位为分：3 表示 0.03 元。
            if re.fullmatch(r"\d+", text):
                amount = amount / 100
            return f"{amount:.2f}"
        except Exception:
            return text

    @staticmethod
    def _amount_parts(data: Dict[str, Any], available: Any = None) -> Tuple[str, str]:
        if available is None:
            available = UnicomDailyClockin._pick_first(data, [
                "availableAmount", "availableAmt", "usableAmount", "usableAmt",
                "canUseAmount", "balance", "remainAmount", "remainAmt",
                "couponAmount", "couponAmt", "reduceAmount", "availableCouponAmount"
            ])
        count_amount = data.get("countAmount")
        available_text = "未知" if available is None else UnicomDailyClockin._format_available_amount(available)
        count_text = UnicomDailyClockin._format_money(count_amount)
        return available_text, count_text

    @staticmethod
    def _amount_text(data: Dict[str, Any], available: Any = None) -> str:
        available_text, count_text = UnicomDailyClockin._amount_parts(data, available)
        return f"可用立减金 {available_text} 元，累计金额 {count_text} 元"

    @staticmethod
    def _format_account_label(name: str) -> str:
        name = (name or "未命名账号").strip()
        match = re.fullmatch(r"账号\s*[:：]\s*(.+)", name)
        if match:
            name = match.group(1).strip()
        elif name.startswith("账号"):
            name = name[2:].strip()
        return f"账号:{name or '未命名账号'}"

    @staticmethod
    def _make_result_line(name: str, status: str, day_text: str = "", state_text: str = "", available_text: str = "未知", count_text: str = "未知", extra: Optional[str] = None) -> str:
        parts = [UnicomDailyClockin._format_account_label(name), f"结果：{status}"]
        if day_text:
            parts.append(f"今日：{day_text}")
        parts.append(f"可用立减金：{available_text} 元")
        parts.append(f"累计金额：{count_text} 元")
        if extra:
            parts.append(f"备注：{extra}")
        return "｜".join(parts)

    @staticmethod
    def _week_text(day: int) -> str:
        week_map = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}
        return week_map.get(day, f"第{day}天")

    @staticmethod
    def _sign_state_text(value: str) -> str:
        state_map = {"0": "已签到", "1": "可签到"}
        return state_map.get(str(value), f"未知状态({value})")

    def _query_available_amount(self, account: Dict[str, str]) -> Any:
        try:
            res = self._post(account, "/ci-mcss-party-front/v1/ttlxj/queryAvailable", {})
            data = res.get("data") or {}
            if str(data.get("returnCode")) == "0":
                return data.get("availableAmount")
        except Exception as err:
            logger.warning(f"联通签到立减金查询可用立减金失败：{account.get('name') or '未命名账号'} {err}")
        return None

    def _checkin_one(self, account: Dict[str, str]) -> Tuple[str, str]:
        name = account.get("name") or "未命名账号"
        info = self._post(account, "/ci-mcss-party-front/v1/ttlxj/userDrawInfo", {})
        data = info.get("data") or {}
        rc = str(data.get("returnCode"))
        if rc != "0":
            return "失败", self._make_result_line(name, "状态查询失败", extra=f"returnCode={rc} msg={data.get('returnMsg')}")

        day = int(data.get("dayOfWeek") or 0)
        today_key = f"day{day}"
        today_state = str(data.get(today_key, ""))
        available_amount = self._query_available_amount(account)
        day_text = self._week_text(day)
        state_text = self._sign_state_text(today_state)
        if today_state != "1":
            available_text, count_text = self._amount_parts(data, available_amount)
            return "已签到/无需签到", self._make_result_line(name, "已签到/无需签到", day_text, state_text, available_text, count_text)

        draw_type = "C" if day == 7 else "B"
        res = self._post(account, "/ci-mcss-party-front/v1/ttlxj/unifyDrawNew", {
            "drawType": draw_type,
            "bizFrom": "226",
            "activityId": "TTLXJ20210330",
        })
        rdata = res.get("data") or {}
        rcode = str(rdata.get("returnCode"))
        available_amount = self._query_available_amount(account)
        available_text, count_text = self._amount_parts(rdata, available_amount)
        if rcode == "0":
            return "签到成功", self._make_result_line(name, "签到成功", day_text, "已签到", available_text, count_text)
        if rcode == "MMP372":
            return "今日已签到", self._make_result_line(name, "今日已签到", day_text, "已签到", available_text, count_text)
        return "失败", self._make_result_line(name, "签到失败", day_text, state_text, available_text, count_text, f"returnCode={rcode} msg={rdata.get('returnMsg')}")

    def run_checkin(self):
        start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("开始执行联通签到立减金")
        try:
            accounts = self._load_accounts()
            results = []
            ok_count = 0
            fail_count = 0
            for account in accounts:
                try:
                    status, text = self._checkin_one(account)
                    if status in ("签到成功", "今日已签到", "已签到/无需签到"):
                        ok_count += 1
                    else:
                        fail_count += 1
                    results.append(text)
                except Exception as err:
                    fail_count += 1
                    name = account.get("name") or "未命名账号"
                    logger.error(f"联通签到立减金账号执行异常：{name} {err}\n{traceback.format_exc()}")
                    results.append(f"{self._format_account_label(name)}｜结果：执行异常｜备注：{err}")

            status = f"执行完成：成功/无需处理 {ok_count}，失败 {fail_count}"
            summary = f"执行时间：{start}\n账号统计：成功/无需处理 {ok_count}，失败 {fail_count}"
            self._save_result(start, status, summary + "\n" + "\n".join(results))
        except Exception as err:
            logger.error(f"联通签到立减金执行异常：{err}\n{traceback.format_exc()}")
            self._save_result(start, "执行异常", str(err))

    def _save_result(self, run_time: str, status: str, result: str):
        self._last_run = run_time
        self._last_status = status
        self._last_result = result
        logger.info(f"联通签到立减金：{status}\n{result}")
        if self._notify:
            self.post_message(
                mtype=NotificationType.Plugin,
                title=f"联通签到立减金：{status}",
                text=result,
            )
        self._update_config()

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        version = getattr(settings, "VERSION_FLAG", "v1")
        cron_component = "VCronField" if version == "v2" else "VTextField"
        accounts_placeholder = '账号:0001\nauthInfo:{...}\nbizChannelInfo:{...}\ntokenid:...\ncookie:...\n\n账号:0002\nauthInfo:{...}\nbizChannelInfo:{...}\ntokenid:...\ncookie:...'
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VSwitch", "props": {"model": "notify", "label": "开启通知"}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VSwitch", "props": {"model": "onlyonce", "label": "立即运行一次"}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": cron_component, "props": {"model": "cron", "label": "执行周期 Cron", "placeholder": "5 6 * * *", "hint": "默认每天 06:05 执行", "persistent-hint": True}}]},
                            {"component": "VCol", "props": {"cols": 12}, "content": [{"component": "VAlert", "props": {"type": "info", "variant": "tonal", "text": "多账号支持标准 JSON，也支持未转义宽松文本。可直接粘贴 账号:xxx/authInfo/bizChannelInfo/tokenid/cookie，插件运行时会自动解析并转义。"}}]},
                            {"component": "VCol", "props": {"cols": 12}, "content": [{"component": "VTextarea", "props": {"model": "accounts_json", "label": "多账号配置（JSON 或宽松文本）", "placeholder": accounts_placeholder, "rows": 10, "auto-grow": False}}]},
                            {"component": "VCol", "props": {"cols": 12}, "content": [{"component": "VAlert", "props": {"type": "warning", "variant": "tonal", "text": "下面是单账号兼容配置。多账号 JSON 不为空时，将优先使用多账号配置。登录态也可留空改用容器环境变量 UNICOM_CLOCKIN_AUTHINFO / UNICOM_CLOCKIN_TOKENID / UNICOM_CLOCKIN_BIZCHANNELINFO / UNICOM_CLOCKIN_COOKIE。"}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [{"component": "VTextarea", "props": {"model": "auth_info", "label": "联通登录态 authInfo", "placeholder": "粘贴 authInfo JSON", "rows": 7, "auto-grow": False}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [{"component": "VTextarea", "props": {"model": "tokenid", "label": "联通签到请求头 tokenid", "placeholder": "请输入 tokenid", "rows": 7, "auto-grow": False}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [{"component": "VTextarea", "props": {"model": "biz_channel_info", "label": "联通登录态 bizChannelInfo", "placeholder": "粘贴 bizChannelInfo JSON", "rows": 8, "auto-grow": False}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [{"component": "VTextarea", "props": {"model": "cookie", "label": "联通活动页 Cookie", "placeholder": "粘贴完整 Cookie", "rows": 8, "auto-grow": False}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [{"component": "VTextField", "props": {"model": "last_run", "label": "上次运行", "readonly": True}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [{"component": "VTextField", "props": {"model": "last_status", "label": "运行状态", "readonly": True}}]},
                            {"component": "VCol", "props": {"cols": 12}, "content": [{"component": "VTextarea", "props": {"model": "last_result", "label": "最近结果", "readonly": True, "rows": 8, "auto-grow": True}}]},
                        ],
                    }
                ],
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "notify": True,
            "cron": "5 6 * * *",
            "accounts_json": self._accounts_json,
            "auth_info": self._auth_info,
            "tokenid": self._tokenid,
            "biz_channel_info": self._biz_channel_info,
            "cookie": self._cookie,
            "last_run": self._last_run,
            "last_status": self._last_status,
            "last_result": self._last_result,
        }

    def get_page(self) -> List[dict]:
        return [
            {
                "component": "VCard",
                "props": {"variant": "outlined", "class": "mb-3"},
                "content": [
                    {"component": "VCardTitle", "text": "联通签到立减金"},
                    {"component": "VCardSubtitle", "text": f"上次运行：{self._last_run or '未运行'}｜状态：{self._last_status or '未知'}"},
                    {"component": "VCardText", "content": [{"component": "VTextarea", "props": {"model-value": self._last_result or "暂无运行结果", "readonly": True, "auto-grow": True, "rows": 10, "variant": "outlined", "label": "最近结果"}}]},
                ],
            }
        ]

    def stop_service(self) -> None:
        pass
