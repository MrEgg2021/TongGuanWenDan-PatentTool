from __future__ import annotations

import unittest

from PySide6.QtCore import QEvent

from gui.windowing.overlay_controller import _OverlayController


class _FakeToggle:
    def __init__(self) -> None:
        self.enabled = True

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)


class _FakeShell:
    def __init__(self) -> None:
        self.sidebar_toggle = _FakeToggle()


class _FakeWindow:
    def __init__(self) -> None:
        self._modern_shell = _FakeShell()


class _FakeOwner:
    def __init__(self) -> None:
        self.rect_value = (0, 0, 100, 100)
        self.filters: list[object] = []
        self._window = _FakeWindow()

    def rect(self):
        return self.rect_value

    def installEventFilter(self, filt) -> None:
        self.filters.append(filt)

    def removeEventFilter(self, filt) -> None:
        if filt in self.filters:
            self.filters.remove(filt)

    def window(self):
        return self._window


class _FakeOverlay:
    def __init__(self) -> None:
        self.parent = None
        self.geometry = None
        self.raised = 0

    def setParent(self, parent) -> None:
        self.parent = parent

    def setGeometry(self, geometry) -> None:
        self.geometry = geometry

    def raise_(self) -> None:
        self.raised += 1


class _FakeEvent:
    def __init__(self, event_type: int) -> None:
        self._event_type = int(event_type)

    def type(self) -> int:
        return self._event_type


class OverlayControllerTests(unittest.TestCase):
    def test_attach_and_relayout_follow_owner_geometry(self) -> None:
        ctrl = _OverlayController()
        owner = _FakeOwner()
        overlay = _FakeOverlay()

        ctrl.attach("x", overlay, owner)
        self.assertIs(overlay.parent, owner)
        self.assertEqual(overlay.geometry, owner.rect_value)

        owner.rect_value = (0, 0, 200, 150)
        ctrl.relayout("x", reason="test")
        self.assertEqual(overlay.geometry, (0, 0, 200, 150))

    def test_detach_removes_record(self) -> None:
        ctrl = _OverlayController()
        owner = _FakeOwner()
        overlay = _FakeOverlay()
        ctrl.attach("x", overlay, owner)
        ctrl.detach("x")
        self.assertNotIn("x", ctrl._records)
        self.assertNotIn("x", ctrl._name_to_attach_seq)

    def test_modal_active_disables_sidebar_toggle(self) -> None:
        ctrl = _OverlayController()
        owner = _FakeOwner()
        overlay = _FakeOverlay()
        ctrl.attach("x", overlay, owner)

        ctrl.set_modal_active(True)
        self.assertFalse(owner.window()._modern_shell.sidebar_toggle.enabled)
        ctrl.set_modal_active(False)
        self.assertTrue(owner.window()._modern_shell.sidebar_toggle.enabled)

    def test_owner_resize_event_triggers_relayout(self) -> None:
        ctrl = _OverlayController()
        owner = _FakeOwner()
        overlay = _FakeOverlay()
        ctrl.attach("x", overlay, owner)
        owner.rect_value = (0, 0, 320, 180)
        ctrl.eventFilter(owner, _FakeEvent(int(QEvent.Resize)))
        self.assertEqual(overlay.geometry, (0, 0, 320, 180))

    def test_detach_before_deactivate_still_restores_sidebar_toggle(self) -> None:
        ctrl = _OverlayController()
        owner = _FakeOwner()
        overlay = _FakeOverlay()
        ctrl.attach("x", overlay, owner)

        ctrl.set_modal_active(True)
        self.assertTrue(ctrl.is_modal_active())
        self.assertFalse(owner.window()._modern_shell.sidebar_toggle.enabled)

        ctrl.detach("x")
        ctrl.set_modal_active(False)
        self.assertFalse(ctrl.is_modal_active())
        self.assertTrue(owner.window()._modern_shell.sidebar_toggle.enabled)

    def test_reconcile_sidebar_toggle_without_records_uses_window_hint(self) -> None:
        ctrl = _OverlayController()
        win = _FakeWindow()
        win._modern_shell.sidebar_toggle.enabled = False

        ctrl.reconcile_sidebar_toggle(win)
        self.assertTrue(win._modern_shell.sidebar_toggle.enabled)

        ctrl.set_modal_active(True)
        ctrl.reconcile_sidebar_toggle(win)
        self.assertFalse(win._modern_shell.sidebar_toggle.enabled)

        ctrl.set_modal_active(False)
        ctrl.reconcile_sidebar_toggle(win)
        self.assertTrue(win._modern_shell.sidebar_toggle.enabled)

    def test_same_owner_relayout_uses_attach_order(self) -> None:
        ctrl = _OverlayController()
        owner = _FakeOwner()
        raise_trace: list[str] = []

        class _TrackOverlay(_FakeOverlay):
            def __init__(self, name: str) -> None:
                super().__init__()
                self._name = name

            def raise_(self) -> None:
                super().raise_()
                raise_trace.append(self._name)

        old_overlay = _TrackOverlay("old")
        new_overlay = _TrackOverlay("new")
        ctrl.attach("old", old_overlay, owner)
        ctrl.attach("new", new_overlay, owner)
        raise_trace.clear()

        ctrl.eventFilter(owner, _FakeEvent(int(QEvent.LayoutRequest)))
        self.assertEqual(["old", "new"], raise_trace)


if __name__ == "__main__":
    unittest.main()
