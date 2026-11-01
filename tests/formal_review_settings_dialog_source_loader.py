from __future__ import annotations

from pathlib import Path


def load_formal_review_settings_dialog_source() -> str:
    paths = [
        Path("gui/widgets_impl/formal_review/settings_dialog.py"),
        Path("gui/widgets_impl/formal_review/settings_dialog_parts/wordlist_tab.py"),
        Path("gui/widgets_impl/formal_review/settings_dialog_parts/highlight_tab.py"),
    ]
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)
