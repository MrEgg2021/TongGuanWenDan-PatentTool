from __future__ import annotations

import argparse
import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path


EXCLUDED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "output",
    "temp_processing",
}

CLEANUP_CANDIDATE_TOKENS = (
    "deprecated",
    "diagnose",
    "experiment",
    "legacy",
    "old",
    "temp",
    "test_batch",
    "unused",
)


@dataclass(frozen=True)
class FunctionRow:
    path: str
    name: str
    lineno: int
    length: int
    nesting_depth: int


@dataclass(frozen=True)
class FileRow:
    path: str
    lines: int
    function_count: int
    broad_except_count: int
    star_import_count: int
    parse_error: str = ""


@dataclass(frozen=True)
class StarImportRow:
    path: str
    lineno: int
    module: str


@dataclass(frozen=True)
class CleanupCandidateRow:
    path: str
    reason: str


def _to_posix(path: Path) -> str:
    return path.as_posix()


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def _iter_python_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if _is_excluded(rel):
            continue
        files.append(path)
    return sorted(files, key=lambda item: _to_posix(item.relative_to(root)))


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _nesting_depth(node: ast.AST) -> int:
    nested_types = (
        ast.AsyncFor,
        ast.AsyncWith,
        ast.For,
        ast.If,
        ast.Match,
        ast.Try,
        ast.While,
        ast.With,
    )
    max_depth = 0
    stack = [(child, 1) for child in getattr(node, "body", [])]
    while stack:
        current, depth = stack.pop()
        max_depth = max(max_depth, depth)
        for child in ast.iter_child_nodes(current):
            next_depth = depth + 1 if isinstance(child, nested_types) else depth
            stack.append((child, next_depth))
    return max_depth


