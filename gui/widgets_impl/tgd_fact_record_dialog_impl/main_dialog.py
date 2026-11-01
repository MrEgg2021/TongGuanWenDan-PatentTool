from __future__ import annotations

from PySide6.QtCore import Qt, QEvent, QEventLoop, QTimer, QPoint, QRect
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from gui.widgets_impl.combo_wheel_blocker import ComboWheelBlocker
from .db_save_ops import _collect_record, _is_empty_payload, _on_save_clicked
from .region_ops import _init_region_widgets, _on_applicant_province_changed, _on_contact_province_changed
from .ui_build_ops import (
    _build_agency_poa_section,
    _build_applicant_section,
    _build_contact_section,
    _build_group_section,
    _build_inventor_section,
    _build_ui,
    _new_group,
)


class TgdFactRecordDialog(QDialog):
    _build_ui = _build_ui
    _new_group = _new_group
    _build_applicant_section = _build_applicant_section
    _build_agency_poa_section = _build_agency_poa_section
    _build_inventor_section = _build_inventor_section
    _build_contact_section = _build_contact_section
    _build_group_section = _build_group_section

    _init_region_widgets = _init_region_widgets
    _on_applicant_province_changed = _on_applicant_province_changed
    _on_contact_province_changed = _on_contact_province_changed

    _collect_record = _collect_record
    _is_empty_payload = _is_empty_payload
    _on_save_clicked = _on_save_clicked

    def __init__(self, parent=None):
        super().__init__(parent)
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

        self._dialog_result: int = QDialog.Rejected
        self._exec_loop: QEventLoop | None = None
        self._size_target: QWidget | None = None
        self._pending_resize_sync = False

        self._combo_wheel_blocker = ComboWheelBlocker(self)

        self._build_ui()
        self._init_region_widgets()

        try:
            self._combo_wheel_blocker.register_strict_scroll_area(getattr(self, "_scroll_area", None))
        except Exception:
            pass

        try:
            self._combo_wheel_blocker.register_combo(self.applicant_type_combo)
            self._combo_wheel_blocker.register_combo(self.applicant_id_type_combo)
            self._combo_wheel_blocker.register_combo(self.applicant_province_combo)
            self._combo_wheel_blocker.register_combo(self.applicant_city_combo)
            self._combo_wheel_blocker.register_combo(self.inventor_id_type_combo)
            self._combo_wheel_blocker.register_combo(self.contact_province_combo)
            self._combo_wheel_blocker.register_combo(self.contact_city_combo)
        except Exception:
            pass

        try:
            self.btn_save.clicked.connect(self._on_save_clicked)
        except Exception:
            pass
        try:
            self.btn_close.clicked.connect(self.reject)
        except Exception:
            pass

    def _apply_target_geometry(self, target: QWidget | None) -> None:
        if target is None:
            return

        try:
            pos = target.mapToGlobal(QPoint(0, 0))
            self.setGeometry(QRect(pos, target.size()))
        except Exception:
            try:
                self.setGeometry(target.rect())
            except Exception:
                pass

        try:
            card = getattr(self, "_card", None)
            if card is None:
                return
            try:
                tw = int(target.size().width())
                th = int(target.size().height())
            except Exception:
                tw = 0
                th = 0

            w = 820
            h = 620
            if tw > 0:
                desired_w = int(tw * 0.92)
                max_w = max(560, tw - 40)
                w = min(desired_w, max_w)
                w = max(560, w)

            if th > 0:
                desired_h = max(520, int(th * 0.92))
                max_h = max(420, th - 40)
                h = min(desired_h, max_h)
                h = max(420, h)

            card.setFixedSize(int(w), int(h))
        except Exception:
            pass

    def _sync_from_target(self) -> None:
        try:
            self._pending_resize_sync = False
        except Exception:
            pass
        target = getattr(self, "_size_target", None)
        if target is None:
            return
        self._apply_target_geometry(target)

    def _schedule_sync_from_target(self) -> None:
        try:
            if bool(getattr(self, "_pending_resize_sync", False)):
                return
            self._pending_resize_sync = True
        except Exception:
            return
        try:
            QTimer.singleShot(0, self._sync_from_target)
        except Exception:
            pass

    def exec(self) -> int:  # type: ignore[override]
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

        self._apply_target_geometry(target)

        self._dialog_result = QDialog.Rejected
        self.show()
        self.raise_()

        loop = QEventLoop(self)
        self._exec_loop = loop
        loop.exec()
        return int(self._dialog_result)

    def _finish_dialog(self, accepted: bool) -> None:
        self._dialog_result = QDialog.Accepted if accepted else QDialog.Rejected
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
        self._finish_dialog(False)

    def accept(self) -> None:  # type: ignore[override]
        self._finish_dialog(True)

    def eventFilter(self, obj, event):  # type: ignore[override]
        try:
            size_target = getattr(self, "_size_target", None)
            if size_target is not None and obj is size_target:
                if event.type() in (QEvent.Resize, QEvent.Move):
                    self._schedule_sync_from_target()
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):  # type: ignore[override]
        try:
            if event.key() == Qt.Key_Escape:
                event.ignore()
                return
        except Exception:
            pass
        return super().keyPressEvent(event)


__all__ = ["TgdFactRecordDialog"]
