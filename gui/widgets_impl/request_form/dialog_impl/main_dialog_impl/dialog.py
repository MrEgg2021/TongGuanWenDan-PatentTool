from __future__ import annotations


from PySide6.QtCore import Qt, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from ...dialog_ui import build_request_form_dialog_ui
from gui.windowing import overlay_controller as overlay_controller_api

from gui.dialog_utils import ask_continue_cancel

from ...validation import accept as _accept
from ...data_io import set_initial_data as _set_initial_data, get_request_data as _get_request_data
from ...regions import (
    get_region_code_from_combo as _get_region_code_from_combo,
    populate_province_combo as _populate_province_combo,
    populate_city_combo as _populate_city_combo,
    init_contact_region_widgets as _init_contact_region_widgets,
    on_contact_province_changed as _on_contact_province_changed,
    init_applicant_region_widgets as _init_applicant_region_widgets,
    on_applicant_province_changed as _on_applicant_province_changed,
)
from ...tabs import (
    create_applicant_tab as _create_applicant_tab,
    add_applicant_tab as _add_applicant_tab,
    remove_current_applicant_tab as _remove_current_applicant_tab,
    renumber_applicant_tabs as _renumber_applicant_tabs,
    create_inventor_tab as _create_inventor_tab,
    add_inventor_tab as _add_inventor_tab,
    remove_current_inventor_tab as _remove_current_inventor_tab,
    renumber_inventor_tabs as _renumber_inventor_tabs,
)

from ...fact_dropdown import (
    _on_inline_fact_combo_text_edited,
    _refresh_inline_fact_dropdown,
    _set_region_combo_value,
    _setup_inline_fact_dropdowns_for_applicant_tab,
    _setup_inline_fact_dropdowns_for_agency,
    _setup_inline_fact_dropdowns_for_contact,
    _setup_inline_fact_dropdowns_for_inventor_tab,
)
from ...fact_autofill import (
    _on_inline_fact_combo_activated,
    _on_applicant_anchor_editing_finished,
)

from ...fact_import import (
    _set_cache_context,
    _on_btn_save_clicked,
    _on_btn_import_to_data_mgmt_clicked,
)

from .geometry_ops import _apply_target_geometry, _schedule_sync_from_target, _sync_from_target
from .event_filter_ops import _register_combo_wheel_block, event_filter as _event_filter
from gui.widgets_impl.combo_wheel_blocker import ComboWheelBlocker


