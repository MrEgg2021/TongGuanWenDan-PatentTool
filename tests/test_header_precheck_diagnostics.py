from __future__ import annotations

import unittest
from unittest.mock import patch

from gui.header_check import _offer_header_precheck_hint


class HeaderPrecheckDiagnosticsTests(unittest.TestCase):
    def test_header_precheck_dialog_shows_plain_hint_without_diagnostic_export(self) -> None:
        with patch("gui.header_check.show_blocking_alert_modal") as alert_mock:
            _offer_header_precheck_hint(object(), "demo.docx", "检测页眉时出错：boom")

        alert_mock.assert_called_once()
        body = alert_mock.call_args.args[2]
        self.assertIn("检测页眉时出错", body)
        self.assertNotIn("导出诊断包", body)


if __name__ == "__main__":
    unittest.main()