def _is_broad_except(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    if isinstance(handler.type, ast.Name):
        return handler.type.id in {"Exception", "BaseException"}
    if isinstance(handler.type, ast.Tuple):
        return any(isinstance(item, ast.Name) and item.id in {"Exception", "BaseException"} for item in handler.type.elts)
    return False


def _scan_file(root: Path, path: Path) -> tuple[FileRow, list[FunctionRow], list[StarImportRow]]:
    rel = _to_posix(path.relative_to(root))
    text = _read_source(path)
    lines = text.splitlines()
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        return (
            FileRow(
                path=rel,
                lines=len(lines),
                function_count=0,
                broad_except_count=0,
                star_import_count=0,
                parse_error=f"{exc.__class__.__name__}: {exc}",
            ),
            [],
            [],
        )

    functions: list[FunctionRow] = []
    broad_except_count = 0
    star_imports: list[StarImportRow] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_lineno = int(getattr(node, "end_lineno", node.lineno))
            functions.append(
                FunctionRow(
                    path=rel,
                    name=node.name,
                    lineno=int(node.lineno),
                    length=end_lineno - int(node.lineno) + 1,
                    nesting_depth=_nesting_depth(node),
                )
            )
        elif isinstance(node, ast.ExceptHandler) and _is_broad_except(node):
            broad_except_count += 1
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    star_imports.append(
                        StarImportRow(
                            path=rel,
                            lineno=int(node.lineno),
                            module=str(node.module or ""),
                        )
                    )

    return (
        FileRow(
            path=rel,
            lines=len(lines),
            function_count=len(functions),
            broad_except_count=broad_except_count,
            star_import_count=len(star_imports),
        ),
        functions,
        star_imports,
    )


def _cleanup_candidates(files: list[Path], root: Path) -> list[CleanupCandidateRow]:
    rows: list[CleanupCandidateRow] = []
    for path in files:
        rel = _to_posix(path.relative_to(root))
        lowered = rel.casefold()
        matched = [token for token in CLEANUP_CANDIDATE_TOKENS if token in lowered]
        if matched:
            rows.append(CleanupCandidateRow(path=rel, reason=f"path token: {', '.join(matched)}"))
    return rows


def build_inventory(root: Path) -> dict[str, object]:
    root = root.resolve()
    files = _iter_python_files(root)
    file_rows: list[FileRow] = []
    function_rows: list[FunctionRow] = []
    star_import_rows: list[StarImportRow] = []

    for path in files:
        file_row, functions, star_imports = _scan_file(root, path)
        file_rows.append(file_row)
        function_rows.extend(functions)
        star_import_rows.extend(star_imports)

    large_files = sorted(file_rows, key=lambda item: (-item.lines, item.path))[:40]
    long_functions = sorted(function_rows, key=lambda item: (-item.length, item.path, item.lineno))[:60]
    broad_except_files = sorted(
        (item for item in file_rows if item.broad_except_count),
        key=lambda item: (-item.broad_except_count, item.path),
    )[:40]
    star_import_files = sorted(star_import_rows, key=lambda item: (item.path, item.lineno))
    parse_errors = [item for item in file_rows if item.parse_error]
    cleanup_candidates = _cleanup_candidates(files, root)

    return {
        "summary": {
            "python_files": len(file_rows),
            "python_lines": sum(item.lines for item in file_rows),
            "functions": len(function_rows),
            "broad_except_handlers": sum(item.broad_except_count for item in file_rows),
            "star_imports": len(star_import_rows),
            "parse_errors": len(parse_errors),
            "cleanup_candidates": len(cleanup_candidates),
        },
        "large_files": [asdict(item) for item in large_files],
        "long_functions": [asdict(item) for item in long_functions],
        "broad_except_files": [asdict(item) for item in broad_except_files],
        "star_imports": [asdict(item) for item in star_import_files],
        "parse_errors": [asdict(item) for item in parse_errors],
        "cleanup_candidates": [asdict(item) for item in cleanup_candidates],
    }


def _markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    out = ["| " + " | ".join(headers) + " |"]
    out.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        out.append("| " + " | ".join(str(value).replace("\n", " ") for value in row) + " |")
    return "\n".join(out)


def render_markdown(inventory: dict[str, object]) -> str:
    summary = inventory["summary"]
    assert isinstance(summary, dict)
    lines = [
        "# Project-Wide Codebase Audit Baseline",
        "",
        "This report is generated by `python tools/quality/project_audit_inventory.py`.",
        "Cleanup candidates are inventory signals only; they are not deletion proof.",
        "",
        "## Summary",
        "",
        _markdown_table(
            ["Metric", "Value"],
            [[key, value] for key, value in summary.items()],
        ),
        "",
        "## Largest Python Files",
        "",
        _markdown_table(
            ["Path", "Lines", "Functions", "Broad Except", "Star Imports"],
            [
                [
                    item["path"],
                    item["lines"],
                    item["function_count"],
                    item["broad_except_count"],
                    item["star_import_count"],
                ]
                for item in inventory["large_files"]
            ],
        ),
        "",
        "## Longest Functions",
        "",
        _markdown_table(
            ["Path", "Line", "Function", "Length", "Nesting"],
            [
                [item["path"], item["lineno"], item["name"], item["length"], item["nesting_depth"]]
                for item in inventory["long_functions"]
            ],
        ),
        "",
        "## Broad Exception Hotspots",
        "",
        _markdown_table(
            ["Path", "Broad Except Count"],
            [[item["path"], item["broad_except_count"]] for item in inventory["broad_except_files"]],
        ),
        "",
        "## Star Imports",
        "",
        _markdown_table(
            ["Path", "Line", "Module"],
            [[item["path"], item["lineno"], item["module"]] for item in inventory["star_imports"]],
        ),
        "",
        "## Heuristic Cleanup Candidates",
        "",
        _markdown_table(
            ["Path", "Reason"],
            [[item["path"], item["reason"]] for item in inventory["cleanup_candidates"]],
        ),
    ]

    parse_errors = inventory.get("parse_errors") or []
    if parse_errors:
        lines.extend(
            [
                "",
                "## Parse Errors",
                "",
                _markdown_table(
                    ["Path", "Error"],
                    [[item["path"], item["parse_error"]] for item in parse_errors],
                ),
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a project-wide Python maintainability audit inventory.")
    parser.add_argument("--root", default=".", help="Repository root to scan.")
    parser.add_argument("--report-md", default="", help="Optional Markdown report output path.")
    parser.add_argument("--report-json", default="", help="Optional JSON report output path.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    inventory = build_inventory(root)
    rendered = render_markdown(inventory)
    print(rendered)

    if args.report_md:
        report_md = Path(args.report_md)
        report_md.parent.mkdir(parents=True, exist_ok=True)
        report_md.write_text(rendered, encoding="utf-8")

    if args.report_json:
        report_json = Path(args.report_json)
        report_json.parent.mkdir(parents=True, exist_ok=True)
        report_json.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
