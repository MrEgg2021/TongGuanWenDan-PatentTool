from __future__ import annotations

import argparse
import ast
from pathlib import Path


LFS_POINTER_HEADER = b"version https://git-lfs.github.com/spec/v1"


def iter_pyinstaller_data_sources(spec_path: Path):
    tree = ast.parse(spec_path.read_text(encoding="utf-8"), filename=str(spec_path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "Analysis":
            continue
        for keyword in node.keywords:
            if keyword.arg != "datas" or not isinstance(keyword.value, (ast.List, ast.Tuple)):
                continue
            for item in keyword.value.elts:
                if not isinstance(item, (ast.List, ast.Tuple)) or not item.elts:
                    continue
                source = item.elts[0]
                if isinstance(source, ast.Constant) and isinstance(source.value, str):
                    yield source.value


def find_lfs_pointer_data_inputs(spec_paths: list[Path], *, repo_root: Path) -> list[Path]:
    pointers: list[Path] = []
    for spec_path in spec_paths:
        for source in iter_pyinstaller_data_sources(spec_path):
            candidate = Path(source)
            if not candidate.is_absolute():
                candidate = repo_root / candidate
            if not candidate.is_file():
                continue
            with candidate.open("rb") as stream:
                if stream.read(len(LFS_POINTER_HEADER)) == LFS_POINTER_HEADER:
                    pointers.append(candidate)
    return pointers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reject Git LFS pointer files referenced by PyInstaller datas.")
    parser.add_argument("specs", nargs="*", default=["CPCXMLGui.spec"])
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    spec_paths = [repo_root / value for value in args.specs]
    pointers = find_lfs_pointer_data_inputs(spec_paths, repo_root=repo_root)
    if pointers:
        for pointer in pointers:
            print(f"Git LFS pointer referenced by PyInstaller datas: {pointer}")
        return 1
    print("PyInstaller data integrity check passed: no Git LFS pointers referenced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
