from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _log_path() -> Path:
    return _repo_root() / "conversion.log"


def _artifact_dir() -> Path:
    return _repo_root() / "artifacts" / "manual_retest"


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _run_cmd(cmd: list[str], cwd: Path) -> int:
    print(f"[RUN] {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(cwd), check=False)
    print(f"[EXIT] {proc.returncode}")
    return int(proc.returncode)


def _prepare(run_checks: bool, launch_gui: bool) -> int:
    root = _repo_root()
    log = _log_path()
    artifact = _artifact_dir()
    artifact.mkdir(parents=True, exist_ok=True)

    if log.exists():
        log.unlink()
        print(f"[OK] removed old log: {log}")
    else:
        print(f"[OK] log not found, no need to clean: {log}")

    checks: list[tuple[str, list[str]]] = []
    if run_checks:
        checks = [
            ("compileall", [sys.executable, "-m", "compileall", "-q", "."]),
            (
                "formal_review_tests",
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_formal_review*.py"],
            ),
            (
                "openspec_validate",
                ["cmd", "/c", "openspec", "validate", "--all"]
                if os.name == "nt" else ["openspec", "validate", "--all"],
            ),
        ]

    failed: list[str] = []
    for name, cmd in checks:
        code = _run_cmd(cmd, root)
        if code != 0:
            failed.append(name)

    if failed:
        print("[FAIL] baseline checks failed:", ", ".join(failed))
        return 1

    if launch_gui:
        print("[RUN] launching gui_app.py ...")
        subprocess.Popen([sys.executable, "gui_app.py"], cwd=str(root))
    else:
        print("[SKIP] GUI launch disabled")

    print("")
    print("== Manual Retest Steps ==")
    print("A) Word 修订接受与窗口保护")
    print("1. 用含修订的 DOCX 走一次普通转换流程（不是形式审查入口）。")
    print("2. 确认不再出现“非活动窗口”导致的 AcceptAll 失败。")
    print("B) 形式审查与修订写回")
    print("1. 进入“形式审查”页面，选择自己准备的本地测试文档。")
    print("2. 点击“解析”->“开始审查”->“生成附图标记修订”。")
    print("3. 完成后回到终端执行 collect。")
    print("")
    print("Collect command:")
    print(f"{sys.executable} tools/quality/manual_retest_helper.py collect")
    return 0


def _read_log_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    return text.splitlines()


def _match_lines(lines: list[str], pattern: str) -> list[str]:
    rx = re.compile(pattern)
    return [line for line in lines if rx.search(line)]


def _extract_revision_pairs(write_lines: list[str]) -> tuple[list[int], list[int]]:
    before: list[int] = []
    after: list[int] = []
    rb = re.compile(r"revision_count_before=(\d+)")
    ra = re.compile(r"revision_count_after=(\d+)")
    for line in write_lines:
        mb = rb.search(line)
        if mb:
            before.append(int(mb.group(1)))
        ma = ra.search(line)
        if ma:
            after.append(int(ma.group(1)))
    return before, after


def _latest_pairs_growth(before: list[int], after: list[int]) -> bool | None:
    if not before or not after:
        return None
    n = min(len(before), len(after))
    if n <= 0:
        return None
    return any(after[i] > before[i] for i in range(n))


def _collect(report_name: str = "") -> int:
    log = _log_path()
    artifact = _artifact_dir()
    artifact.mkdir(parents=True, exist_ok=True)

    lines = _read_log_lines(log)
    if not lines:
        print(f"[FAIL] log not found or empty: {log}")
        return 1

    accept_lines = _match_lines(lines, r"\[ACCEPT_ALL\]")
    accept_primary_ok = _match_lines(lines, r"\[ACCEPT_ALL\]\s+method=AcceptAllRevisions\s+ok=True")
    accept_fallback_ok = _match_lines(lines, r"\[ACCEPT_ALL\]\s+method=Revisions\.AcceptAll\s+ok=True")
    non_active_err = _match_lines(lines, r"非活动状态|non[- ]?active")

    punct_lines = _match_lines(lines, r"\[formal_review\]\[punct\]")
    punct_claims = _match_lines(punct_lines, r"\bclaims\b")
    punct_desc = _match_lines(punct_lines, r"\bdescription\b")
    punct_abs = _match_lines(punct_lines, r"\babstract\b")

    comment_sync_lines = _match_lines(lines, r"\[formal_review\]\[comment_sync\]")
    comment_has_hist = _match_lines(comment_sync_lines, r"strict_failed=|loose_rescued=|final_failed=")

    write_lines = _match_lines(lines, r"\[formal_review\]\[write_executor\]")
    before, after = _extract_revision_pairs(write_lines)
    growth = _latest_pairs_growth(before, after)
    rollback_lines = _match_lines(write_lines, r"rollback")

    accept_status = "PASS"
    if not accept_lines:
        accept_status = "INCONCLUSIVE"
    elif non_active_err:
        accept_status = "FAIL"

    formal_status = "PASS"
    if not punct_claims or not punct_desc or not punct_abs:
        formal_status = "FAIL"
    if not comment_has_hist:
        formal_status = "FAIL"
    if growth is False:
        formal_status = "FAIL"

    overall = "PASS"
    if accept_status == "FAIL" or formal_status == "FAIL":
        overall = "FAIL"
    elif accept_status == "INCONCLUSIVE":
        overall = "INCONCLUSIVE"

    stamp = _timestamp()
    base_name = report_name.strip() or f"manual_retest_report_{stamp}"
    md_path = artifact / f"{base_name}.md"
    json_path = artifact / f"{base_name}.json"
    snippet_path = artifact / f"{base_name}.snippets.log"

    snippets: list[str] = []
    snippets.extend(accept_lines[-20:])
    snippets.extend(punct_lines[-20:])
    snippets.extend(comment_sync_lines[-40:])
    snippets.extend(write_lines[-40:])
    snippet_path.write_text("\n".join(snippets), encoding="utf-8")

    md_lines = [
        f"# Manual Retest Report ({stamp})",
        "",
        f"- overall: **{overall}**",
        f"- acceptall: **{accept_status}**",
        f"- formal_review: **{formal_status}**",
        f"- log_path: `{log}`",
        "",
        "## AcceptAll",
        f"- accept_lines: {len(accept_lines)}",
        f"- primary_ok(AcceptAllRevisions): {len(accept_primary_ok)}",
        f"- fallback_ok(Revisions.AcceptAll): {len(accept_fallback_ok)}",
        f"- non_active_error_lines: {len(non_active_err)}",
        "",
        "## Formal Review",
        f"- punct_claims_lines: {len(punct_claims)}",
        f"- punct_description_lines: {len(punct_desc)}",
        f"- punct_abstract_lines: {len(punct_abs)}",
        f"- comment_sync_histogram_lines: {len(comment_has_hist)}",
        f"- write_executor_before_count: {len(before)}",
        f"- write_executor_after_count: {len(after)}",
        f"- revision_growth_detected: {growth}",
        f"- rollback_log_lines: {len(rollback_lines)}",
        "",
        "## Evidence Files",
        f"- snippets: `{snippet_path}`",
        f"- json: `{json_path}`",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    payload = {
        "timestamp": stamp,
        "overall": overall,
        "acceptall": {
            "status": accept_status,
            "accept_lines": len(accept_lines),
            "primary_ok": len(accept_primary_ok),
            "fallback_ok": len(accept_fallback_ok),
            "non_active_error_lines": len(non_active_err),
        },
        "formal_review": {
            "status": formal_status,
            "punct_claims_lines": len(punct_claims),
            "punct_description_lines": len(punct_desc),
            "punct_abstract_lines": len(punct_abs),
            "comment_sync_histogram_lines": len(comment_has_hist),
            "write_executor_before_count": len(before),
            "write_executor_after_count": len(after),
            "revision_growth_detected": growth,
            "rollback_log_lines": len(rollback_lines),
        },
        "files": {
            "log_path": str(log),
            "report_md": str(md_path),
            "report_json": str(json_path),
            "snippets": str(snippet_path),
        },
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] report: {md_path}")
    print(f"[OK] json: {json_path}")
    print(f"[OK] snippets: {snippet_path}")
    print(f"[RESULT] overall={overall} acceptall={accept_status} formal_review={formal_status}")
    return 0 if overall in {"PASS", "INCONCLUSIVE"} else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Manual GUI retest helper (prepare/collect).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prepare = sub.add_parser("prepare", help="Clean log, optional baseline checks, and optionally launch GUI.")
    p_prepare.add_argument("--run-checks", action="store_true", help="Run baseline checks before manual GUI steps.")
    p_prepare.add_argument("--no-launch-gui", action="store_true", help="Do not launch gui_app.py.")

    p_collect = sub.add_parser("collect", help="Collect conversion.log evidence and generate report.")
    p_collect.add_argument("--report-name", default="", help="Custom output report base name.")

    args = parser.parse_args()

    if args.cmd == "prepare":
        return _prepare(run_checks=bool(args.run_checks), launch_gui=not bool(args.no_launch_gui))
    if args.cmd == "collect":
        return _collect(report_name=str(args.report_name or ""))
    return 2


if __name__ == "__main__":
    sys.exit(main())