class RequestFormDialog(QDialog):
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
            self.setObjectName("requestFormEmbedded")
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
        self._wheel_block_targets = set()
        self._dialog_result: int = QDialog.Rejected
        self._exec_loop: QEventLoop | None = None
        self._size_target: QWidget | None = None
        self._pending_resize_sync = False
        self._overlay_owner: QWidget | None = None
        self._overlay_name: str = ""
        self._overlay_modal_active = False

        self._dirty: bool = False

        build_request_form_dialog_ui(self)

        self._strict_scroll_wheel_blocker = ComboWheelBlocker(self)
        try:
            self._strict_scroll_wheel_blocker.register_strict_scroll_area(getattr(self, "_scroll_area", None))
        except Exception:
            pass

        self._fact_candidates = []
        self._fact_candidates_truncated = False
        self._fact_selected_exact_by_ctx = {}
        self._fact_candidates_cache_rows = []
        self._fact_candidates_cache_truncated = False
        self._fact_candidates_cache_dirty = True
        self._fact_candidates_cache_sig = None
        self._fact_combo_managed_targets = set()
        self._fact_combo_field_map = {}
        self._fact_combo_line_edit_map = {}
        self._combo_popup_owner_map = {}

        self._fact_dropdown_weak_filter_mode = True

        try:
            setup_fn = getattr(self, "_setup_inline_fact_dropdowns_for_contact", None)
            if callable(setup_fn):
                setup_fn()
        except Exception:
            pass

        try:
            setup_fn = getattr(self, "_setup_inline_fact_dropdowns_for_agency", None)
            if callable(setup_fn):
                setup_fn()
        except Exception:
            pass

        self._request_form_cache = None
        self._request_form_cache_key = ""
        self._source_file_path = ""

        try:
            self.btn_save.clicked.connect(lambda: self._on_btn_save_clicked())
        except Exception:
            pass
        try:
            self.btn_import_to_data_mgmt.clicked.connect(lambda: self._on_btn_import_to_data_mgmt_clicked())
        except Exception:
            pass
        try:
            btn_back = getattr(self, "btn_back", None)
            if btn_back is not None:
                btn_back.clicked.connect(self.reject)
        except Exception:
            pass

        try:
            self._setup_dirty_tracking()
        except Exception:
            pass

    def _mark_dirty(self, *args) -> None:
        _ = args
        try:
            self._dirty = True
        except Exception:
            pass

    def _setup_dirty_tracking(self) -> None:
        try:
            from PySide6.QtWidgets import QAbstractButton, QComboBox, QLineEdit
        except Exception:
            return

        for edit in self.findChildren(QLineEdit) or []:
            try:
                edit.textEdited.connect(self._mark_dirty)
            except Exception:
                pass

        for combo in self.findChildren(QComboBox) or []:
            try:
                combo.activated.connect(self._mark_dirty)
            except Exception:
                pass
            try:
                le = combo.lineEdit() if combo.isEditable() else None
            except Exception:
                le = None
            if le is not None:
                try:
                    le.textEdited.connect(self._mark_dirty)
                except Exception:
                    pass

        for btn in self.findChildren(QAbstractButton) or []:
            try:
                btn.clicked.connect(self._mark_dirty)
            except Exception:
                pass

    def exec(self) -> int:  # type: ignore[override]
        if bool(getattr(self, "_embedded", False)):
            self._dialog_result = QDialog.Rejected
            try:
                self.show()
            except Exception:
                pass
            loop = QEventLoop(self)
            self._exec_loop = loop
            loop.exec()
            return int(self._dialog_result)

        owner = self.parentWidget()
        if owner is None:
            try:
                owner = QApplication.activeWindow()
            except Exception:
                owner = None

        if owner is not None and self.parentWidget() is None:
            try:
                self.setParent(owner)
            except Exception:
                pass

        target = owner
        try:
            shell = getattr(owner, "_modern_shell", None) if owner is not None else None
            main_area = getattr(shell, "main_area", None) if shell else None
            if main_area is not None:
                target = main_area
        except Exception:
            target = owner

        try:
            prev_target = getattr(self, "_size_target", None)
            if prev_target is not None:
                prev_target.removeEventFilter(self)
        except Exception:
            pass
        try:
            self._size_target = target
        except Exception:
            self._size_target = None
        try:
            if self._size_target is not None:
                self._size_target.installEventFilter(self)
        except Exception:
            pass

        try:
            self._overlay_owner = target if target is not None else owner
        except Exception:
            self._overlay_owner = owner
        try:
            self._overlay_name = f"request_form_overlay_{id(self)}"
        except Exception:
            self._overlay_name = ""
        self._overlay_modal_active = False

        try:
            if self._overlay_owner is not None and self.parentWidget() is not self._overlay_owner:
                self.setParent(self._overlay_owner)
        except Exception:
            pass

        try:
            if self._overlay_owner is not None and self._overlay_name:
                overlay_controller_api.attach(self._overlay_name, self, self._overlay_owner)
                overlay_controller_api.set_modal_active(True)
                self._overlay_modal_active = True
        except Exception:
            self._overlay_modal_active = False

        self._apply_target_geometry(self._overlay_owner if self._overlay_owner is not None else target)

        self._dialog_result = QDialog.Rejected
        self.show()
        self.raise_()

        loop = QEventLoop(self)
        self._exec_loop = loop
        loop.exec()
        return int(self._dialog_result)

    def _finish_dialog(self, accepted: bool) -> None:
        self._dialog_result = QDialog.Accepted if accepted else QDialog.Rejected
        if bool(getattr(self, "_embedded", False)):
            try:
                self.hide()
            except Exception:
                pass
            try:
                if self._exec_loop is not None:
                    self._exec_loop.quit()
            except Exception:
                pass
            return

        try:
            if bool(getattr(self, "_overlay_modal_active", False)):
                overlay_controller_api.set_modal_active(False)
                self._overlay_modal_active = False
        except Exception:
            pass
        try:
            name = str(getattr(self, "_overlay_name", "") or "").strip()
            if name:
                overlay_controller_api.detach(name)
        except Exception:
            pass
        try:
            self._overlay_name = ""
            self._overlay_owner = None
        except Exception:
            pass

        try:
            if self._size_target is not None:
                self._size_target.removeEventFilter(self)
        except Exception:
            pass
        try:
            self._size_target = None
        except Exception:
            pass
        try:
            self.hide()
        except Exception:
            pass
        try:
            if self._exec_loop is not None:
                self._exec_loop.quit()
        except Exception:
            pass

        try:
            QTimer.singleShot(0, lambda: self.setParent(None))
            QTimer.singleShot(0, self.deleteLater)
        except Exception:
            pass

    def reject(self) -> None:  # type: ignore[override]
        if bool(getattr(self, "_dirty", False)):
            if not ask_continue_cancel(
                self,
                "提示",
                "返回将放弃未保存的修改。\n\n是否仍然返回？",
                continue_text="放弃修改",
                cancel_text="取消",
            ):
                return
        self._finish_dialog(False)

    def accept(self) -> None:  # type: ignore[override]
        self._finish_dialog(True)

    def keyPressEvent(self, event):  # type: ignore[override]
        try:
            if event.key() == Qt.Key_Escape:
                event.ignore()
                return
        except Exception:
            pass
        return super().keyPressEvent(event)

    def set_target_file_name(self, file_name: str) -> None:
        name = str(file_name or "").strip()
        if not name:
            self._file_label.setVisible(False)
            self._file_label.setText("")
            return
        self._file_label.setText(f"当前文件：{name}")
        self._file_label.setVisible(True)

    def eventFilter(self, obj, event):  # type: ignore[override]
        return _event_filter(self, obj, event)


