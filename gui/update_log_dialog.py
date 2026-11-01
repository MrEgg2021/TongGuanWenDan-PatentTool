from __future__ import annotations

import re
import sys
from math import ceil
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QPushButton, QScrollArea, QTextBrowser, QVBoxLayout, QWidget

from core.paths_utils import get_app_dir, get_resource_path

_VERSION_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)\.md$", re.IGNORECASE)


def _changelog_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(get_resource_path("更新日志"))
    return Path(get_app_dir()) / "用户使用手册+更新日志" / "更新日志"


def _load_changelogs() -> list[tuple[str, str]]:
    entries: list[tuple[tuple[int, int, int], str, str]] = []
    for path in _changelog_dir().glob("v*.md"):
        match = _VERSION_RE.match(path.name)
        if not match:
            continue
        version = tuple(int(part) for part in match.groups())
        entries.append((version, f"V{match.group(1)}.{match.group(2)}.{match.group(3)}", path.read_text(encoding="utf-8")))
    entries.sort(reverse=True)
    return [(label, text) for _, label, text in entries]


class UpdateLogDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("更新日志")
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("按版本展开查看更新内容，可同时展开多个版本。"))

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget(scroll)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

        entries = _load_changelogs()
        if not entries:
            body_layout.addWidget(QLabel("暂时没有可查看的更新日志。"))
        for index, (label, markdown) in enumerate(entries):
            body_layout.addWidget(self._build_section(label, markdown, expanded=index == 0))
        body_layout.addStretch(1)

    def _build_section(self, label: str, markdown: str, *, expanded: bool) -> QFrame:
        section = QFrame(self)
        section.setObjectName("Card")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(12, 10, 12, 10)
        section_layout.setSpacing(6)

        header = QPushButton(section)
        header.setCheckable(True)
        header.setChecked(expanded)
        viewer = QTextBrowser(section)
        viewer.setReadOnly(True)
        viewer.setOpenExternalLinks(True)
        viewer.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        viewer.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        viewer.setFrameShape(QFrame.NoFrame)
        viewer.setMarkdown(markdown)

        def sync_height() -> None:
            viewer.document().setTextWidth(max(100, viewer.viewport().width()))
            viewer.setFixedHeight(max(80, ceil(viewer.document().size().height()) + 12))

        def set_expanded(checked: bool) -> None:
            header.setText(f"{'▼' if checked else '▶'} {label}")
            viewer.setVisible(checked)
            if checked:
                QTimer.singleShot(0, sync_height)

        header.toggled.connect(set_expanded)
        viewer.document().documentLayout().documentSizeChanged.connect(lambda _size: sync_height())
        section_layout.addWidget(header)
        section_layout.addWidget(viewer)
        set_expanded(expanded)
        return section


def show_update_log_dialog(parent=None) -> None:
    UpdateLogDialog(parent).exec()
