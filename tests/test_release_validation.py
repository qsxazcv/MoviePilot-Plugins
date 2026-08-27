from pathlib import Path
from zipfile import ZipFile

from scripts.validate_federation import federation_asset_errors
from scripts.build_release import archive_files, build_release
from scripts.validate_release import release_zip_errors


def _write_zip(path: Path, entries: dict[str, str | bytes]) -> None:
    with ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def test_release_zip_accepts_plugin_root_and_version(tmp_path):
    archive = tmp_path / "demo_v1.2.3.zip"
    _write_zip(archive, {"demo/__init__.py": 'plugin_version = "1.2.3"\n'})
    assert release_zip_errors(archive, "Demo", "1.2.3") == []


def test_release_zip_rejects_repository_prefix_and_nested_directory(tmp_path):
    archive = tmp_path / "bad.zip"
    _write_zip(archive, {"plugins.v3/demo/demo/__init__.py": 'plugin_version = "1.0.0"\n'})
    errors = release_zip_errors(archive, "Demo", "1.0.0")
    assert any("must start" in error for error in errors)
    assert any("nested" in error for error in errors)


def test_release_zip_rejects_directory_only_archive(tmp_path):
    archive = tmp_path / "empty.zip"
    _write_zip(archive, {"demo/": ""})
    errors = release_zip_errors(archive, "Demo", "1.0.0")
    assert "release ZIP contains no files" in errors


def test_federation_references_must_exist(tmp_path):
    assets = tmp_path / "demo" / "dist" / "assets"
    assets.mkdir(parents=True)
    (assets / "remoteEntry.js").write_text(
        "import './present.js'; import './missing.css';", encoding="utf-8"
    )
    (assets / "present.js").write_text("export {}", encoding="utf-8")
    errors = federation_asset_errors(tmp_path / "demo")
    assert errors == ["demo: remoteEntry.js references missing dist/assets/missing.css"]


def test_federation_rejects_forbidden_global_style_asset(tmp_path):
    assets = tmp_path / "demo" / "dist" / "assets"
    assets.mkdir(parents=True)
    (assets / "remoteEntry.js").write_text("export {}", encoding="utf-8")
    (assets / "vuetify-main.css").write_text("/* global */", encoding="utf-8")
    errors = federation_asset_errors(tmp_path / "demo")
    assert any("forbidden federation style asset" in error for error in errors)


def test_build_release_uses_plugin_root_and_excludes_runtime_files(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins.v3" / "demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "__init__.py").write_text('plugin_version = "1.0.0"\n', encoding="utf-8")
    (plugin_dir / "__pycache__").mkdir()
    (plugin_dir / "__pycache__" / "bad.pyc").write_bytes(b"bad")
    monkeypatch.setattr("scripts.build_release.ROOT", tmp_path)
    archive = build_release("Demo", "1.0.0", tmp_path / "out")
    assert archive.name == "demo_v1.0.0.zip"
    assert release_zip_errors(archive, "Demo", "1.0.0") == []
    assert [p.name for p in archive_files(plugin_dir)] == ["__init__.py"]
