from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHeaderView,
    QSplitter,
    QSplitterHandle,
    QStyledItemDelegate,
)

from core.tgd_data_management_impl.candidates_query import (
    query_agency_agent_candidates,
    query_fact_record_candidates,
)
from core.tgd_data_management_impl.fact_record_query import query_fact_candidates_for_manager
from gui.widgets_impl.tgd_fact_record_manager_utils import _norm_text
from gui.widgets_impl.combo_wheel_blocker import ComboWheelBlocker


class AutoWrapHeaderView(QHeaderView):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setSectionResizeMode(QHeaderView.Interactive)
        self.setDefaultAlignment(Qt.AlignCenter | Qt.TextWordWrap)

    def sectionSizeFromContents(self, logicalIndex):
        s = super().sectionSizeFromContents(logicalIndex)
        s.setHeight(max(s.height(), 48))
        return s

    def initStyleOption(self, option):
        super().initStyleOption(option)
        option.textElideMode = Qt.ElideNone
        option.alignment = Qt.AlignCenter | Qt.TextWordWrap


class _PressableWidthSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        try:
            if orientation == Qt.Horizontal:
                self.setCursor(Qt.SplitHCursor)
            else:
                self.setCursor(Qt.SplitVCursor)
        except Exception:
            pass

    def mousePressEvent(self, event):  # type: ignore[override]
        try:
            sp = self.splitter()
            if sp is not None and hasattr(sp, "_set_pressed_handle"):
                sp._set_pressed_handle(True)
        except Exception:
            pass
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):  # type: ignore[override]
        try:
            sp = self.splitter()
            if sp is not None and hasattr(sp, "_set_pressed_handle"):
                sp._set_pressed_handle(False)
        except Exception:
            pass
        super().mouseReleaseEvent(event)


class _PressableWidthSplitter(QSplitter):
    def __init__(self, orientation, parent=None, *, normal_width: int = 3, pressed_width: int = 4):
        super().__init__(orientation, parent)
        self._normal_handle_width = int(normal_width)
        self._pressed_handle_width = int(pressed_width)
        try:
            self.setHandleWidth(self._normal_handle_width)
        except Exception:
            pass

    def _set_pressed_handle(self, pressed: bool) -> None:
        try:
            w = self._pressed_handle_width if pressed else self._normal_handle_width
            if int(self.handleWidth()) != int(w):
                self.setHandleWidth(int(w))
        except Exception:
            pass

    def createHandle(self):  # type: ignore[override]
        return _PressableWidthSplitterHandle(self.orientation(), self)


class FilterComboBox(QComboBox):
    filterChanged = Signal(str)

    def __init__(self, parent=None, placeholder="筛选...", scope="fact", col=""):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.lineEdit().setPlaceholderText(placeholder)
        self.scope = scope
        self.col = col

        self._combo_wheel_blocker = ComboWheelBlocker(self)
        self._combo_wheel_blocker.register_combo(self)

        # Style
        self.setStyleSheet("""
            QComboBox {
                border: none;
                background: transparent;
                border-bottom: 1px solid #CBD5E1;
                font-size: 13px;
                padding-left: 6px;
            }
            QComboBox:focus {
                border-bottom: 2px solid #3b82f6;
            }
            QLineEdit {
                background: transparent;
                padding-left: 0px;
                margin-left: 0px;
            }
        """)

        # Timer for debouncing input
        self._typing_timer = QTimer(self)
        self._typing_timer.setSingleShot(True)
        self._typing_timer.setInterval(300)
        self._typing_timer.timeout.connect(self._on_typing_timeout)

        self.lineEdit().textEdited.connect(self._schedule_query)
        self.lineEdit().returnPressed.connect(self._on_return_pressed)
        # self.currentIndexChanged.connect(self._on_index_changed) # Careful with loop
        self.activated.connect(self._on_activated)

    def _schedule_query(self, text: str):
        self._typing_timer.start()

    def _on_typing_timeout(self):
        self.showPopup()

    def showPopup(self):
        self._refresh_candidates()
        super().showPopup()

    def _find_manager(self):
        p = self.parent()
        while p is not None:
            if hasattr(p, "_get_fact_group_name_filter_text"):
                return p
            try:
                p = p.parent()
            except Exception:
                break
        return None

    def _refresh_candidates(self):
        typed = self.currentText().strip()
        # We need to call the query function
        # For simplicity, we can reuse the existing query logic references if possible, 
        # or call the imported functions directly.

        limit = 50
        values = []
        try:
            if self.scope == "agency":
                res = query_agency_agent_candidates(col=self.col, typed=typed, limit=limit)
                values = list(res.values or [])
            else:
                if self.col == "group_name":
                    # group_name usually stands alone or is the top filter, but user requested full linkage.
                    # Let's treat it as a linked filter too if possible.
                    # But if we want to keep it simple or if query_group_name_candidates is specialized, check first.
                    # Actually query_fact_candidates_for_manager supports group_name as target_col.
                    # So we can use the unified logic.
                    pass

                # Unified logic for 'fact' scope
                mgr = self._find_manager()
                if mgr is not None and hasattr(mgr, "_get_filters"):
                    filters = mgr._get_filters()
                    # Remove self from filters
                    if self.col in filters:
                        filters[self.col] = ""

                    res = query_fact_candidates_for_manager(
                        target_col=self.col,
                        typed=typed,
                        limit=limit,
                        **filters
                    )
                    values = list(res.values or [])
                else:
                    # Fallback
                    group_name = ""
                    if mgr is not None:
                        try:
                            group_name = _norm_text(mgr._get_fact_group_name_filter_text())
                        except Exception:
                            group_name = ""

                    res = query_fact_record_candidates(group_name=group_name, col=self.col, typed=typed, limit=limit)
                    values = list(res.values or [])
        except Exception:
            pass

        # Block signals to prevent triggering filter changed while populating
        self.blockSignals(True)
        curr_text = self.currentText()
        self.clear()
        if curr_text and curr_text not in values:
            pass # Keep typed text? QComboBox logic is complex.
            # If we clear, the text might be lost if not carefully handled.
            # However, since it is editable, text should persist in lineEdit.

        self.addItems(values)
        self.lineEdit().setText(curr_text)
        self.blockSignals(False)

    def _on_return_pressed(self):
        self.filterChanged.emit(self.currentText())

    def _on_activated(self, index):
        self.filterChanged.emit(self.itemText(index))


class SmartTableDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, options=None):
        super().__init__(parent)
        self.options = options or []

    def createEditor(self, parent, option, index):
        if not self.options:
            return super().createEditor(parent, option, index)
        editor = QComboBox(parent)
        editor.setEditable(True)
        editor.addItems(self.options)

        wheel_blocker = ComboWheelBlocker(editor)
        try:
            editor._combo_wheel_blocker = wheel_blocker
        except Exception:
            pass
        wheel_blocker.register_combo(editor)
        return editor

    def setEditorData(self, editor, index):
        if not self.options:
            super().setEditorData(editor, index)
            return
        value = index.model().data(index, Qt.EditRole)
        editor.setCurrentText(str(value))

    def setModelData(self, editor, model, index):
        if not self.options:
            super().setModelData(editor, model, index)
            return
        model.setData(index, editor.currentText(), Qt.EditRole)
