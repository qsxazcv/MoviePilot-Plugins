"""检测本次提交中版本发生变化、且启用了 release 的 V3 插件。

用法：
    python scripts/detect_release_changes.py --before <sha> [--after <sha>]
    python scripts/detect_release_changes.py --plugin-id MyPlugin

输出 JSON 数组，并写入 GITHUB_OUTPUT（在 Actions 中可用）。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.v3.json"


def read_package(ref: str | None) -> dict:
    """读取指定 git 引用中的 package.v3.json，ref 为空时读取工作区。"""
    if not ref:
        return json.loads(PACKAGE.read_text(encoding="utf-8"))
    try:
        raw = subprocess.check_output(
            ["git", "show", f"{ref}:package.v3.json"], cwd=ROOT, text=True
        )
    except subprocess.CalledProcessError:
        return {}
    return json.loads(raw)


def release_versions(package: dict) -> dict[str, str]:
    """返回启用了 release 的插件 ID 到版本号的映射。"""
    return {
        plugin_id: str(entry.get("version"))
        for plugin_id, entry in package.items()
        if isinstance(entry, dict) and entry.get("release") is True
    }


def main() -> int:
    """计算需要发版的插件列表。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", default="")
    parser.add_argument("--after", default="")
    parser.add_argument("--plugin-id", default="")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    after_pkg = read_package(args.after or None)
    before_pkg = read_package(args.before) if args.before else {}
    after_versions = release_versions(after_pkg)
    before_versions = release_versions(before_pkg)

    if args.plugin_id:
        target = args.plugin_id.strip()
        if target not in after_pkg:
            print(f"插件不存在于 package.v3.json：{target}", file=sys.stderr)
            return 1
        if after_versions.get(target) is None:
            print(f"插件未设置 release: true，跳过：{target}", file=sys.stderr)
            return 1
        plugins = [{"id": target, "dir": target.lower(), "version": after_versions[target]}]
    else:
        plugins = [
            {"id": plugin_id, "dir": plugin_id.lower(), "version": version}
            for plugin_id, version in after_versions.items()
            if before_versions.get(plugin_id) != version
        ]

    payload = json.dumps(plugins, ensure_ascii=False)
    print(payload)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"plugins={payload}\n")
            fh.write(f"has_plugins={'true' if plugins else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
