#!/usr/bin/env python3
"""Repository text encoding integrity checker.

Checks UTF-8 text files for:
- decode failures
- replacement characters (U+FFFD)
- illegal control characters
- private-use characters (unless allowlisted)
- mojibake signatures
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_INCLUDE_GLOBS = [
    "AGENTS.md",
    ".editorconfig",
    ".githooks/**/*",
    ".vscode/**/*.json",
    "*.md",
    "*.py",
    "*.json",
    "*.yaml",
    "*.yml",
    "*.ps1",
    "openspec/**/*.md",
    "openspec/**/*.yaml",
    "core/**/*.py",
    "gui/**/*.py",
    "tools/**/*.py",
    "tests/**/*.py",
]

DEFAULT_EXCLUDE_GLOBS = [
    "openspec/changes/archive/**",
    "build/**",
    "dist/**",
    "**/__pycache__/**",
]

# Keep mojibake rules centralized for easy maintenance.
MOJIBAKE_REGEX_RULES = [
    ("mojibake_replacement_glyph", re.compile(r"[\u951f\ufffd]")),
    ("mojibake_punct_sequence", re.compile(r"[\u951b\u9225\u9286]{2,}")),
]

MOJIBAKE_SUSPICIOUS_CODEPOINTS = {
    0x6D60,
    0x6D93,
    0x7039,
    0x7459,
    0x7487,
    0x7F01,
    0x9225,
    0x9286,
    0x935A,
    0x9366,
    0x93B4,
    0x93C4,
    0x9468,
    0x951B,
    0x95AB,
}


@dataclass(frozen=True)
class Issue:
    path: str
    line: int
    column: int
    rule_id: str
    message: str
    snippet: str


@dataclass(frozen=True)
class AllowRule:
    path_pattern: str
    line: str  # "*" or int-like string
    rule_id: str  # "*" or specific rule id


ALLOWLIST_PATTERN = re.compile(
    r"^(?P<path>[^:]+):(?P<line>\*|\d+)(?::(?P<rule>[A-Za-z0-9_.\-*]+))?$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check repository text files for UTF-8 and mojibake issues."
    )
    parser.add_argument("--root", default=".", help="Repository root path.")
    parser.add_argument(
        "--allowlist",
        default="tools/text_encoding_allowlist.txt",
        help=(
            "Allowlist file. Format: path_glob:line[:rule_id], "
            "rule_id defaults to '*'."
        ),
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Additional include glob (can be repeated).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional exclude glob (can be repeated).",
    )
    return parser.parse_args()


def normalize_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def load_allowlist(path: Path) -> list[AllowRule]:
    if not path.exists():
        return []
    rules: list[AllowRule] = []
    for idx, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = ALLOWLIST_PATTERN.match(line)
        if not m:
            raise ValueError(f"Invalid allowlist entry at line {idx}: {raw}")
        rules.append(
            AllowRule(
                path_pattern=m.group("path"),
                line=m.group("line"),
                rule_id=m.group("rule") or "*",
            )
        )
    return rules


def is_excluded(rel_path: str, exclude_globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel_path, pat) for pat in exclude_globs)


def iter_target_files(root: Path, include_globs: list[str], exclude_globs: list[str]) -> list[Path]:
    matched: dict[str, Path] = {}
    for pattern in include_globs:
        for p in root.glob(pattern):
            if not p.is_file():
                continue
            rel = normalize_rel(p, root)
            if is_excluded(rel, exclude_globs):
                continue
            matched[rel] = p
    return [matched[k] for k in sorted(matched.keys())]


def contains_illegal_control_char(ch: str) -> bool:
    cp = ord(ch)
    return cp < 32 and ch not in ("\t", "\n", "\r")


def is_private_use_char(cp: int) -> bool:
    return (
        0xE000 <= cp <= 0xF8FF
        or 0xF0000 <= cp <= 0xFFFFD
        or 0x100000 <= cp <= 0x10FFFD
    )


def mojibake_char_score(line: str) -> int:
    return sum(1 for ch in line if ord(ch) in MOJIBAKE_SUSPICIOUS_CODEPOINTS)


def is_allowed(issue: Issue, allow_rules: list[AllowRule]) -> bool:
    for rule in allow_rules:
        if not fnmatch.fnmatch(issue.path, rule.path_pattern):
            continue
        if rule.line != "*" and int(rule.line) != issue.line:
            continue
        if rule.rule_id != "*" and rule.rule_id != issue.rule_id:
            continue
        return True
    return False


def check_file(path: Path, root: Path) -> list[Issue]:
    rel = normalize_rel(path, root)
    issues: list[Issue] = []
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        issues.append(
            Issue(
                path=rel,
                line=exc.start + 1,
                column=exc.start + 1,
                rule_id="utf8_decode_error",
                message=f"UTF-8 decode failed: {exc.reason}",
                snippet="",
            )
        )
        return issues

    for line_no, line in enumerate(text.splitlines(), 1):
        if "\ufffd" in line:
            col = line.index("\ufffd") + 1
            issues.append(
                Issue(
                    path=rel,
                    line=line_no,
                    column=col,
                    rule_id="replacement_char",
                    message="Found U+FFFD replacement character.",
                    snippet=line,
                )
            )

        for col, ch in enumerate(line, 1):
            if contains_illegal_control_char(ch):
                issues.append(
                    Issue(
                        path=rel,
                        line=line_no,
                        column=col,
                        rule_id="illegal_control_char",
                        message=f"Found illegal control character U+{ord(ch):04X}.",
                        snippet=line,
                    )
                )
            cp = ord(ch)
            if is_private_use_char(cp):
                issues.append(
                    Issue(
                        path=rel,
                        line=line_no,
                        column=col,
                        rule_id="private_use_char",
                        message=f"Found private-use character U+{cp:04X}.",
                        snippet=line,
                    )
                )

        for rule_id, pattern in MOJIBAKE_REGEX_RULES:
            m = pattern.search(line)
            if m:
                issues.append(
                    Issue(
                        path=rel,
                        line=line_no,
                        column=m.start() + 1,
                        rule_id=rule_id,
                        message=f"Matched mojibake pattern: {rule_id}",
                        snippet=line,
                    )
                )

        # Secondary heuristic: high-density suspicious mojibake characters.
        # Keep threshold conservative to avoid noise on normal Chinese text.
        if len(line) >= 12 and mojibake_char_score(line) >= 6:
            issues.append(
                Issue(
                    path=rel,
                    line=line_no,
                    column=1,
                    rule_id="mojibake_high_density",
                    message="High density of suspicious mojibake characters.",
                    snippet=line,
                )
            )

    return issues


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    include_globs = [*DEFAULT_INCLUDE_GLOBS, *args.include]
    exclude_globs = [*DEFAULT_EXCLUDE_GLOBS, *args.exclude]

    allowlist_path = (root / args.allowlist).resolve()
    allow_rules = load_allowlist(allowlist_path)

    files = iter_target_files(root, include_globs, exclude_globs)
    issues: list[Issue] = []
    for path in files:
        issues.extend(check_file(path, root))

    issues = [issue for issue in issues if not is_allowed(issue, allow_rules)]
    if not issues:
        print(f"[OK] text integrity check passed ({len(files)} files scanned).")
        return 0

    console_encoding = sys.stdout.encoding or "utf-8"
    print(f"[FAIL] text integrity check found {len(issues)} issue(s).")
    for issue in sorted(issues, key=lambda x: (x.path, x.line, x.column, x.rule_id)):
        snippet = issue.snippet.strip()
        if len(snippet) > 160:
            snippet = snippet[:157] + "..."
        safe_snippet = snippet.encode(console_encoding, errors="backslashreplace").decode(
            console_encoding, errors="ignore"
        )
        print(
            f"- {issue.path}:{issue.line}:{issue.column} "
            f"[{issue.rule_id}] {issue.message}"
        )
        if safe_snippet:
            print(f"  > {safe_snippet}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
