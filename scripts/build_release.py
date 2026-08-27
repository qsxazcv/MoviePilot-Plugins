"""Build deterministic V3 plugin Release ZIP archives from package.v3.json."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

try:
    from scripts.validate_release import release_zip_errors
except ModuleNotFoundError:  # Support direct execution: python scripts/build_release.py
    from validate_release import release_zip_errors


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.v3.json"
DEFAULT_OUTPUT = ROOT / "dist" / "releases"
EXCLUDED_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".log", ".bak", ".tmp"}


def load_release_plugins(package_path: Path = PACKAGE) -> list[tuple[str, str]]:
    """Return V3 release-enabled plugin IDs and versions in index order."""
    package = json.loads(package_path.read_text(encoding="utf-8"))
    return [
        (plugin_id, str(entry["version"]))
        for plugin_id, entry in package.items()
        if isinstance(entry, dict) and entry.get("release") is True
    ]


def archive_files(plugin_dir: Path) -> list[Path]:
    """Return publishable files below one plugin directory."""
    return sorted(
        path
        for path in plugin_dir.rglob("*")
        if path.is_file()
        and not set(path.relative_to(plugin_dir).parts) & EXCLUDED_PARTS
        and path.suffix.lower() not in EXCLUDED_SUFFIXES
    )


def build_release(plugin_id: str, version: str, output_dir: Path = DEFAULT_OUTPUT) -> Path:
    """Build and validate one plugin archive."""
    plugin_dir = ROOT / "plugins.v3" / plugin_id.lower()
    if not plugin_dir.is_dir():
        raise FileNotFoundError(f"missing plugin directory: {plugin_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{plugin_id.lower()}_v{version}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in archive_files(plugin_dir):
            relative = source.relative_to(plugin_dir).as_posix()
            archive.write(source, f"{plugin_id.lower()}/{relative}")
    errors = release_zip_errors(archive_path, plugin_id, version)
    if errors:
        raise ValueError("; ".join(errors))
    return archive_path


def build_all(output_dir: Path = DEFAULT_OUTPUT) -> list[Path]:
    """Build all release-enabled V3 plugin archives."""
    return [build_release(plugin_id, version, output_dir) for plugin_id, version in load_release_plugins()]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-id")
    parser.add_argument("--version")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if bool(args.plugin_id) != bool(args.version):
        parser.error("--plugin-id and --version must be provided together")
    archives = (
        [build_release(args.plugin_id, args.version, args.output)]
        if args.plugin_id
        else build_all(args.output)
    )
    for archive in archives:
        print(archive)
