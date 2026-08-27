"""Validate a MoviePilot plugin Release ZIP."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import PurePosixPath
from pathlib import Path


FORBIDDEN_PARTS = {"plugins", "plugins.v2", "plugins.v3", "__pycache__", "node_modules"}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".log", ".bak"}
VERSION_PATTERN = re.compile(r"plugin_version\s*=\s*([\"'])([^\"']+)\1")


def release_zip_errors(zip_path: Path, plugin_id: str, expected_version: str | None = None) -> list[str]:
    """Return structural and metadata errors for one release archive."""
    errors: list[str] = []
    plugin_dir = plugin_id.lower()
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
            if not names:
                return ["release ZIP is empty"]
            file_names = [name for name in names if not name.endswith("/")]
            if not file_names:
                errors.append("release ZIP contains no files")
            for name in names:
                if "\\" in name:
                    errors.append(f"backslash path is not allowed: {name}")
                    continue
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts:
                    errors.append(f"unsafe archive path: {name}")
                    continue
                if not path.parts or path.parts[0] != plugin_dir:
                    errors.append(f"archive entry must start with {plugin_dir}/: {name}")
                if len(path.parts) > 1 and path.parts[1] == plugin_dir:
                    errors.append(f"nested plugin directory is not allowed: {name}")
                if set(path.parts) & FORBIDDEN_PARTS or path.name.lower().endswith(tuple(FORBIDDEN_SUFFIXES)):
                    errors.append(f"runtime or generated artifact is not allowed: {name}")

            init_name = f"{plugin_dir}/__init__.py"
            if init_name not in names:
                errors.append(f"missing {init_name}")
            else:
                source = archive.read(init_name).decode("utf-8")
                match = VERSION_PATTERN.search(source)
                if not match:
                    errors.append(f"{init_name}: missing literal plugin_version")
                elif expected_version and match.group(2) != expected_version:
                    errors.append(
                        f"{init_name}: plugin_version={match.group(2)!r} does not match {expected_version!r}"
                    )
            return errors
    except FileNotFoundError:
        return [f"missing release ZIP: {zip_path}"]
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
        return [f"cannot validate {zip_path}: {exc}"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("plugin_id")
    parser.add_argument("--version")
    args = parser.parse_args()
    problems = release_zip_errors(args.zip_path, args.plugin_id, args.version)
    if problems:
        print("Release ZIP validation failed:")
        print("\n".join(f"- {problem}" for problem in problems))
        raise SystemExit(1)
    print("Release ZIP validation passed.")
