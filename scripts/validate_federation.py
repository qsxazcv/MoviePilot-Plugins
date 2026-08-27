"""Validate V3 Vue federation assets without importing MoviePilot."""

from __future__ import annotations

import re
from pathlib import Path


ASSET_REFERENCE = re.compile(r"[\"'](\./[^\"']+\.(?:js|css))[\"']")
FORBIDDEN_GLOBAL_STYLE = re.compile(r"(?:^|[-_/])(?:vuetify|mdi)[^/]*\.css$|__federation_shared_vuetify", re.I)


def federation_asset_errors(plugin_dir: Path) -> list[str]:
    """Return errors for a plugin's remoteEntry.js and referenced assets."""
    assets_dir = plugin_dir / "dist" / "assets"
    remote_entry = assets_dir / "remoteEntry.js"
    if not remote_entry.is_file():
        return []

    errors: list[str] = []
    for path in assets_dir.rglob("*"):
        if path.is_file() and FORBIDDEN_GLOBAL_STYLE.search(path.name):
            errors.append(f"{plugin_dir.name}: forbidden federation style asset {path.relative_to(plugin_dir)}")

    try:
        source = remote_entry.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{plugin_dir.name}: cannot read {remote_entry.relative_to(plugin_dir)}: {exc}"]

    if "\\" in source:
        errors.append(f"{plugin_dir.name}: remoteEntry.js contains backslash asset paths")

    references = sorted(set(ASSET_REFERENCE.findall(source)))
    for reference in references:
        target = assets_dir / reference[2:]
        if not target.is_file():
            errors.append(f"{plugin_dir.name}: remoteEntry.js references missing {target.relative_to(plugin_dir)}")
    return errors


def validate_federation_tree(plugins_root: Path) -> list[str]:
    """Validate every V3 plugin that contains a federation entry point."""
    errors: list[str] = []
    if not plugins_root.is_dir():
        return errors
    for plugin_dir in sorted(path for path in plugins_root.iterdir() if path.is_dir()):
        errors.extend(federation_asset_errors(plugin_dir))
    return errors


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugins_root", type=Path, nargs="?", default=Path("plugins.v3"))
    args = parser.parse_args()
    problems = validate_federation_tree(args.plugins_root)
    if problems:
        print("Federation validation failed:")
        print("\n".join(f"- {problem}" for problem in problems))
        raise SystemExit(1)
    print("Federation validation passed.")
