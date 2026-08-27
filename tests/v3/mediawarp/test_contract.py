import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ID = "MediaWarp"
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


def test_mediawarp_has_port_configuration_and_no_federation_requirement():
    source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    assert '"port"' in source
    assert "get_render_mode" not in source
    assert "def get_api" in source
