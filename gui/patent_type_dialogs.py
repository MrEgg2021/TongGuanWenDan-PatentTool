from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.patent_type_resolution import get_patent_type_display_label
from gui.widgets import GraphicCheckBox


_OPTIONS = [
    ("invention", "发明"),
    ("utility_model", "实用新型"),
]


def _build_dialog_shell(parent, *, title: str, prompt: str) -> tuple[QDialog, QVBoxLayout]:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    try:
        dlg.setWindowModality(Qt.WindowModal)
    except Exception:
        pass
    try:
        dlg.setModal(True)
    except Exception:
        pass

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(12)

    lbl = QLabel(str(prompt or ""), dlg)
    try:
        lbl.setWordWrap(True)
    except Exception:
        pass
    layout.addWidget(lbl)
    return dlg, layout


def prompt_single_patent_type_choice(parent, *, file_path: str) -> str | None:
    file_name = os.path.basename(str(file_path or "")) or str(file_path or "")
    dlg, layout = _build_dialog_shell(
        parent,
        title="选择最终专利类型",
        prompt=f"当前未启用请求书，且说明书中未直接识别到“发明内容”或“实用新型内容”。\n\n请为文件“{file_name}”选择最终专利类型：",
    )

    option_box = QWidget(dlg)
    option_layout = QVBoxLayout(option_box)
    option_layout.setContentsMargins(0, 0, 0, 0)
    option_layout.setSpacing(8)

    group = QButtonGroup(dlg)
    radios: dict[str, GraphicCheckBox] = {}
    for value, label in _OPTIONS:
        radio = GraphicCheckBox(label, option_box)
        group.addButton(radio)
        radios[value] = radio
        option_layout.addWidget(radio)
    layout.addWidget(option_box)

    button_row = QHBoxLayout()
    button_row.addStretch(1)
    btn_cancel = QPushButton("取消", dlg)
    btn_ok = QPushButton("确定", dlg)
    btn_ok.setDefault(True)
    btn_ok.setEnabled(False)
    button_row.addWidget(btn_cancel)
    button_row.addWidget(btn_ok)
    layout.addLayout(button_row)

    def _selected_value() -> str | None:
        for value, radio in radios.items():
            try:
                if radio.isChecked():
                    return value
            except Exception:
                continue
        return None

    def _sync_ok() -> None:
        try:
            btn_ok.setEnabled(bool(_selected_value()))
        except Exception:
            pass

    for radio in radios.values():
        try:
            radio.toggled.connect(_sync_ok)
        except Exception:
            pass
    btn_cancel.clicked.connect(dlg.reject)
    btn_ok.clicked.connect(dlg.accept)

    if dlg.exec() != QDialog.Accepted:
        return None
    return _selected_value()


def prompt_batch_patent_type_choices(
    parent,
    *,
    file_paths: list[str],
    existing_choices: dict[str, str] | None = None,
) -> dict[str, str] | None:
    file_paths = [str(p) for p in (file_paths or []) if str(p or "").strip()]
    if not file_paths:
        return {}

    existing_choices = dict(existing_choices or {})
    dlg, layout = _build_dialog_shell(
        parent,
        title="批量确认最终专利类型",
        prompt="当前未启用请求书，且以下文件的说明书中未直接识别到“发明内容”或“实用新型内容”。\n\n请逐文件选择最终专利类型：",
    )

    table = QTableWidget(len(file_paths), 2, dlg)
    table.setHorizontalHeaderLabels(["文件名", "最终专利类型"])
    try:
        table.verticalHeader().setVisible(False)
    except Exception:
        pass
    try:
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    except Exception:
        pass
    try:
        table.horizontalHeader().setStretchLastSection(True)
    except Exception:
        pass
    try:
        table.setSelectionMode(QAbstractItemView.NoSelection)
    except Exception:
        pass

    combos: dict[str, QComboBox] = {}
    for row, file_path in enumerate(file_paths):
        file_name = os.path.basename(file_path) or file_path
        name_item = QTableWidgetItem(file_name)
        try:
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        except Exception:
            pass
        table.setItem(row, 0, name_item)

        combo = QComboBox(table)
        combo.addItem("请选择...", "")
        for value, label in _OPTIONS:
            combo.addItem(label, value)
        selected = str(existing_choices.get(file_path) or "")
        if selected in {"invention", "utility_model"}:
            idx = combo.findData(selected)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        table.setCellWidget(row, 1, combo)
        combos[file_path] = combo
    layout.addWidget(table, 1)

    button_row = QHBoxLayout()
    button_row.addStretch(1)
    btn_cancel = QPushButton("取消", dlg)
    btn_ok = QPushButton("确定", dlg)
    btn_ok.setDefault(True)
    button_row.addWidget(btn_cancel)
    button_row.addWidget(btn_ok)
    layout.addLayout(button_row)

    def _collect() -> dict[str, str]:
        resolved: dict[str, str] = {}
        for file_path, combo in combos.items():
            try:
                value = str(combo.currentData() or "")
            except Exception:
                value = ""
            if value in {"invention", "utility_model"}:
                resolved[file_path] = value
        return resolved

    def _sync_ok() -> None:
        try:
            btn_ok.setEnabled(len(_collect()) == len(file_paths))
        except Exception:
            btn_ok.setEnabled(False)

    for combo in combos.values():
        try:
            combo.currentIndexChanged.connect(_sync_ok)
        except Exception:
            pass
    _sync_ok()

    btn_cancel.clicked.connect(dlg.reject)
    btn_ok.clicked.connect(dlg.accept)

    if dlg.exec() != QDialog.Accepted:
        return None
    return _collect()


def format_processing_patent_type_text(patent_type: str | None) -> str:
    label = get_patent_type_display_label(patent_type)
    return f"最终专利类型：{label or '待确定'}"


__all__ = [
    "format_processing_patent_type_text",
    "prompt_batch_patent_type_choices",
    "prompt_single_patent_type_choice",
]
