import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ID = "weiyuncookie"
PLUGIN_DIR = ROOT / "plugins.v3" / PLUGIN_ID


def _plugin_class():
    tree = ast.parse((PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8"))
    return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == PLUGIN_ID)


def test_metadata_and_vue_assets_match():
    package = json.loads((ROOT / "package.v3.json").read_text(encoding="utf-8"))["weiyuncookie"]
    attrs = {
        target.id: ast.literal_eval(item.value)
        for item in _plugin_class().body
        if isinstance(item, ast.Assign)
        for target in item.targets
        if isinstance(target, ast.Name) and target.id in {"plugin_version", "plugin_author", "plugin_icon"}
    }
    assert attrs["plugin_version"] == package["version"]
    assert attrs["plugin_author"] == package["author"]
    assert attrs["plugin_icon"] == package["icon"]
    assert (PLUGIN_DIR / "dist/assets/remoteEntry.js").is_file()


def test_commands_api_service_and_render_mode_contracts():
    source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    assert source.count('"cmd": "/weiyun_') == 3
    assert source.count('"path": "/') == 7
    assert '"id": "weiyuncookie_check"' in source
    assert 'return "vue", "dist/assets"' in source


def test_lifecycle_stop_contract():
    source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    assert "_stop_event" in source
    assert "stop_event.set()" in source
    assert "thread.join(timeout=2)" in source
    assert "self._login_running = False" in source
