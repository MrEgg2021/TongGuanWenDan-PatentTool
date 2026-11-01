from __future__ import annotations

from pathlib import Path


def _read_existing(paths: list[Path]) -> str:
    chunks: list[str] = []
    for fp in paths:
        if fp.exists() and fp.is_file():
            chunks.append(fp.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def read_official_docs_mixin_source(repo_root: Path) -> str:
    base = repo_root / "gui/main_window/mixins"
    paths: list[Path] = [base / "official_docs_mixin.py"]
    ops_dir = base / "official_docs_ops"
    if ops_dir.exists():
        paths.extend(sorted(ops_dir.glob("*.py")))
    return _read_existing(paths)


def read_official_docs_page_source(repo_root: Path) -> str:
    base = repo_root / "gui/ui_layout_impl"
    paths: list[Path] = [base / "official_docs_page.py"]
    for sub_name in ("official_docs_page", "official_docs_page_parts"):
        sub_dir = base / sub_name
        if sub_dir.exists():
            paths.extend(sorted(sub_dir.glob("*.py")))
    return _read_existing(paths)
