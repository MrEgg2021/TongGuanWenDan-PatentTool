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

from core.release_notes import (
    build_release_manifest_from_commits,
    collect_release_commits,
    infer_version_from_ref,
    resolve_ref,
    write_manifest,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成发布 manifest")
    parser.add_argument("--previous-ref", required=True, help="上一个对外发布的 Git ref/tag")
    parser.add_argument("--release-ref", required=True, help="本次发布的 Git ref/tag")
    parser.add_argument("--release-version", required=True, help="本次对外版本号，如 3.1")
    parser.add_argument("--git-tag", required=True, help="本次 Git 发布标记，如 v3.1.0")
    parser.add_argument("--previous-user-version", help="上一个对外版本号；默认从 previous-ref 推断")
    parser.add_argument("--product-visible-version", help="产品界面显示版本；默认等于 release-version")
    parser.add_argument("--quality-gates-file", help="质量门 JSON 数组路径")
    parser.add_argument("--packaging-evidence-file", help="打包证据 JSON 数组路径")
    parser.add_argument("--output", help="输出 JSON 路径")
    return parser.parse_args(argv)


def _load_evidence_list(path_arg: str | None) -> list[dict]:
    if not path_arg:
        return []
    payload = json.loads(Path(path_arg).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise SystemExit(f"evidence file must be a JSON list: {path_arg}")
    normalized: list[dict] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise SystemExit(f"evidence item #{index} must be a JSON object: {path_arg}")
        normalized.append(item)
    return normalized


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = Path(args.output) if args.output else PROJECT_ROOT / "docs" / "release_notes" / "manifests" / f"{args.git_tag}.json"
    commits = collect_release_commits(PROJECT_ROOT, args.previous_ref, args.release_ref)
    quality_gates = _load_evidence_list(args.quality_gates_file)
    packaging_evidence = _load_evidence_list(args.packaging_evidence_file)
    manifest = build_release_manifest_from_commits(
        commits,
        previous_ref=args.previous_ref,
        release_ref=args.release_ref,
        release_user_version=args.release_version,
        git_tag=args.git_tag,
        previous_user_version=args.previous_user_version or infer_version_from_ref(args.previous_ref),
        product_visible_version=args.product_visible_version or args.release_version,
        previous_commit=resolve_ref(PROJECT_ROOT, args.previous_ref),
        release_commit=resolve_ref(PROJECT_ROOT, args.release_ref),
        quality_gates=quality_gates,
        packaging_evidence=packaging_evidence,
    )
    write_manifest(output_path, manifest)
    print(json.dumps({"manifest_path": str(output_path.resolve())}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
