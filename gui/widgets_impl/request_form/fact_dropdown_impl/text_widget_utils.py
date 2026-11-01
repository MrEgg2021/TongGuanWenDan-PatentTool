from __future__ import annotations

from typing import Any, List

from PySide6.QtWidgets import QComboBox


def _norm_text(value) -> str:
    if value is None:
        return ""
    try:
        s = str(value)
    except Exception:
        return ""
    return s.strip()


def _is_empty_text_widget(widget) -> bool:
    if widget is None:
        return True
    try:
        if isinstance(widget, QComboBox):
            txt = widget.currentText()
        else:
            txt = widget.text()
    except Exception:
        txt = ""
    return (str(txt or "").strip() == "")


def _set_line_edit_if_empty(edit, value: str) -> bool:
    if edit is None:
        return False

    if not _norm_text(value):
        return False
    if not _is_empty_text_widget(edit):
        return False
    try:
        if isinstance(edit, QComboBox):
            edit.setEditText(str(value))
        else:
            edit.setText(str(value))
        return True
    except Exception:
        return False


def _set_combo_by_data_or_text(combo: QComboBox, value: str, *, data_first: bool = True) -> bool:
    if combo is None:
        return False
    v = _norm_text(value)
    if not v:
        return False
    try:
        cur_txt = combo.currentText()
    except Exception:
        cur_txt = ""
    if _norm_text(cur_txt):
        return False

    try:
        if data_first:
            idx = combo.findData(v)
            if idx >= 0:
                combo.setCurrentIndex(idx)
                return True
    except Exception:
        pass
    try:
        idx2 = combo.findText(v)
        if idx2 >= 0:
            combo.setCurrentIndex(idx2)
            return True
    except Exception:
        pass
    try:
        combo.setEditText(v)
        return True
    except Exception:
        return False


def _set_region_combo_value(self, combo: QComboBox | None, value: str, *, kind: str = "") -> None:
    if combo is None:
        return
    try:
        combo.setEditable(True)
    except Exception:
        pass
    try:
        combo.setEditText(_norm_text(value))
    except Exception:
        pass


def _unique_values(candidates: list, col: str) -> List[Any]:
    seen = set()
    out = []
    for row in candidates or []:
        if not isinstance(row, dict):
            continue
        v = row.get(col)
        if v is None:
            continue
        s = _norm_text(v)
        if not s:
            continue
        key = s
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def _stable_sig_for_dict(d: dict) -> tuple:
    items = []
    for k in sorted((d or {}).keys()):
        try:
            items.append((str(k), _norm_text(d.get(k))))
        except Exception:
            items.append((str(k), ""))
    return tuple(items)
