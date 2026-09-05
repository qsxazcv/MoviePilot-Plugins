"""IkuaiAssistant Agent 工具入口辅助。"""
from typing import Any, Callable


def run_cli_tool(execute: Callable[..., Any], **kwargs: Any) -> str:
    """转发 CLI Agent 工具调用，保留原参数契约。"""
    return execute(**kwargs)


def run_skill_tool(read: Callable[..., Any], list_only: bool, name: str) -> Any:
    """转发技能查询工具调用。"""
    return read(name) if not list_only else None


def serialize_result(result: Any) -> str:
    """将工具结果序列化为稳定的中文 JSON。"""
    import json
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


def resolve_plugin(manager: Any, plugin_id: str = "IkuaiAssistant") -> Any:
    """从插件管理器获取运行中的指定插件。"""
    return manager.running_plugins.get(plugin_id)


def run_cli_plugin(manager: Any, command: str, **kwargs: Any) -> str:
    """执行 CLI 工具并统一处理插件未运行状态。"""
    plugin = resolve_plugin(manager)
    if not plugin:
        return serialize_result({"ok": False, "error": "IkuaiAssistant 插件未运行"})
    return serialize_result(plugin.run_cli_command(command=command, **kwargs))


def run_skill_plugin(manager: Any, name: str = "", list_only: bool = False) -> str:
    """读取 Skill 工具并统一处理插件未运行状态。"""
    plugin = resolve_plugin(manager)
    if not plugin:
        return serialize_result({"ok": False, "error": "IkuaiAssistant 插件未运行"})
    result = plugin.list_agent_skills() if list_only else plugin.read_agent_skill(name)
    return serialize_result(result)
