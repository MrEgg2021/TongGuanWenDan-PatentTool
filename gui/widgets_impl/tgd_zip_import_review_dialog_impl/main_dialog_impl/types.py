from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QStyledItemDelegate


class ImportAction:
    IMPORT_CONTINUE = 1
    SKIP = 2
    IMPORT_STOP_AFTER = 3


class _AgencyCandidateDelegate(QStyledItemDelegate):
    def __init__(self, parent, *, dialog, col: str):
        super().__init__(parent)
        self._dialog = dialog
        self._col = str(col or "")

    def createEditor(self, parent, option, index):  # type: ignore[override]
        editor = super().createEditor(parent, option, index)
        try:
            if isinstance(editor, QLineEdit):
                self._dialog._attach_agency_editor_completer(editor, col=self._col)
        except Exception:
            pass
        return editor
