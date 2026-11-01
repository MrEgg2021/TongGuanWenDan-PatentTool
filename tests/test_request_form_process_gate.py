from __future__ import annotations
import types
import unittest
from unittest.mock import patch


class _DummyCheck:

    def __init__(self, checked: bool=True) -> None:
        self._checked = bool(checked)

    def isChecked(self) -> bool:
        return bool(self._checked)


class RequestFormProcessGateTests(unittest.TestCase):

    def test_request_form_office_check_uses_unified_guard(self) -> None:
        from gui.single_run_impl import preflight_flow
        window = types.SimpleNamespace()
        with patch('gui.single_run_impl.preflight_flow.ensure_office_processes_ready', return_value=False) as guard_mock:
            result = preflight_flow._ensure_office_closed_for_request_form(window)
        self.assertFalse(result)
        guard_mock.assert_called_once_with(window, context='request_form_preflight')
if __name__ == '__main__':
    unittest.main()
