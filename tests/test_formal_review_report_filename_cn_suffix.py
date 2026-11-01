import unittest
from pathlib import Path


class FormalReviewReportFilenameCnSuffixTests(unittest.TestCase):
    def test_plain_text_report_default_name_uses_cn_prefix(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/settings_export_ops.py").read_text(encoding="utf-8")
        self.assertIn('base = f"形式审查报告_{stamp}"', source)

    def test_word_mode_report_default_name_uses_cn_suffix_with_timestamp(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/settings_export_ops.py").read_text(encoding="utf-8")
        self.assertIn('stamp = datetime.now().strftime("%Y%m%d_%H%M%S")', source)
        self.assertIn('suggested_name = f"{default_name}_形式审查报告_{stamp}.xlsx"', source)
        self.assertIn("QFileDialog.getSaveFileName(self, \"导出 Excel 报告\", suggested_name, \"Excel (*.xlsx)\")", source)


if __name__ == "__main__":
    unittest.main()
