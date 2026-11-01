from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _is_forbidden_file(path: Path) -> bool:
    name = path.name.lower()
    if ".pyc." in name:
        return True
    if name.endswith(".pyc") or name.endswith(".pyo"):
        return True
    return False


def _scan_tests_tree(root: Path) -> dict[str, list[str]]:
    bad_dirs: list[str] = []
    bad_files: list[str] = []

    if not root.exists():
        return {"bad_dirs": bad_dirs, "bad_files": bad_files}

    for path in root.rglob("*"):
        if path.is_dir():
            if path.name == "__pycache__":
                bad_dirs.append(str(path).replace("\\", "/"))
            continue
        if path.is_file() and _is_forbidden_file(path):
            bad_files.append(str(path).replace("\\", "/"))

    bad_dirs.sort()
    bad_files.sort()
    return {"bad_dirs": bad_dirs, "bad_files": bad_files}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail when tests tree contains compiled/cache artifacts.")
    parser.add_argument("--tests-root", default="tests", help="Path to tests root directory.")
    parser.add_argument("--report-json", default="", help="Optional JSON report output path.")
    args = parser.parse_args()

    root = Path(args.tests_root)
    result = _scan_tests_tree(root)
    bad_dirs = result["bad_dirs"]
    bad_files = result["bad_files"]

    root_norm = str(root).replace("\\", "/")

    print("== check_tests_artifacts summary ==")
    print(f"tests_root={root_norm}")
    print(f"bad_dirs={len(bad_dirs)} bad_files={len(bad_files)}")

    if bad_dirs:
        print("-- bad dirs --")
        for item in bad_dirs[:50]:
            print(item)
    if bad_files:
        print("-- bad files --")
        for item in bad_files[:50]:
            print(item)

    if args.report_json:
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "tests_root": str(root).replace("\\", "/"),
                    "bad_dirs": bad_dirs,
                    "bad_files": bad_files,
                    "bad_dirs_count": len(bad_dirs),
                    "bad_files_count": len(bad_files),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    return 1 if (bad_dirs or bad_files) else 0


if __name__ == "__main__":
    sys.exit(main())