RequestFormDialog.accept = _accept
RequestFormDialog.set_initial_data = _set_initial_data
RequestFormDialog.get_request_data = _get_request_data
RequestFormDialog._get_region_code_from_combo = _get_region_code_from_combo
RequestFormDialog._populate_province_combo = _populate_province_combo
RequestFormDialog._populate_city_combo = _populate_city_combo
RequestFormDialog._init_contact_region_widgets = _init_contact_region_widgets
RequestFormDialog._on_contact_province_changed = _on_contact_province_changed
RequestFormDialog._init_applicant_region_widgets = _init_applicant_region_widgets
RequestFormDialog._on_applicant_province_changed = _on_applicant_province_changed
RequestFormDialog._create_applicant_tab = _create_applicant_tab
RequestFormDialog._add_applicant_tab = _add_applicant_tab
RequestFormDialog._remove_current_applicant_tab = _remove_current_applicant_tab
RequestFormDialog._renumber_applicant_tabs = _renumber_applicant_tabs
RequestFormDialog._create_inventor_tab = _create_inventor_tab
RequestFormDialog._add_inventor_tab = _add_inventor_tab
RequestFormDialog._remove_current_inventor_tab = _remove_current_inventor_tab
RequestFormDialog._renumber_inventor_tabs = _renumber_inventor_tabs

RequestFormDialog._set_region_combo_value = _set_region_combo_value
RequestFormDialog._setup_inline_fact_dropdowns_for_applicant_tab = _setup_inline_fact_dropdowns_for_applicant_tab
RequestFormDialog._setup_inline_fact_dropdowns_for_inventor_tab = _setup_inline_fact_dropdowns_for_inventor_tab
RequestFormDialog._setup_inline_fact_dropdowns_for_contact = _setup_inline_fact_dropdowns_for_contact
RequestFormDialog._setup_inline_fact_dropdowns_for_agency = _setup_inline_fact_dropdowns_for_agency
RequestFormDialog._refresh_inline_fact_dropdown = _refresh_inline_fact_dropdown
RequestFormDialog._on_inline_fact_combo_text_edited = _on_inline_fact_combo_text_edited
RequestFormDialog._on_inline_fact_combo_activated = _on_inline_fact_combo_activated
RequestFormDialog._on_applicant_anchor_editing_finished = _on_applicant_anchor_editing_finished

RequestFormDialog.set_cache_context = _set_cache_context
RequestFormDialog._on_btn_save_clicked = _on_btn_save_clicked
RequestFormDialog._on_btn_import_to_data_mgmt_clicked = _on_btn_import_to_data_mgmt_clicked

RequestFormDialog._apply_target_geometry = _apply_target_geometry
RequestFormDialog._sync_from_target = _sync_from_target
RequestFormDialog._schedule_sync_from_target = _schedule_sync_from_target
RequestFormDialog._register_combo_wheel_block = _register_combo_wheel_block


__all__ = ["RequestFormDialog"]
