from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


RANK_ORDER = {ch: idx for idx, ch in enumerate("ABCDEF", start=1)}


@dataclass
class FunctionMetric:
    path: str
    name: str
    lineno: int
    length: int
    depth: int
    rank: str
    complexity: int


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _calc_depth(node: ast.AST) -> int:
    max_depth = 0
    stack = [(child, 1) for child in getattr(node, "body", [])]
    while stack:
        current, depth = stack.pop()
        max_depth = max(max_depth, depth)
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith, ast.Match)):
                stack.append((child, depth + 1))
            else:
                stack.append((child, depth))
    return max_depth


def _scan_ast_functions(path: Path) -> dict[tuple[str, int], tuple[int, int]]:
    text = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(text)
    out: dict[tuple[str, int], tuple[int, int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = int(getattr(node, "end_lineno", node.lineno) - node.lineno + 1)
            depth = _calc_depth(node)
            out[(node.name, int(node.lineno))] = (length, depth)
    return out


def _radon_cc() -> dict[tuple[str, str, int], tuple[str, int]]:
    proc = subprocess.run(
        ["python", "-m", "radon", "cc", "core", "gui", "-j"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"radon failed: {proc.stderr}")
    data = json.loads(proc.stdout or "{}")
    out: dict[tuple[str, str, int], tuple[str, int]] = {}
    for path, items in data.items():
        if not isinstance(items, list):
            continue
        path_norm = str(path).replace("\\", "/")
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("type") not in ("function", "method"):
                continue
            name = str(item.get("name") or "")
            lineno = int(item.get("lineno") or 0)
            rank = str(item.get("rank") or "")
            complexity = int(item.get("complexity") or 0)
            out[(path_norm, name, lineno)] = (rank, complexity)
    return out


def _load_exceptions(path: Path) -> set[tuple[str, str, int]]:
    if not path.exists():
        return set()
    data = _load_json(path)
    entries = data.get("exceptions", []) if isinstance(data, dict) else []
    out: set[tuple[str, str, int]] = set()
    for item in entries:
        if not isinstance(item, dict):
            continue
        out.add(
            (
                str(item.get("path") or "").replace("\\", "/"),
                str(item.get("name") or ""),
                int(item.get("lineno") or 0),
            )
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Check complexity thresholds for target functions.")
    parser.add_argument(
        "--targets-json",
        default="openspec/changes/repo-l4-quality-governance-v1/baseline/top4-metrics.json",
        help="JSON list with fields: path, name, lineno",
    )
    parser.add_argument(
        "--exceptions-json",
        default="openspec/changes/repo-l4-quality-governance-v1/exceptions.json",
        help="Optional JSON exception list.",
    )
    parser.add_argument("--max-length", type=int, default=120)
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--max-rank", default="D")
    parser.add_argument("--report-json", default="")
    args = parser.parse_args()

    targets_path = Path(args.targets_json)
    targets = _load_json(targets_path)
    if not isinstance(targets, list):
        raise RuntimeError("targets-json must be a JSON list")

    exceptions = _load_exceptions(Path(args.exceptions_json))
    radon_map = _radon_cc()

    rows: list[FunctionMetric] = []
    for item in targets:
        if not isinstance(item, dict):
            continue
        fp = str(item.get("path") or "").replace("\\", "/")
        name = str(item.get("name") or "")
        lineno = int(item.get("lineno") or 0)
        if not fp or not name or lineno <= 0:
            continue
        ast_map = _scan_ast_functions(Path(fp))
        if (name, lineno) not in ast_map:
            raise RuntimeError(f"target not found in AST: {fp}:{lineno}::{name}")
        length, depth = ast_map[(name, lineno)]
        rank, complexity = radon_map.get((fp, name, lineno), ("", 0))
        rows.append(
            FunctionMetric(
                path=fp,
                name=name,
                lineno=lineno,
                length=length,
                depth=depth,
                rank=rank,
                complexity=complexity,
            )
        )

    max_rank_val = RANK_ORDER.get(str(args.max_rank).upper(), RANK_ORDER["D"])
    violations = []
    for row in rows:
        key = (row.path, row.name, row.lineno)
        if key in exceptions:
            continue
        row_rank = RANK_ORDER.get(row.rank.upper(), 999)
        if row.length > args.max_length or row.depth > args.max_depth or row_rank > max_rank_val:
            violations.append(
                {
                    "path": row.path,
                    "name": row.name,
                    "lineno": row.lineno,
                    "length": row.length,
                    "depth": row.depth,
                    "rank": row.rank,
                    "complexity": row.complexity,
                }
            )

    summary = {
        "targets": [
            {
                "path": r.path,
                "name": r.name,
                "lineno": r.lineno,
                "length": r.length,
                "depth": r.depth,
                "rank": r.rank,
                "complexity": r.complexity,
            }
            for r in rows
        ],
        "thresholds": {
            "max_length": args.max_length,
            "max_depth": args.max_depth,
            "max_rank": str(args.max_rank).upper(),
        },
        "exceptions_count": len(exceptions),
        "violations": violations,
    }

    print("== touched complexity summary ==")
    print(f"targets={len(rows)} exceptions={len(exceptions)} violations={len(violations)}")
    for item in violations:
        print(
            f"{item['path']}:{item['lineno']} {item['name']} "
            f"len={item['length']} depth={item['depth']} rank={item['rank']} c={item['complexity']}"
        )

    if args.report_json:
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
