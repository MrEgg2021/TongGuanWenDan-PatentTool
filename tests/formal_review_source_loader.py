from __future__ import annotations

from pathlib import Path


def _resolve_repo_root(repo_root: Path | None = None) -> Path:
    if repo_root is not None:
        return Path(repo_root)
    return Path(__file__).resolve().parents[1]


def _read_existing(paths: list[Path]) -> str:
    chunks: list[str] = []
    for fp in paths:
        if fp.exists() and fp.is_file():
            chunks.append(fp.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def read_formal_review_mixin_source(repo_root: Path | None = None) -> str:
    root = _resolve_repo_root(repo_root)
    base = root / "gui/main_window/mixins"
    paths: list[Path] = [base / "formal_review_mixin.py"]
    ops_dir = base / "formal_review_ops"
    if ops_dir.exists():
        paths.extend(sorted(ops_dir.rglob("*.py")))
    return _read_existing(paths)


def read_formal_review_page_source(repo_root: Path | None = None) -> str:
    root = _resolve_repo_root(repo_root)
    base = root / "gui/ui_layout_impl"
    paths: list[Path] = [base / "formal_review_page.py"]
    parts_dir = base / "formal_review_page_parts"
    if parts_dir.exists():
        paths.extend(sorted(parts_dir.rglob("*.py")))
    return _read_existing(paths)

