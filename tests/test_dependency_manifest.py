from pathlib import Path

import scripts.check_v3_dependency_install as checker


def test_discovers_all_v3_pyprojects(tmp_path, monkeypatch):
    (tmp_path / "plugins.v3/alpha").mkdir(parents=True)
    (tmp_path / "plugins.v3/beta").mkdir(parents=True)
    (tmp_path / "plugins.v3/alpha/pyproject.toml").write_text("[project]\nname='alpha'\n", encoding="utf-8")
    (tmp_path / "plugins.v3/beta/pyproject.toml").write_text("[project]\nname='beta'\n", encoding="utf-8")
    assert [p.parent.name for p in checker.manifests(tmp_path)] == ["alpha", "beta"]


def test_rejects_missing_project_name_or_dependencies(tmp_path):
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text("[project]\ndependencies = ['requests']\n", encoding="utf-8")
    errors = checker.validate_manifest(manifest)
    assert any("project.name" in error for error in errors)


def test_rejects_invalid_dependency(tmp_path):
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        "[project]\nname = 'demo'\ndependencies = ['not a valid requirement !!!']\n",
        encoding="utf-8",
    )
    errors = checker.validate_manifest(manifest)
    assert any("invalid dependency" in error for error in errors)


def test_python_flag_runs_uv_dry_run(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins.v3/demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\ndependencies = []\n", encoding="utf-8"
    )
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    calls = []

    class Result:
        returncode = 0

    def fake_run(command, **kwargs):
        calls.append(command)
        return Result()

    monkeypatch.setattr(checker.subprocess, "run", fake_run)
    monkeypatch.setattr(checker.sys, "argv", ["check", "--python", "3.14"])
    assert checker.main() == 0
    assert calls == [["uv", "pip", "install", "--dry-run", "--python", "3.14", "-r", str(plugin_dir / "pyproject.toml")]]


def test_install_and_check_run_real_uv_commands(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins.v3/demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\ndependencies = []\n", encoding="utf-8"
    )
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    calls = []

    class Result:
        returncode = 0

    def fake_run(command, **kwargs):
        calls.append(command)
        return Result()

    monkeypatch.setattr(checker.subprocess, "run", fake_run)
    monkeypatch.setattr(
        checker.sys,
        "argv",
        ["check", "--python", "/tmp/venv/bin/python", "--install", "--check"],
    )
    assert checker.main() == 0
    assert calls == [
        [
            "uv",
            "pip",
            "install",
            "--python",
            "/tmp/venv/bin/python",
            "-r",
            str(plugin_dir / "pyproject.toml"),
        ],
        ["uv", "pip", "check", "--python", "/tmp/venv/bin/python"],
    ]
