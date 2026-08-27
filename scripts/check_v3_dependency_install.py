"""Check V3 plugin dependency manifests and optionally resolve them with uv."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path

try:
    from packaging.requirements import Requirement
except ImportError:  # pragma: no cover - packaging is supplied by CI/uv environments
    Requirement = None


ROOT = Path(__file__).resolve().parents[1]


def manifests(root: Path | None = None) -> list[Path]:
    root = root or ROOT
    return sorted(root.glob("plugins.v3/*/pyproject.toml"))


def validate_manifest(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"{path}: invalid TOML: {exc}"]
    project = document.get("project")
    if not isinstance(project, dict):
        return [f"{path}: missing [project]"]
    if not isinstance(project.get("name"), str) or not project["name"].strip():
        errors.append(f"{path}: project.name must be non-empty")
    if "dependencies" in project.get("dynamic", []):
        errors.append(f"{path}: dynamic dependencies are not supported")
    dependencies = project.get("dependencies", [])
    if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
        errors.append(f"{path}: project.dependencies must be a string array")
    elif Requirement is not None:
        for dependency in dependencies:
            try:
                Requirement(dependency)
            except Exception as exc:
                errors.append(f"{path}: invalid dependency {dependency!r}: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--static-only", action="store_true")
    parser.add_argument("--python", dest="python_version", default=None)
    parser.add_argument("--check", action="store_true", help="resolve each manifest in a temporary uv environment")
    args = parser.parse_args()
    paths = manifests()
    errors = [error for path in paths for error in validate_manifest(path)]
    if not paths:
        errors.append("no V3 pyproject.toml manifests found")
    if errors:
        print("V3 dependency manifest check failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    if args.python_version and not args.static_only:
        python_version = args.python_version or "3.14"
        for path in paths:
            command = ["uv", "pip", "install", "--dry-run", "--python", python_version, "-r", str(path)]
            result = subprocess.run(command, cwd=ROOT, check=False)
            if result.returncode:
                return result.returncode
    print(f"V3 dependency manifests valid: {len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
