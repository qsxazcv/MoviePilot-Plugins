from pathlib import Path

import scripts.validate_repo as validator


def _plugin_source(version: str = "1.0.0") -> str:
    return f'''from app.plugins import _PluginBase\n\n\nclass Demo(_PluginBase):\n    plugin_version = "{version}"\n    plugin_author = "tester"\n    plugin_icon = "demo.png"\n    auth_level = 1\n'''


def _write_fixture(root: Path, *, version: str = "1.0.0", bad_manifest: bool = False) -> None:
    (root / "plugins.v3/demo").mkdir(parents=True)
    (root / "plugins.v3/demo/__init__.py").write_text(_plugin_source(version), encoding="utf-8")
    (root / "plugins.v3/demo/pyproject.toml").write_text(
        '[project]\nname = "moviepilot-plugin-demo"\ndynamic = ["version"]\n'
        'requires-python = ">=3.12"\ndependencies = ["requests"]\n',
        encoding="utf-8",
    )
    if bad_manifest:
        (root / "plugins.v3/demo/pyproject.toml").write_text(
            '[project]\nname = "moviepilot-plugin-demo"\ndependencies = ["not a valid requirement !!!"]\n',
            encoding="utf-8",
        )
    (root / "package.v3.json").write_text(
        '{"Demo": {"name": "Demo", "description": "Demo", "labels": "test", '
        f'"version": "{version}", "icon": "demo.png", "author": "tester", '
        f'"level": 1, "history": {{"{version}": "test"}}, '
        '"system_version": ">=3.0.0"}}',
        encoding="utf-8",
    )
    (root / "README.md").write_text(f"`Demo` `{version}`\n", encoding="utf-8")


def test_validator_checks_v3_index(tmp_path, monkeypatch):
    _write_fixture(tmp_path)
    monkeypatch.setattr(validator, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(validator, "PACKAGE_V3", tmp_path / "package.v3.json")
    monkeypatch.setattr(validator, "README", tmp_path / "README.md")
    monkeypatch.setattr(validator, "PLUGINS_V3", tmp_path / "plugins.v3")
    monkeypatch.setattr(validator, "LEGACY_PACKAGE", tmp_path / "package.json")
    monkeypatch.setattr(validator, "LEGACY_PLUGINS", tmp_path / "plugins")
    monkeypatch.setattr(validator, "tracked_or_publishable_paths", lambda: [])
    errors = []
    validator.validate_repository(errors)
    assert errors == []


def test_validator_rejects_v3_version_mismatch(tmp_path, monkeypatch):
    _write_fixture(tmp_path, version="1.0.0")
    package = (tmp_path / "package.v3.json").read_text(encoding="utf-8").replace('"1.0.0"', '"2.0.0"', 1)
    (tmp_path / "package.v3.json").write_text(package, encoding="utf-8")
    monkeypatch.setattr(validator, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(validator, "PACKAGE_V3", tmp_path / "package.v3.json")
    monkeypatch.setattr(validator, "README", tmp_path / "README.md")
    monkeypatch.setattr(validator, "PLUGINS_V3", tmp_path / "plugins.v3")
    monkeypatch.setattr(validator, "LEGACY_PACKAGE", tmp_path / "package.json")
    monkeypatch.setattr(validator, "LEGACY_PLUGINS", tmp_path / "plugins")
    monkeypatch.setattr(validator, "tracked_or_publishable_paths", lambda: [])
    errors = []
    validator.validate_repository(errors)
    assert any("plugin_version" in error or "version" in error for error in errors)


def test_validator_rejects_invalid_v3_dependency_manifest(tmp_path, monkeypatch):
    _write_fixture(tmp_path, bad_manifest=True)
    monkeypatch.setattr(validator, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(validator, "PACKAGE_V3", tmp_path / "package.v3.json")
    monkeypatch.setattr(validator, "README", tmp_path / "README.md")
    monkeypatch.setattr(validator, "PLUGINS_V3", tmp_path / "plugins.v3")
    monkeypatch.setattr(validator, "LEGACY_PACKAGE", tmp_path / "package.json")
    monkeypatch.setattr(validator, "LEGACY_PLUGINS", tmp_path / "plugins")
    monkeypatch.setattr(validator, "tracked_or_publishable_paths", lambda: [])
    errors = []
    validator.validate_repository(errors)
    assert any("dependency" in error.lower() for error in errors)


def test_validator_rejects_removed_v2_layout(tmp_path, monkeypatch):
    _write_fixture(tmp_path)
    (tmp_path / "package.v2.json").write_text("{}", encoding="utf-8")
    (tmp_path / "plugins.v2").mkdir()
    monkeypatch.setattr(validator, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(validator, "PACKAGE_V3", tmp_path / "package.v3.json")
    monkeypatch.setattr(validator, "README", tmp_path / "README.md")
    monkeypatch.setattr(validator, "PLUGINS_V3", tmp_path / "plugins.v3")
    monkeypatch.setattr(validator, "V2_PACKAGE", tmp_path / "package.v2.json")
    monkeypatch.setattr(validator, "V2_PLUGINS", tmp_path / "plugins.v2")
    monkeypatch.setattr(validator, "LEGACY_PACKAGE", tmp_path / "package.json")
    monkeypatch.setattr(validator, "LEGACY_PLUGINS", tmp_path / "plugins")
    monkeypatch.setattr(validator, "tracked_or_publishable_paths", lambda: [])
    errors = []
    validator.validate_repository(errors)
    assert any("package.v2.json" in error for error in errors)
    assert any("plugins.v2" in error for error in errors)
