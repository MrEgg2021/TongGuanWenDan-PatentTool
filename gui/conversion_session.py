from __future__ import annotations

from PySide6.QtWidgets import QScrollArea


def _best_effort(action) -> None:
    try:
        action()
    except Exception:
        pass


def set_conversion_ui_enabled(window, enabled: bool) -> None:
    _best_effort(
        lambda: hasattr(window, "_modern_shell")
        and hasattr(window._modern_shell, "nav_group")
        and window._modern_shell.nav_group.setEnabled(enabled)
    )
    _best_effort(
        lambda: hasattr(window, "_modern_shell")
        and hasattr(window._modern_shell, "sidebar_toggle")
        and window._modern_shell.sidebar_toggle.setEnabled(enabled)
    )
    _best_effort(
        lambda: (
            (scroll_area := window.findChild(QScrollArea, "MainScrollArea")) is not None
            and scroll_area.setEnabled(enabled)
        )
    )
    _best_effort(lambda: hasattr(window, "btn_run") and window.btn_run.setEnabled(enabled))


def begin_conversion_session(window) -> bool:
    try:
        if getattr(window, "_is_processing_conversion", False):
            return False
    except Exception:
        return False
    try:
        window._is_processing_conversion = True
    except Exception:
        return False
    return True


def release_conversion_session(window) -> None:
    _best_effort(lambda: setattr(window, "_is_processing_conversion", False))
    _best_effort(lambda: setattr(window, "_progress_scope", None))
    _best_effort(lambda: setattr(window, "_cancel_requested", False))
    _best_effort(lambda: hasattr(window, "_hide_processing_overlay") and window._hide_processing_overlay())
    set_conversion_ui_enabled(window, True)


def begin_single_run_session(window, *, fallback: bool = False) -> bool:
    if fallback:
        return True
    try:
        if getattr(window, "_single_run_in_progress", False):
            return False
    except Exception:
        return False
    try:
        window._single_run_in_progress = True
    except Exception:
        return False
    return True


def release_single_run_session(window) -> None:
    _best_effort(lambda: setattr(window, "_single_run_in_progress", False))
    _best_effort(
        lambda: getattr(window, "_progress_scope", None) == "single" and setattr(window, "_progress_scope", None)
    )
    _best_effort(lambda: setattr(window, "_cancel_requested", False))
    _best_effort(lambda: hasattr(window, "_hide_processing_overlay") and window._hide_processing_overlay())
    _best_effort(lambda: hasattr(window, "btn_run") and window.btn_run.setEnabled(True))


def release_batch_run_session(window) -> None:
    _best_effort(
        lambda: getattr(window, "_progress_scope", None) == "batch" and setattr(window, "_progress_scope", None)
    )
    _best_effort(lambda: setattr(window, "_cancel_requested", False))
    _best_effort(lambda: hasattr(window, "_hide_processing_overlay") and window._hide_processing_overlay())
    _best_effort(lambda: hasattr(window, "btn_run") and window.btn_run.setEnabled(True))
