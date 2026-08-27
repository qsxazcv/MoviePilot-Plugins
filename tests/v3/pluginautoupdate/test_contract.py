import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ID = "PluginAutoUpdate"
PLUGIN_DIR = ROOT / "plugins.v3" / PLUGIN_ID.lower()


def _class():
    tree = ast.parse((PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8"))
    return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == PLUGIN_ID)


def test_metadata_and_v3_manifest_match():
    package = json.loads((ROOT / "package.v3.json").read_text(encoding="utf-8"))[PLUGIN_ID]
    attrs = {
        target.id: ast.literal_eval(item.value)
        for item in _class().body
        if isinstance(item, ast.Assign)
        for target in item.targets
        if isinstance(target, ast.Name) and target.id in {"plugin_version", "plugin_author", "plugin_icon"}
    }
    assert attrs["plugin_version"] == package["version"]
    assert attrs["plugin_author"] == package["author"]
    assert attrs["plugin_icon"] == package["icon"]
    assert (PLUGIN_DIR / "pyproject.toml").is_file()


def test_plugin_update_command_and_empty_api_contract():
    source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    assert '"cmd": "/plugin_update"' in source
    get_api = next(node for node in ast.walk(_class()) if isinstance(node, ast.FunctionDef) and node.name == "get_api")
    assert any(isinstance(node, ast.Pass) for node in ast.walk(get_api))
