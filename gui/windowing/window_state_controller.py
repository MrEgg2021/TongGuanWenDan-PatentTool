from __future__ import annotations

import base64
from typing import Any

from PySide6.QtCore import QEvent, QObject, QTimer

from core.app_preferences import (
    get_main_window_geometry_v1,
    get_main_window_state_v1,
    set_main_window_geometry_v1,
    set_main_window_state_v1,
)

_CONTROLLER_ATTR = "_window_state_controller_v1"
_LAST_CONTROLLER: "_WindowStateController | None" = None


def _to_b64(raw: bytes | bytearray | memoryview | Any) -> str:
    try:
        data = bytes(raw)
    except Exception:
        data = b""
    if not data:
        return ""
    try:
        return base64.b64encode(data).decode("ascii")
    except Exception:
        return ""


def _from_b64(value: str) -> bytes:
    text = str(value or "").strip()
    if not text:
        return b""
    try:
        return base64.b64decode(text.encode("ascii"), validate=True)
    except Exception:
        return b""


class _WindowStateController(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window = None
        self._paused = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(250)
        self._save_timer.timeout.connect(self._on_save_timeout)

    def bind(self, window) -> None:
        if window is None:
            return
        if self._window is window:
            return
        if self._window is not None:
            try:
                self._window.removeEventFilter(self)
            except Exception:
                pass
        self._window = window
        try:
            window.installEventFilter(self)
        except Exception:
            pass

    def restore(self, window=None) -> None:
        target = window if window is not None else self._window
        if target is None:
            return

        self.pause()
        try:
            geometry_b64 = get_main_window_geometry_v1()
            geometry_raw = _from_b64(geometry_b64 or "")
            if geometry_raw:
                try:
                    target.restoreGeometry(geometry_raw)
                except Exception:
                    pass

            state = get_main_window_state_v1()
            if isinstance(state, dict):
                if bool(state.get("maximized", False)):
                    try:
                        target.showMaximized()
                    except Exception:
                        pass
                elif bool(state.get("fullscreen", False)):
                    try:
                        target.showFullScreen()
                    except Exception:
                        pass
        finally:
            self.resume()

    def save_now(self, window=None) -> None:
        target = window if window is not None else self._window
        if target is None or self._paused:
            return
        self._save_window(target)

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def eventFilter(self, obj, event) -> bool:
        if obj is self._window and event is not None and (not self._paused):
            try:
                event_type = int(event.type())
            except Exception:
                event_type = -1
            if event_type in (
                int(QEvent.Move),
                int(QEvent.Resize),
                int(QEvent.WindowStateChange),
                int(QEvent.Show),
            ):
                self._schedule_save()
        return False

    def _schedule_save(self) -> None:
        if self._paused:
            return
        try:
            self._save_timer.start()
        except Exception:
            pass

    def _on_save_timeout(self) -> None:
        self.save_now()

    def _save_window(self, window) -> None:
        try:
            geometry_raw = window.saveGeometry()
        except Exception:
            geometry_raw = b""
        geometry_b64 = _to_b64(geometry_raw)
        if geometry_b64:
            set_main_window_geometry_v1(geometry_b64)

        state_payload = {
            "maximized": bool(getattr(window, "isMaximized", lambda: False)()),
            "fullscreen": bool(getattr(window, "isFullScreen", lambda: False)()),
        }
        set_main_window_state_v1(state_payload)


def _ensure_controller(window) -> _WindowStateController | None:
    global _LAST_CONTROLLER
    if window is None:
        return _LAST_CONTROLLER
    ctrl = getattr(window, _CONTROLLER_ATTR, None)
    if isinstance(ctrl, _WindowStateController):
        _LAST_CONTROLLER = ctrl
        return ctrl
    ctrl = _WindowStateController(parent=window)
    setattr(window, _CONTROLLER_ATTR, ctrl)
    _LAST_CONTROLLER = ctrl
    return ctrl


def bind(window) -> None:
    ctrl = _ensure_controller(window)
    if ctrl is not None:
        ctrl.bind(window)


def restore(window) -> None:
    ctrl = _ensure_controller(window)
    if ctrl is not None:
        ctrl.restore(window)


def save_now(window) -> None:
    ctrl = _ensure_controller(window)
    if ctrl is not None:
        ctrl.save_now(window)


def pause(window=None) -> None:
    ctrl = _ensure_controller(window)
    if ctrl is not None:
        ctrl.pause()


def resume(window=None) -> None:
    ctrl = _ensure_controller(window)
    if ctrl is not None:
        ctrl.resume()
