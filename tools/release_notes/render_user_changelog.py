from __future__ import annotations

# Direct-script support mutates sys.path before project imports.
# ruff: noqa: E402

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.release_notes import load_manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="用户更新日志现已改为手工维护")
    parser.add_argument("--manifest", required=True, help="release manifest JSON 路径")
    parser.add_argument("--output-root", help="输出根目录；默认项目根目录")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_path = Path(args.manifest).resolve()
    output_root = Path(args.output_root).resolve() if args.output_root else PROJECT_ROOT
    manifest = load_manifest(manifest_path)
    git_tag = str(manifest.get("git_tag") or "").strip() or "<version>"
    changelog_path = output_root / "用户使用手册+更新日志" / "更新日志" / f"{git_tag}.md"
    index_path = output_root / "用户使用手册+更新日志" / "更新日志.md"
    payload = {
        "error": "用户更新日志已改为手工维护，脚本不会再覆盖最终对外文案。",
        "manual_user_changelog": str(changelog_path.resolve()),
        "manual_changelog_index": str(index_path.resolve()),
        "recommended_command": "python tools/release_notes/render_internal_evidence.py --manifest <manifest>",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
