import sys
import types
import unittest
from unittest.mock import patch

from core.formal_review.window_docking import DockLayout, DockResult, dock_app_and_word


class FormalReviewWindowDockingTests(unittest.TestCase):
    def test_layout_defaults(self) -> None:
        layout = DockLayout()
        self.assertAlmostEqual(layout.left_ratio, 0.30, places=2)
        self.assertTrue(layout.primary_monitor_only)

    def test_invalid_hwnd_returns_failure(self) -> None:
        result = dock_app_and_word(0, 0, DockLayout())
        self.assertIsInstance(result, DockResult)
        self.assertFalse(result.ok)

    def test_dock_uses_canonical_hwnds_for_positioning(self) -> None:
        calls: list[tuple[str, int]] = []

        def _show_window(hwnd: int, _mode: int) -> None:
            calls.append(("show", int(hwnd)))

        def _set_window_pos(hwnd: int, *_args) -> None:
            calls.append(("set", int(hwnd)))

        fake_con = types.SimpleNamespace(SWP_NOZORDER=0x4, SWP_NOACTIVATE=0x10, SW_RESTORE=9)
        fake_gui = types.SimpleNamespace(
            ShowWindow=_show_window,
            SetWindowPos=_set_window_pos,
            GetWindowRect=lambda _hwnd: (10, 10, 110, 210),
        )

        with patch.dict(sys.modules, {"win32con": fake_con, "win32gui": fake_gui}):
            with patch("core.formal_review.window_docking._primary_monitor_rect", return_value=(0, 0, 1600, 900)):
                with patch(
                    "core.formal_review.window_docking._canonical_top_level_hwnd",
                    side_effect=[101, 202],
                ):
                    result = dock_app_and_word(1, 2, DockLayout(left_ratio=0.3))

        self.assertTrue(result.ok)
        set_targets = [hwnd for kind, hwnd in calls if kind == "set"]
        self.assertEqual(set_targets, [101, 202])

    def test_dock_returns_diagnostic_message_when_setwindowpos_raises(self) -> None:
        def _show_window(_hwnd: int, _mode: int) -> None:
            return None

        def _set_window_pos(_hwnd: int, *_args) -> None:
            raise RuntimeError("boom")

        fake_con = types.SimpleNamespace(SWP_NOZORDER=0x4, SWP_NOACTIVATE=0x10, SW_RESTORE=9)
        fake_gui = types.SimpleNamespace(
            ShowWindow=_show_window,
            SetWindowPos=_set_window_pos,
            GetWindowRect=lambda hwnd: (int(hwnd), 0, int(hwnd) + 100, 200),
        )

        with patch.dict(sys.modules, {"win32con": fake_con, "win32gui": fake_gui}):
            with patch("core.formal_review.window_docking._primary_monitor_rect", return_value=(0, 0, 1200, 800)):
                with patch(
                    "core.formal_review.window_docking._canonical_top_level_hwnd",
                    side_effect=[301, 302],
                ):
                    result = dock_app_and_word(1, 2, DockLayout(left_ratio=0.3))

        self.assertFalse(result.ok)
        self.assertIn("SetWindowPos", result.message)
        self.assertIsNotNone(result.app_rect)
        self.assertIsNotNone(result.word_rect)

    def test_dock_returns_failure_when_canonical_hwnd_invalid(self) -> None:
        with patch("core.formal_review.window_docking._canonical_top_level_hwnd", side_effect=[0, 0]):
            result = dock_app_and_word(11, 22, DockLayout())
        self.assertFalse(result.ok)
        self.assertIn("归一化", result.message)


if __name__ == "__main__":
    unittest.main()
