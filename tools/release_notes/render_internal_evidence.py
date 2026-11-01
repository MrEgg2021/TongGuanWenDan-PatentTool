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

from core.release_notes import load_manifest, write_internal_evidence_output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从 manifest 渲染内部发布证据")
    parser.add_argument("--manifest", required=True, help="release manifest JSON 路径")
    parser.add_argument("--output-root", help="输出根目录；默认项目根目录")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_path = Path(args.manifest).resolve()
    output_root = Path(args.output_root).resolve() if args.output_root else PROJECT_ROOT
    manifest = load_manifest(manifest_path)
    written = write_internal_evidence_output(manifest, output_root=output_root)
    payload = {"internal_evidence": str(written.resolve())}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
