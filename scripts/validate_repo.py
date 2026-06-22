"""Validate MoviePilot plugin repository metadata without importing MoviePilot."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_V2 = REPO_ROOT / "package.v2.json"
PACKAGE_V1 = REPO_ROOT / "package.json"
README = REPO_ROOT / "README.md"
PLUGINS_V2 = REPO_ROOT / "plugins.v2"
PLUGINS_V1 = REPO_ROOT / "plugins"

REQUIRED_PACKAGE_FIELDS = {
    "name",
    "description",
    "labels",
    "version",
    "icon",
    "author",
    "level",
    "history",
}
SENSITIVE_PATH_PARTS = {
    ".env",
    "config",
    "data",
    "cache",
    "logs",
    "tmp",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
}
SENSITIVE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".bak",
    ".tmp",
    ".secret",
    ".key",
    ".pem",
    ".crt",
    ".p12",
    ".pfx",
}


@dataclass(frozen=True)
class PluginClass:
    """Static metadata extracted from a plugin class."""

    name: str
    attrs: dict[str, Any]
    has_vue_render_mode: bool


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise AssertionError(f"missing required file: {path.relative_to(REPO_ROOT)}") from None
    except json.JSONDecodeError as exc:
        raise AssertionError(f"invalid JSON in {path.relative_to(REPO_ROOT)}: {exc}") from exc
    if not isinstance(data, dict):
        raise AssertionError(f"{path.relative_to(REPO_ROOT)} must contain a JSON object")
    return data


def literal_value(node: ast.AST) -> Any:
    """Return a safe literal value, or None for dynamic expressions."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None


def extract_plugin_classes(path: Path) -> dict[str, PluginClass]:
    """Extract top-level plugin classes and static class attributes."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        raise AssertionError(f"syntax error in {path.relative_to(REPO_ROOT)}: {exc}") from exc

    classes: dict[str, PluginClass] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        inherits_plugin_base = any(getattr(base, "id", None) == "_PluginBase" for base in node.bases)
        if not inherits_plugin_base:
            continue
        attrs: dict[str, Any] = {}
        has_vue_render_mode = False
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attrs[target.id] = literal_value(item.value)
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "get_render_mode":
                has_vue_render_mode = True
        classes[node.name] = PluginClass(node.name, attrs, has_vue_render_mode)
    return classes


def assert_package_entry(package_name: str, entry: Any, plugins_root: Path, errors: list[str]) -> None:
    """Validate one package entry against its plugin source directory."""
    if not isinstance(entry, dict):
        errors.append(f"{package_name}: package entry must be an object")
        return

    missing = [field for field in sorted(REQUIRED_PACKAGE_FIELDS) if not entry.get(field)]
    if missing:
        errors.append(f"{package_name}: missing package fields: {', '.join(missing)}")

    history = entry.get("history")
    if history is not None and not isinstance(history, dict):
        errors.append(f"{package_name}: history must be an object")

    version = str(entry.get("version") or "")
    if isinstance(history, dict) and version:
        if version not in history and f"v{version}" not in history:
            errors.append(f"{package_name}: history lacks current version {version}")

    plugin_dir = plugins_root / package_name.lower()
    init_file = plugin_dir / "__init__.py"
    if not plugin_dir.is_dir():
        errors.append(f"{package_name}: missing directory {plugin_dir.relative_to(REPO_ROOT)}")
        return
    if not init_file.is_file():
        errors.append(f"{package_name}: missing {init_file.relative_to(REPO_ROOT)}")
        return

    try:
        classes = extract_plugin_classes(init_file)
    except AssertionError as exc:
        errors.append(str(exc))
        return

    plugin_class = classes.get(package_name)
    if plugin_class is None:
        errors.append(f"{package_name}: package key must match plugin class name")
        return

    attrs = plugin_class.attrs
    expected_pairs = {
        "version": "plugin_version",
        "author": "plugin_author",
        "icon": "plugin_icon",
        "level": "auth_level",
    }
    for package_field, attr_name in expected_pairs.items():
        package_value = entry.get(package_field)
        attr_value = attrs.get(attr_name)
        if attr_value is not None and str(package_value) != str(attr_value):
            errors.append(
                f"{package_name}: {package_field}={package_value!r} "
                f"does not match {attr_name}={attr_value!r}"
            )

    if plugin_class.has_vue_render_mode:
        remote_entry = plugin_dir / "dist" / "assets" / "remoteEntry.js"
        if not remote_entry.is_file():
            errors.append(f"{package_name}: Vue render mode requires {remote_entry.relative_to(REPO_ROOT)}")


def validate_package(package_path: Path, plugins_root: Path, errors: list[str]) -> dict[str, Any]:
    """Validate a package file and return its JSON object."""
    package = load_json(package_path)
    for package_name, entry in package.items():
        assert_package_entry(package_name, entry, plugins_root, errors)
    return package


def validate_readme(package: dict[str, Any], errors: list[str]) -> None:
    """Ensure README documents every V2 package entry."""
    try:
        text = README.read_text(encoding="utf-8")
    except FileNotFoundError:
        errors.append("missing README.md")
        return

    for package_name, entry in package.items():
        version = str(entry.get("version") or "")
        if f"`{package_name}`" not in text:
            errors.append(f"README.md: missing plugin id `{package_name}`")
        if version and f"`{version}`" not in text and f"`v{version}`" not in text:
            errors.append(f"README.md: missing version {version} for {package_name}")


def tracked_or_publishable_paths() -> list[Path]:
    """Return tracked and non-ignored paths as seen by git."""
    command = ["git", "ls-files", "--cached", "--others", "--exclude-standard"]
    result = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise AssertionError(result.stderr.strip() or "git ls-files failed")
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line.strip()]


def validate_sensitive_paths(errors: list[str]) -> None:
    """Reject obvious runtime, secret, cache, and credential artifacts."""
    try:
        paths = tracked_or_publishable_paths()
    except AssertionError as exc:
        errors.append(str(exc))
        return

    for path in paths:
        rel = path.relative_to(REPO_ROOT)
        parts = {part.lower() for part in rel.parts}
        name = rel.name.lower()
        if parts & SENSITIVE_PATH_PARTS or name.endswith(tuple(SENSITIVE_SUFFIXES)):
            errors.append(f"sensitive/runtime artifact should not be publishable: {rel.as_posix()}")


def main() -> int:
    """Run all repository checks."""
    errors: list[str] = []
    package_v2 = validate_package(PACKAGE_V2, PLUGINS_V2, errors)
    if PACKAGE_V1.exists():
        validate_package(PACKAGE_V1, PLUGINS_V1, errors)
    validate_readme(package_v2, errors)
    validate_sensitive_paths(errors)

    if errors:
        print("Repository validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Repository validation passed.")
    print(f"Validated {len(package_v2)} V2 package entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
