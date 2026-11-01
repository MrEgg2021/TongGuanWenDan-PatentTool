from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


WHITE_LIST_PATTERNS = (
    "used; unable to detect undefined names",
    "may be undefined, or defined from star imports",
)

DETERMINISTIC_PATTERNS = (
    "imported but unused",
    "is assigned to but never used",
    "shadowed by",
    "f-string is missing placeholders",
    "undefined name",
)


@dataclass
class Finding:
    line: str
    category: str


def _classify(line: str) -> str:
    text = str(line or "")
    for pat in WHITE_LIST_PATTERNS:
        if pat in text:
            return "whitelist"
    for pat in DETERMINISTIC_PATTERNS:
        if pat in text:
            return "deterministic"
    return "other"


def _run_pyflakes(targets: list[str]) -> list[str]:
    child_env = dict(os.environ)
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-m", "pyflakes", *targets],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return [line for line in output.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify pyflakes findings and enforce deterministic gate.")
    parser.add_argument("targets", nargs="*", default=["core", "gui"], help="Paths passed to pyflakes.")
    parser.add_argument("--report-json", default="", help="Optional JSON report output path.")
    parser.add_argument("--raw-output", default="", help="Optional raw pyflakes output file path.")
    parser.add_argument("--show-samples", type=int, default=20, help="How many sample lines to print per category.")
    args = parser.parse_args()

    lines = _run_pyflakes(list(args.targets))

    if args.raw_output:
        raw_path = Path(args.raw_output)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text("\n".join(lines), encoding="utf-8")

    findings: list[Finding] = []
    for line in lines:
        findings.append(Finding(line=line, category=_classify(line)))

    deterministic = [f.line for f in findings if f.category == "deterministic"]
    whitelist = [f.line for f in findings if f.category == "whitelist"]
    other = [f.line for f in findings if f.category == "other"]

    print("== pyflakes_gate summary ==")
    print(f"targets={args.targets}")
    print(f"total={len(findings)} deterministic={len(deterministic)} whitelist={len(whitelist)} other={len(other)}")

    sample_n = max(0, int(args.show_samples))
    if deterministic:
        print("-- deterministic samples --")
        for line in deterministic[:sample_n]:
            print(line)
    if whitelist:
        print("-- whitelist samples --")
        for line in whitelist[:sample_n]:
            print(line)
    if other:
        print("-- other samples --")
        for line in other[:sample_n]:
            print(line)

    if args.report_json:
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "targets": list(args.targets),
                    "total": len(findings),
                    "deterministic_count": len(deterministic),
                    "whitelist_count": len(whitelist),
                    "other_count": len(other),
                    "deterministic": deterministic,
                    "whitelist": whitelist,
                    "other": other,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # Gate rule:
    # - deterministic MUST be zero
    # - "other" MUST be zero to avoid silently ignoring unknown categories
    if deterministic or other:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
