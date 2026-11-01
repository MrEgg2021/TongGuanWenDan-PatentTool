from __future__ import annotations

import unittest
from unittest.mock import patch

from gui.single_run_impl import postprocess_flow


class SingleRunSupportDiagnosticsPromptTests(unittest.TestCase):
    def test_table_failure_prompt_uses_user_safe_wording(self) -> None:
        result = {
            "table_screenshot_failures": [
                {
                    "section": "description",
                    "desc_para_num": 8,
                    "stage": "WORD_PDF_EXPORT_FAILED",
                    "error": "COM PDF traceback",
                }
            ]
        }

        with patch.object(postprocess_flow, "show_blocking_alert_modal") as alert_mock:
            postprocess_flow._maybe_alert_table_screenshot_failures(object(), result)

        body = alert_mock.call_args.args[2]
        self.assertIn("部分表格未能自动转换", body)
        self.assertIn("人工复查", body)
        self.assertNotIn("截图失败", body)
        self.assertNotIn("PDF", body)
        self.assertNotIn("COM", body)
        self.assertNotIn("traceback", body.lower())


if __name__ == "__main__":
    unittest.main()
