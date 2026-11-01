from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


def pick_value_from_list(parent, title: str, items: List[str], *, prompt: str = "请选择一个值：") -> Optional[int]:
    """弹出列表选择框，返回选中项索引；取消返回 None。"""

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
    layout.setSpacing(10)

    lbl = QLabel(str(prompt or ""), dlg)
    try:
        lbl.setWordWrap(True)
    except Exception:
        pass
    layout.addWidget(lbl)

    lst = QListWidget(dlg)
    for it in items:
        QListWidgetItem(str(it), lst)
    if items:
        try:
            lst.setCurrentRow(0)
        except Exception:
            pass
    layout.addWidget(lst, 1)

    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    btn_cancel = QPushButton("取消", dlg)
    btn_ok = QPushButton("确定", dlg)
    btn_ok.setDefault(True)
    btn_row.addWidget(btn_cancel)
    btn_row.addWidget(btn_ok)
    layout.addLayout(btn_row)

    btn_cancel.clicked.connect(dlg.reject)
    btn_ok.clicked.connect(dlg.accept)
    try:
        lst.itemDoubleClicked.connect(lambda _it: dlg.accept())
    except Exception:
        pass

    ok = dlg.exec() == QDialog.Accepted
    if not ok:
        return None
    idx = lst.currentRow()
    if idx is None:
        return None
    try:
        idx_i = int(idx)
    except Exception:
        return None
    if idx_i < 0 or idx_i >= len(items):
        return None
    return idx_i


def pick_multi_values_from_list(
    parent,
    title: str,
    items: List[str],
    *,
    prompt: str = "请选择关联申请人（可多选）：",
    ok_text: str = "确认并继续",
    skip_text: str = "跳过本条",
    cancel_text: str = "取消写回",
    selected_indexes: Optional[List[int]] = None,
) -> tuple[str, List[int]]:
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
    layout.setSpacing(10)

    lbl = QLabel(str(prompt or ""), dlg)
    try:
        lbl.setWordWrap(True)
    except Exception:
        pass
    layout.addWidget(lbl)

    lst = QListWidget(dlg)
    try:
        lst.setSelectionMode(QAbstractItemView.MultiSelection)
    except Exception:
        pass
    for it in items:
        QListWidgetItem(str(it), lst)
    for index in list(selected_indexes or []):
        if 0 <= int(index) < lst.count():
            item = lst.item(int(index))
            if item is not None:
                item.setSelected(True)
    layout.addWidget(lst, 1)

    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    btn_cancel = QPushButton(str(cancel_text or "取消写回"), dlg)
    btn_skip = QPushButton(str(skip_text or "跳过本条"), dlg)
    btn_ok = QPushButton(str(ok_text or "确认并继续"), dlg)
    btn_ok.setDefault(True)
    btn_row.addWidget(btn_cancel)
    btn_row.addWidget(btn_skip)
    btn_row.addWidget(btn_ok)
    layout.addLayout(btn_row)

    action = "cancel"

    def _sync_ok_enabled() -> None:
        try:
            btn_ok.setEnabled(bool(lst.selectedItems()))
        except Exception:
            try:
                btn_ok.setEnabled(False)
            except Exception:
                pass

    _sync_ok_enabled()

    try:
        lst.itemSelectionChanged.connect(_sync_ok_enabled)
    except Exception:
        pass

    def _on_cancel():
        nonlocal action
        action = "cancel"
        dlg.reject()

    def _on_skip():
        nonlocal action
        action = "skip"
        dlg.accept()

    def _on_ok():
        nonlocal action
        action = "ok"
        dlg.accept()

    btn_cancel.clicked.connect(_on_cancel)
    btn_skip.clicked.connect(_on_skip)
    btn_ok.clicked.connect(_on_ok)

    accepted = dlg.exec() == QDialog.Accepted
    if not accepted:
        return "cancel", []
    if action != "ok":
        return str(action or "cancel"), []

    idxs: List[int] = []
    try:
        for it in lst.selectedItems() or []:
            row = lst.row(it)
            try:
                idxs.append(int(row))
            except Exception:
                continue
    except Exception:
        idxs = []

    idxs = [i for i in idxs if 0 <= int(i) < len(items)]
    try:
        idxs = sorted(set(idxs))
    except Exception:
        pass
    return "ok", idxs


__all__ = ["pick_value_from_list", "pick_multi_values_from_list"]
