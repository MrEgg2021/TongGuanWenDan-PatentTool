from __future__ import annotations

import unittest
from unittest import mock

from PySide6.QtCore import QEvent

from gui.windowing import window_state_controller as window_state


class _FakeWindow:
    def __init__(self) -> None:
        self.restored_geometry = None
        self.maximized = False
        self.fullscreen = False
        self.event_filters: list[object] = []

    def installEventFilter(self, filt) -> None:
        self.event_filters.append(filt)

    def removeEventFilter(self, filt) -> None:
        if filt in self.event_filters:
            self.event_filters.remove(filt)

    def saveGeometry(self) -> bytes:
        return b"geom-bytes"

    def restoreGeometry(self, raw: bytes) -> None:
        self.restored_geometry = bytes(raw)

    def isMaximized(self) -> bool:
        return self.maximized

    def isFullScreen(self) -> bool:
        return self.fullscreen

    def showMaximized(self) -> None:
        self.maximized = True

    def showFullScreen(self) -> None:
        self.fullscreen = True


class _FakeEvent:
    def __init__(self, event_type: int) -> None:
        self._event_type = int(event_type)

    def type(self) -> int:
        return self._event_type


class WindowStateControllerTests(unittest.TestCase):
    def test_save_window_persists_geometry_and_state(self) -> None:
        ctrl = window_state._WindowStateController(parent=None)
        win = _FakeWindow()
        with (
            mock.patch("gui.windowing.window_state_controller.set_main_window_geometry_v1") as m_set_geo,
            mock.patch("gui.windowing.window_state_controller.set_main_window_state_v1") as m_set_state,
        ):
            ctrl._save_window(win)
        m_set_geo.assert_called_once()
        m_set_state.assert_called_once_with({"maximized": False, "fullscreen": False})

    def test_restore_applies_saved_geometry_and_maximized_state(self) -> None:
        ctrl = window_state._WindowStateController(parent=None)
        win = _FakeWindow()
        with (
            mock.patch("gui.windowing.window_state_controller.get_main_window_geometry_v1", return_value="Z2VvbQ=="),
            mock.patch("gui.windowing.window_state_controller.get_main_window_state_v1", return_value={"maximized": True}),
        ):
            ctrl.restore(win)
        self.assertEqual(win.restored_geometry, b"geom")
        self.assertTrue(win.maximized)

    def test_event_filter_triggers_schedule_for_resize(self) -> None:
        ctrl = window_state._WindowStateController(parent=None)
        win = _FakeWindow()
        ctrl.bind(win)
        with mock.patch.object(ctrl, "_schedule_save") as m_schedule:
            handled = ctrl.eventFilter(win, _FakeEvent(int(QEvent.Resize)))
        self.assertFalse(handled)
        m_schedule.assert_called_once()


if __name__ == "__main__":
    unittest.main()

