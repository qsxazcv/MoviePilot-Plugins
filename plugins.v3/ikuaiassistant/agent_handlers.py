"""IkuaiAssistant Agent 指南读取辅助函数。"""
from pathlib import Path
from typing import Any


def guide_dir(module_file: str) -> Path:
    """根据模块文件路径定位内置指南目录。"""
    return Path(module_file).resolve().parent / "agent_guide"


def read_guide(module_file: str, relative_path: str) -> dict[str, Any]:
    """安全读取插件内置指南文件。"""
    root = guide_dir(module_file).resolve()
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return {"ok": False, "error": "指定技能文件不存在"}
    if not target.is_file():
        return {"ok": False, "error": "指定技能文件不存在"}
    return {"ok": True, "path": relative_path, "content": target.read_text(encoding="utf-8")}


def list_guides(module_file: str) -> dict[str, Any]:
    """列出插件内置指南文件名。"""
    root = guide_dir(module_file)
    if not root.is_dir():
        return {"ok": True, "skills": []}
    return {"ok": True, "skills": sorted(path.name for path in root.glob("*.md") if path.is_file())}
