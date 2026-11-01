from __future__ import annotations

# Direct-script support mutates sys.path before project imports.
# ruff: noqa: E402

import argparse
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.response_correction import parse_notice_source


TARGET_SAMPLE_DIRS: tuple[tuple[str, str], ...] = (
    ("审查意见", "官方通知书文件参考/有list通知书/审查意见"),
    ("补正通知书", "官方通知书文件参考/有list通知书/补正通知书"),
)


def _iter_zip_files(sample_root: Path) -> list[Path]:
    if not sample_root.exists():
        return []
    return sorted(path for path in sample_root.iterdir() if path.is_file() and path.suffix.lower() == ".zip")


def _collect_rows(base_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for category, relative_dir in TARGET_SAMPLE_DIRS:
        sample_dir = (base_dir / relative_dir).resolve()
        for zip_path in _iter_zip_files(sample_dir):
            parsed = parse_notice_source(str(zip_path))
            meta = parsed.meta
            rows.append(
                {
                    "category": category,
                    "file_name": zip_path.name,
                    "notice_name": str(meta.notice_name or "").strip(),
                    "issue_date": str(meta.issue_date or "").strip(),
                    "doc_serial": str(meta.doc_serial or "").strip(),
                    "meta_source": str(parsed.meta_source or "").strip(),
                    "errors": "；".join(str(item or "").strip() for item in (parsed.errors or ()) if str(item or "").strip()),
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="审计答复/补正通知书样本的字段命中情况。")
    parser.add_argument(
        "--base-dir",
        default=".",
        help="仓库根目录；默认当前工作目录。",
    )
    parser.add_argument(
        "--csv",
        default="",
        help="可选：把审计结果另存为 CSV 文件。",
    )
    args = parser.parse_args()

    base_dir = Path(str(args.base_dir or ".")).resolve()
    rows = _collect_rows(base_dir)
    if not rows:
        print("未找到审查意见/补正通知书样本。")
        return 1

    headers = ["category", "file_name", "notice_name", "issue_date", "doc_serial", "meta_source", "errors"]
    print("\t".join(headers))
    for row in rows:
        print("\t".join(str(row.get(header, "") or "") for header in headers))

    csv_path = str(args.csv or "").strip()
    if csv_path:
        target = Path(csv_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8-sig", newline="") as file_obj:
            writer = csv.DictWriter(file_obj, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nCSV 已写入：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
