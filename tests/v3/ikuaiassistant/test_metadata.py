from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ID = "IkuaiAssistant"
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


def test_ikuai_metadata_matches_v3_index() -> None:
    package = json.loads((ROOT / "package.v3.json").read_text(encoding="utf-8"))
    entry = package[PLUGIN_ID]
    values = _class_assignments()
    assert values["plugin_version"] == entry["version"]
    assert values["plugin_author"] == entry["author"]
    assert values["plugin_icon"] == entry["icon"]


def test_ikuai_bundled_cli_is_nonempty_elf() -> None:
    binary = PLUGIN_DIR / "bin" / "ikuai-cli"
    assert binary.is_file()
    assert binary.stat().st_size > 0
    assert binary.read_bytes()[:4] == b"\x7fELF"


def test_ikuai_v3_manifest_exists() -> None:
    assert (PLUGIN_DIR / "pyproject.toml").is_file()
    assert (ROOT / "package.v3.json").is_file()
