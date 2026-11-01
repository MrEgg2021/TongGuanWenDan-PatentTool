from __future__ import annotations

from PySide6.QtCore import QEvent, QEventLoop, QTimer, QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from gui.dialog_utils import ask_continue_cancel
from gui.widgets_impl.tgd_zip_import_review_debug_ops import zip_dbg
from gui.widgets_impl.tgd_zip_import_review_utils import _norm_text

from .types import ImportAction


def exec_dialog(dlg) -> int:
    if bool(getattr(dlg, "_embedded", False)):
        dlg._dialog_result = QDialog.Rejected
        try:
            dlg.show()
        except Exception:
            pass
        loop = QEventLoop(dlg)
        dlg._exec_loop = loop
        loop.exec()
        return int(getattr(dlg, "_dialog_result", QDialog.Rejected))

    try:
        zip_dbg(f"dialog.exec source={_norm_text(getattr(dlg, '_source_file_path', ''))}")
    except Exception:
        pass
    owner = dlg.parentWidget()
    if owner is None:
        try:
            owner = QApplication.activeWindow()
        except Exception:
            owner = None

    if owner is not None and dlg.parentWidget() is None:
        try:
            dlg.setParent(owner)
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
        prev_target = getattr(dlg, "_size_target", None)
        if prev_target is not None:
            prev_target.removeEventFilter(dlg)
    except Exception:
        pass
    try:
        dlg._size_target = target
    except Exception:
        dlg._size_target = None
    try:
        if dlg._size_target is not None:
            dlg._size_target.installEventFilter(dlg)
    except Exception:
        pass

    apply_target_geometry(dlg, target)

    dlg._dialog_result = QDialog.Rejected
    dlg.show()
    dlg.raise_()

    loop = QEventLoop(dlg)
    dlg._exec_loop = loop
    loop.exec()
    return int(getattr(dlg, "_dialog_result", QDialog.Rejected))


def finish_dialog(dlg, accepted: bool) -> None:
    dlg._dialog_result = QDialog.Accepted if accepted else QDialog.Rejected
    if bool(getattr(dlg, "_embedded", False)):
        try:
            dlg.hide()
        except Exception:
            pass
        try:
            if dlg._exec_loop is not None:
                dlg._exec_loop.quit()
        except Exception:
            pass
        return

    try:
        if dlg._size_target is not None:
            dlg._size_target.removeEventFilter(dlg)
    except Exception:
        pass
    try:
        dlg._size_target = None
    except Exception:
        pass
    try:
        dlg.hide()
    except Exception:
        pass
    try:
        if dlg._exec_loop is not None:
            dlg._exec_loop.quit()
    except Exception:
        pass

    try:
        QTimer.singleShot(0, lambda: dlg.setParent(None))
        QTimer.singleShot(0, dlg.deleteLater)
    except Exception:
        pass


def reject_dialog(dlg) -> None:
    if getattr(dlg, "_dirty", False):
        if not ask_continue_cancel(dlg, "提示", "关闭将跳过该 ZIP 导入。\n\n是否仍然关闭？", continue_text="跳过", cancel_text="取消"):
            return
    dlg._action = ImportAction.SKIP
    finish_dialog(dlg, False)


def on_event_filter(dlg, obj, event) -> None:
    try:
        size_target = getattr(dlg, "_size_target", None)
        if size_target is not None and obj is size_target:
            if event.type() in (QEvent.Resize, QEvent.Move):
                schedule_sync_from_target(dlg)
    except Exception:
        pass


def on_key_press_event(event) -> bool:
    try:
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return True
    except Exception:
        pass
    return False


def apply_target_geometry(dlg, target: QWidget | None) -> None:
    if target is None:
        return
    try:
        pos = target.mapToGlobal(QPoint(0, 0))
        dlg.setGeometry(QRect(pos, target.size()))
    except Exception:
        try:
            dlg.setGeometry(target.rect())
        except Exception:
            pass

    try:
        card = getattr(dlg, "_card", None)
        if card is None:
            return
        tw = int(target.size().width())
        th = int(target.size().height())
        w = min(max(980, int(tw * 0.96)), max(760, tw - 40))
        h = min(max(760, int(th * 0.97)), max(560, th - 30))
        card.setFixedSize(int(w), int(h))
    except Exception:
        pass


def sync_from_target(dlg) -> None:
    dlg._pending_resize_sync = False
    target = getattr(dlg, "_size_target", None)
    if target is None:
        return
    apply_target_geometry(dlg, target)


def schedule_sync_from_target(dlg) -> None:
    try:
        if bool(getattr(dlg, "_pending_resize_sync", False)):
            return
        dlg._pending_resize_sync = True
    except Exception:
        return
    try:
        QTimer.singleShot(0, lambda: sync_from_target(dlg))
    except Exception:
        pass
