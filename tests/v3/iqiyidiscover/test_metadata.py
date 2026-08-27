from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ID = "IqiyiDiscover"
PLUGIN_DIR = ROOT / "plugins.v3" / PLUGIN_ID.lower()


def _class_assignments() -> dict[str, object]:
    tree = ast.parse((PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8"))
    plugin_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == PLUGIN_ID
    )
    values: dict[str, object] = {}
    for node in plugin_class.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                    "plugin_version", "plugin_author", "plugin_icon",
                }:
                    values[target.id] = ast.literal_eval(node.value)
    return values


def test_iqiyi_metadata_matches_v3_index() -> None:
    package = json.loads((ROOT / "package.v3.json").read_text(encoding="utf-8"))
    entry = package[PLUGIN_ID]
    values = _class_assignments()
    assert values["plugin_version"] == entry["version"]
    assert values["plugin_author"] == entry["author"]
    assert values["plugin_icon"] == entry["icon"]


def test_iqiyi_discover_module_uses_method_mapping_contract() -> None:
    source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    get_module = next(
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "get_module"
    )
    dict_returns = [
        node.value for node in ast.walk(get_module)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
    ]
    keys = {
        key.value for value in dict_returns
        for key in value.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    assert {"recognize_media", "async_recognize_media"} <= keys


def test_iqiyi_v3_manifest_exists() -> None:
    assert (PLUGIN_DIR / "pyproject.toml").is_file()
    assert (ROOT / "package.v3.json").is_file()
