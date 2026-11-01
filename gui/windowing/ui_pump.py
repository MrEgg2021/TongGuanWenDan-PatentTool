from __future__ import annotations

import threading

from PySide6.QtCore import QEventLoop
from PySide6.QtWidgets import QApplication

_PUMP_STATE = threading.local()


def pump(*, allow_user_input: bool = False) -> bool:
    """Process one UI event cycle with re-entrancy guard."""
    app = QApplication.instance()
    if app is None:
        return False

    if bool(getattr(_PUMP_STATE, "active", False)):
        return False

    flags = QEventLoop.AllEvents if bool(allow_user_input) else QEventLoop.ExcludeUserInputEvents
    _PUMP_STATE.active = True
    try:
        app.processEvents(flags)
        return True
    finally:
        _PUMP_STATE.active = False

