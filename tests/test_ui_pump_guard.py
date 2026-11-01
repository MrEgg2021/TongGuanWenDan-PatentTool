from __future__ import annotations

import unittest
from unittest import mock

from gui.windowing import ui_pump


class _FakeApp:
    def __init__(self) -> None:
        self.calls = 0
        self.nested_result = None
        self.flags = []

    def processEvents(self, flags) -> None:
        self.calls += 1
        self.flags.append(flags)
        if self.calls == 1:
            self.nested_result = ui_pump.pump(allow_user_input=False)


class UiPumpGuardTests(unittest.TestCase):
    def test_pump_returns_false_when_app_missing(self) -> None:
        with mock.patch("gui.windowing.ui_pump.QApplication") as m_app_cls:
            m_app_cls.instance.return_value = None
            self.assertFalse(ui_pump.pump(allow_user_input=False))

    def test_pump_blocks_reentrant_call(self) -> None:
        fake_app = _FakeApp()
        with mock.patch("gui.windowing.ui_pump.QApplication") as m_app_cls:
            m_app_cls.instance.return_value = fake_app
            ok = ui_pump.pump(allow_user_input=False)
        self.assertTrue(ok)
        self.assertEqual(fake_app.calls, 1)
        self.assertFalse(fake_app.nested_result)


if __name__ == "__main__":
    unittest.main()

