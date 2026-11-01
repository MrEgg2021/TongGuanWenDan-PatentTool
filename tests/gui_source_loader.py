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


def read_navigation_mixin_source(repo_root: Path | None = None) -> str:
    root = _resolve_repo_root(repo_root)
    base = root / "gui/main_window/mixins"
    paths = [base / "navigation_mixin.py", base / "navigation_mixin_impl.py"]
    return _read_existing(paths)


def read_modern_shell_source(repo_root: Path | None = None) -> str:
    root = _resolve_repo_root(repo_root)
    base = root / "gui/ui_layout_impl"
    paths = [base / "modern_shell.py", base / "modern_shell_impl.py"]
    return _read_existing(paths)


def read_official_docs_dialogs_source(repo_root: Path | None = None) -> str:
    root = _resolve_repo_root(repo_root)
    base = root / "gui"
    paths = [base / "official_docs_dialogs.py", base / "official_docs_dialogs_impl.py"]
    return _read_existing(paths)

