from __future__ import annotations

from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtWidgets import QComboBox, QDialog, QLineEdit, QTableWidgetItem, QWidget

from gui.widgets_impl import tgd_zip_import_review_completer_ops as _zip_cpl_ops
from gui.widgets_impl import tgd_zip_import_review_fact_ops as _zip_fact_ops
from gui.widgets_impl import tgd_zip_import_review_import_ops as _zip_import_ops
from gui.widgets_impl.combo_wheel_blocker import ComboWheelBlocker

from . import lifecycle_ops, ui_build_ops
from .types import ImportAction, _AgencyCandidateDelegate


class TgdZipImportReviewDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        embedded: bool = False,
        initial_request_info: dict | None = None,
        source_path: str = "",
    ):
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
            self.setObjectName("tgdZipImportReviewEmbedded")
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
        self._action: int = ImportAction.SKIP
        self._exec_loop: QEventLoop | None = None
        self._size_target: QWidget | None = None
        self._pending_resize_sync = False

        self._dirty: bool = False
        self._loading_fact_editor: bool = False

        self._cpl_targets: dict[QLineEdit, tuple[str, str]] = {}
        self._cpl_timers: dict[QLineEdit, QTimer] = {}
        self._cpl_models: dict[QLineEdit, object] = {}
        self._cpl_cache: dict[tuple[str, str, str], list[str]] = {}
        self._agency_cell_cache: dict[tuple[str, str], list[str]] = {}

        self._source_file_path: str = str(source_path or "")
        self._request_form_cache_key: str = self._source_file_path
        self._initial_request_info: dict = initial_request_info if isinstance(initial_request_info, dict) else {}

        self._fact_rows: list[dict] = []
        self._current_fact_row_idx: int | None = None

        self._import_counts: tuple[int, int, int] = (0, 0, 0)
        self._import_errors: list[str] = []

        ui_build_ops.build_ui(self)

        self._combo_wheel_blocker = ComboWheelBlocker(self)
        try:
            self._combo_wheel_blocker.register_strict_scroll_area(getattr(self, "_scroll_area", None))
        except Exception:
            pass
        for w in self._fact_editor_widgets():
            try:
                if isinstance(w, QComboBox):
                    self._combo_wheel_blocker.register_combo(w)
            except Exception:
                pass

        try:
            self.fact_table.itemSelectionChanged.connect(self._on_fact_selection_changed)
        except Exception:
            pass

        try:
            self.btn_import_continue.clicked.connect(self._on_import_continue_clicked)
        except Exception:
            pass
        try:
            self.btn_skip.clicked.connect(self._on_skip_clicked)
        except Exception:
            pass
        try:
            self.btn_import_stop.clicked.connect(self._on_import_stop_clicked)
        except Exception:
            pass
        try:
            self.btn_close.clicked.connect(self.reject)
        except Exception:
            pass

        try:
            btn_back = getattr(self, "btn_back", None)
            if btn_back is not None:
                btn_back.clicked.connect(self.reject)
        except Exception:
            pass

        for w in self._fact_editor_widgets():
            try:
                if isinstance(w, QLineEdit):
                    w.textChanged.connect(self._on_fact_editor_changed)
                elif isinstance(w, QComboBox):
                    w.currentIndexChanged.connect(self._on_fact_editor_changed)
                    if w.isEditable() and w.lineEdit() is not None:
                        w.lineEdit().textChanged.connect(self._on_fact_editor_changed)
            except Exception:
                pass

        try:
            self.btn_add_agency_row.clicked.connect(self._on_add_agency_row)
        except Exception:
            pass
        try:
            self.btn_del_agency_row.clicked.connect(self._on_del_agency_row)
        except Exception:
            pass

        try:
            self._setup_candidate_completers()
        except Exception:
            pass

        try:
            self._setup_agency_table_candidate_delegate()
        except Exception:
            pass

        self._load_from_request_info()

    def _setup_candidate_completers(self) -> None:
        _zip_cpl_ops.setup_candidate_completers(self)

    def _get_group_for_candidates(self) -> str:
        return _zip_cpl_ops._get_group_for_candidates(self)

    def _setup_agency_table_candidate_delegate(self) -> None:
        _zip_cpl_ops.setup_agency_table_candidate_delegate(self, _AgencyCandidateDelegate)

    def _attach_agency_editor_completer(self, edit: QLineEdit, *, col: str) -> None:
        _zip_cpl_ops.attach_agency_editor_completer(self, edit, col=str(col or ""))

    def get_action(self) -> int:
        return int(self._action)

    def get_import_result(self) -> tuple[int, int, int, list[str]]:
        ins, upd, skp = self._import_counts
        return int(ins), int(upd), int(skp), list(self._import_errors or [])

    def exec(self) -> int:  # type: ignore[override]
        return int(lifecycle_ops.exec_dialog(self))

    def _finish_dialog(self, accepted: bool) -> None:
        lifecycle_ops.finish_dialog(self, accepted)

    def reject(self) -> None:  # type: ignore[override]
        lifecycle_ops.reject_dialog(self)

    def eventFilter(self, obj, event):  # type: ignore[override]
        lifecycle_ops.on_event_filter(self, obj, event)
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):  # type: ignore[override]
        if lifecycle_ops.on_key_press_event(event):
            return
        return super().keyPressEvent(event)

    def _apply_target_geometry(self, target: QWidget | None) -> None:
        lifecycle_ops.apply_target_geometry(self, target)

    def _sync_from_target(self) -> None:
        lifecycle_ops.sync_from_target(self)

    def _schedule_sync_from_target(self) -> None:
        lifecycle_ops.schedule_sync_from_target(self)

    def _build_ui(self) -> None:
        ui_build_ops.build_ui(self)

    def _build_fact_tab(self, tab: QWidget) -> None:
        ui_build_ops.build_fact_tab(self, tab)

    def _build_agency_tab(self, tab: QWidget) -> None:
        ui_build_ops.build_agency_tab(self, tab)

    def _load_from_request_info(self) -> None:
        _zip_fact_ops.load_from_request_info(self)

    def _refresh_fact_table(self) -> None:
        _zip_fact_ops.refresh_fact_table(self)

    def _fact_editor_widgets(self):
        return [
            self.fact_applicant_name,
            self.fact_applicant_type,
            self.fact_applicant_id_type,
            self.fact_applicant_id_no,
            self.fact_applicant_phone,
            self.fact_applicant_email,
            self.fact_applicant_addr_full,
            self.fact_inventor_name,
            self.fact_inventor_id_type,
            self.fact_inventor_id_no,
            self.fact_inventor_nat,
            self.fact_contact_name,
            self.fact_contact_phone,
            self.fact_contact_email,
            self.fact_contact_addr_full,
            self.fact_contact_zip,
            self.fact_group_name,
            self.fact_poa_no,
            self.fact_agency_name,
            self.fact_agency_code,
        ]

    def _on_fact_selection_changed(self) -> None:
        _zip_fact_ops.on_fact_selection_changed(self)

    def _on_fact_editor_changed(self, *args) -> None:
        _zip_fact_ops.on_fact_editor_changed(self, *args)

    def _do_import(self) -> bool:
        return _zip_import_ops.do_import(self)

    def _on_import_continue_clicked(self) -> None:
        if not self._do_import():
            return
        self._dirty = False
        self._action = ImportAction.IMPORT_CONTINUE
        self._finish_dialog(True)

    def _on_import_stop_clicked(self) -> None:
        if not self._do_import():
            return
        self._dirty = False
        self._action = ImportAction.IMPORT_STOP_AFTER
        self._finish_dialog(True)

    def _on_skip_clicked(self) -> None:
        if self._dirty:
            from gui.dialog_utils import ask_continue_cancel

            if not ask_continue_cancel(self, "提示", "跳过将放弃本弹窗的修改。\n\n是否仍然跳过？", continue_text="跳过", cancel_text="取消"):
                return
        self._action = ImportAction.SKIP
        self._finish_dialog(False)

    def _on_add_agency_row(self) -> None:
        try:
            r = int(self.agency_table.rowCount())
        except Exception:
            r = 0
        self.agency_table.setRowCount(r + 1)
        for c in range(5):
            self.agency_table.setItem(r, c, QTableWidgetItem(""))
        self._dirty = True

    def _on_del_agency_row(self) -> None:
        row = -1
        try:
            row = int(self.agency_table.currentRow())
        except Exception:
            row = -1
        if row < 0:
            return
        try:
            self.agency_table.removeRow(row)
        except Exception:
            return
        self._dirty = True


__all__ = ["TgdZipImportReviewDialog", "ImportAction"]
