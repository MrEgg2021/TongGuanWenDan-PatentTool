from __future__ import annotations

from PySide6.QtCore import Qt, QEventLoop, QTimer, Signal
from PySide6.QtWidgets import QDialog, QTableWidget, QWidget

from gui.widgets_impl.combo_wheel_blocker import ComboWheelBlocker
from .checked_state_ops import _CheckedStateOpsMixin
from .export_delete_save_ops import _ExportDeleteSaveOpsMixin
from .layout_ops import _LayoutOpsMixin
from .refresh_ops import _RefreshOpsMixin
from .row_menu_ops import _RowMenuOpsMixin
from .ui_build_ops import _UIBuildOpsMixin


class TgdFactRecordManagerDialog(
    QDialog,
    _UIBuildOpsMixin,
    _LayoutOpsMixin,
    _RowMenuOpsMixin,
    _CheckedStateOpsMixin,
    _RefreshOpsMixin,
    _ExportDeleteSaveOpsMixin,
):
    backRequested = Signal()

    def __init__(self, parent=None, *, embedded: bool = False):
        super().__init__(parent)

        self._embedded = bool(embedded)
        if not self._embedded:
            self.setObjectName("ModalOverlay")
            self.setAttribute(Qt.WA_StyledBackground, True)
            try:
                self.setWindowFlag(Qt.FramelessWindowHint, True)
            except Exception:
                pass
            try:
                self.setAttribute(Qt.WA_TranslucentBackground, True)
            except Exception:
                pass
        else:
            self.setObjectName("tgdFactRecordManagerEmbedded")
            try:
                self.setWindowFlags(Qt.Widget)
            except Exception:
                try:
                    self.setWindowFlag(Qt.Dialog, False)
                    self.setWindowFlag(Qt.Window, False)
                except Exception:
                    pass
            try:
                self.setAttribute(Qt.WA_StyledBackground, True)
            except Exception:
                pass

        self._dialog_result: int = QDialog.Rejected
        self._exec_loop: QEventLoop | None = None
        self._size_target: QWidget | None = None
        self._pending_resize_sync = False

        self._dirty: bool = False
        self._deleted_fact_ids: list[int] = []
        self._deleted_agency_ids: list[int] = []

        self._checked_fact_ids: set[int] = set()
        self._checked_agency_ids: set[int] = set()

        self._layout_save_enabled: bool = False
        self._layout_initialized: bool = False
        self._layout_ever_visible: bool = False
        self._layout_init_pending: bool = False

        # Pointers to widgets
        self.fact_table_left: QTableWidget | None = None
        self.fact_table_right: QTableWidget | None = None
        self.agency_table: QTableWidget | None = None

        self._fact_filter_widgets = {}  # col -> widget
        self._agency_filter_widgets = {}

        self._build_ui()

        self._strict_scroll_wheel_blocker = ComboWheelBlocker(self)
        try:
            self._strict_scroll_wheel_blocker.register_strict_scroll_area(getattr(self, "fact_table_left", None))
            self._strict_scroll_wheel_blocker.register_strict_scroll_area(getattr(self, "fact_table_right", None))
            self._strict_scroll_wheel_blocker.register_strict_scroll_area(getattr(self, "agency_table", None))
        except Exception:
            pass

        if not self._embedded:
            try:
                self._load_layout_state()
            except Exception:
                pass
            try:
                self._layout_initialized = True
            except Exception:
                pass

            try:
                QTimer.singleShot(0, self._enable_layout_save)
            except Exception:
                try:
                    self._enable_layout_save()
                except Exception:
                    pass

        # Initial load
        if not self._embedded:
            try:
                QTimer.singleShot(10, self._refresh_current_tab)
            except Exception:
                pass

    def closeEvent(self, event) -> None:
        try:
            if not bool(getattr(self, "_embedded", False)):
                self._save_layout_state()
            else:
                if bool(getattr(self, "_layout_ever_visible", False)) and bool(
                    getattr(self, "_layout_save_enabled", False)
                ):
                    try:
                        if not bool(self.isVisible()):
                            raise RuntimeError("not visible")
                    except Exception:
                        raise
                    self._save_layout_state(force=True)
        except Exception:
            pass
        try:
            super().closeEvent(event)
        except Exception:
            pass

    def showEvent(self, event) -> None:
        try:
            super().showEvent(event)
        except Exception:
            pass

        try:
            self._layout_ever_visible = True
        except Exception:
            pass

        if bool(getattr(self, "_embedded", False)) and (not bool(getattr(self, "_layout_initialized", False))) and (
            not bool(getattr(self, "_layout_init_pending", False))
        ):
            try:
                self._layout_init_pending = True
            except Exception:
                pass

            def _init_layout_try(attempt: int = 0) -> None:
                structural_mismatch = False
                restore_failed = False
                try:
                    structural_mismatch, restore_failed = self._load_layout_state()
                except Exception:
                    structural_mismatch, restore_failed = False, True

                if bool(restore_failed) and (not bool(structural_mismatch)) and int(attempt) < 1:
                    try:
                        QTimer.singleShot(60, lambda: _init_layout_try(attempt + 1))
                        return
                    except Exception:
                        pass

                try:
                    self._layout_initialized = True
                except Exception:
                    pass
                try:
                    self._layout_init_pending = False
                except Exception:
                    pass

                try:
                    QTimer.singleShot(0, self._enable_layout_save)
                except Exception:
                    try:
                        self._enable_layout_save()
                    except Exception:
                        pass

            try:
                QTimer.singleShot(0, _init_layout_try)
            except Exception:
                _init_layout_try()


__all__ = ["TgdFactRecordManagerDialog"]
