from __future__ import annotations

from PySide6.QtCore import QEventLoop
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from core.user_messages import user_error_text
from gui.ui_modals import build_blocking_alert
from gui.windowing import overlay_controller as overlay_controller_api


def resolve_modal_owner(parent):
    owner = parent
    try:
        shell = getattr(parent, "_modern_shell", None)
        main_area = getattr(shell, "main_area", None) if shell else None
        if main_area is not None:
            owner = main_area
    except Exception:
        owner = parent

    if owner is None:
        try:
            owner = QApplication.activeWindow()
        except Exception:
            owner = None
    return owner


def ask_continue_cancel(
    parent,
    title: str,
    text: str,
    *,
    continue_text: str = "继续",
    cancel_text: str = "取消",
    default_continue: bool = True,
    icon: QMessageBox.Icon | None = QMessageBox.Question,
    apply_button_style: bool = True,
    apply_content_frame: bool = True,
) -> bool:
    owner = parent
    if owner is None:
        try:
            owner = QApplication.activeWindow()
        except Exception:
            owner = None

    _ = (default_continue, apply_button_style, apply_content_frame)

    choice = show_blocking_alert_modal(
        owner,
        title,
        text,
        primary_text=continue_text,
        secondary_text=cancel_text,
    )
    return choice == "primary"


def show_blocking_alert_modal(
    parent,
    title: str,
    body: str,
    *,
    primary_text: str = "重试",
    secondary_text: str = "跳过",
    tertiary_text: str | None = None,
    body_variant: str | None = None,
    close_result: str | None = None,
) -> str:
    """
    使用自定义遮罩弹窗的阻断式警告，返回 "primary" 或 "secondary"。
    """
    choice = "secondary"
    overlay = None
    overlay_name = ""
    loop = QEventLoop()
    try:
        if any(word in title for word in ("错误", "失败", "异常", "不可用", "受阻")):
            body = user_error_text(body)
        owner = resolve_modal_owner(parent)
        overlay = build_blocking_alert(
            owner,
            title_text=title,
            body_text=body,
            primary_text=primary_text,
            secondary_text=secondary_text,
            tertiary_text=tertiary_text,
            body_variant=body_variant,
        )
        if overlay and owner:
            overlay.setParent(owner)
            overlay_name = f"blocking_alert_modal_{id(loop)}"
            try:
                overlay_controller_api.attach(overlay_name, overlay, owner)
                overlay_controller_api.set_modal_active(True)
            except Exception:
                pass
        btn_primary = overlay.findChild(QPushButton, "alertPrimary") if overlay else None
        btn_secondary = overlay.findChild(QPushButton, "alertSecondary") if overlay else None
        btn_tertiary = overlay.findChild(QPushButton, "alertTertiary") if overlay else None
        btn_close_x = overlay.findChild(QPushButton, "ModalCloseButton") if overlay else None

        try:
            p_txt = (primary_text or "").strip()
            s_txt = (secondary_text or "").strip()
            if btn_secondary and (not s_txt or p_txt == s_txt):
                btn_secondary.setVisible(False)
                choice = "primary"
        except Exception:
            pass

        close_choice = "secondary"
        try:
            if btn_secondary is None or (hasattr(btn_secondary, "isVisible") and not btn_secondary.isVisible()):
                close_choice = "primary"
        except Exception:
            close_choice = "secondary"
        if close_result is not None:
            try:
                close_choice = str(close_result)
            except Exception:
                close_choice = "secondary"

        def _on_primary():
            nonlocal choice
            choice = "primary"
            loop.quit()

        def _on_secondary():
            nonlocal choice
            choice = "secondary"
            loop.quit()

        def _on_tertiary():
            nonlocal choice
            choice = "tertiary"
            loop.quit()

        def _on_close_x():
            nonlocal choice
            choice = close_choice
            loop.quit()

        if btn_primary:
            btn_primary.clicked.connect(_on_primary)
        if btn_secondary:
            btn_secondary.clicked.connect(_on_secondary)
        if btn_tertiary:
            btn_tertiary.clicked.connect(_on_tertiary)
        if btn_close_x:
            btn_close_x.clicked.connect(_on_close_x)
        if overlay:
            overlay.show()
            overlay.raise_()
        loop.exec()
    except Exception:
        choice = "secondary"
    finally:
        if overlay_name:
            try:
                overlay_controller_api.set_modal_active(False)
            except Exception:
                pass
            try:
                overlay_controller_api.detach(overlay_name)
            except Exception:
                pass
        try:
            if overlay:
                overlay.setParent(None)
                overlay.deleteLater()
        except Exception:
            pass
    return choice
