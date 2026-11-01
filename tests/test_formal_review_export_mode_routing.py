import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.formal_review.models import ClaimItem, FormalReviewDocument, Issue
from gui.main_window.mixins.formal_review_ops import settings_export_ops


class _DummyWindow:
    on_formal_review_export_report = settings_export_ops.on_formal_review_export_report

    def __init__(self, *, mode: str, with_document: bool = True, with_issues: bool = True) -> None:
        self._formal_review_input_mode = mode
        self._formal_review_current_file = "D:/tmp/demo.docx" if mode == "word" else "__formal_review_plain_text__"
        self._formal_review_document = (
            FormalReviewDocument(
                claims=[ClaimItem(num=1, text="一种装置。")],
                description="说明书。",
                abstract="摘要。",
                drawings="附图。",
            )
            if with_document
            else None
        )
        self._formal_review_issues = (
            [
                Issue(
                    rule_id="x",
                    severity="warning",
                    category="rule",
                    section="claims",
                    message="m",
                    claim_num=1,
                )
            ]
            if with_issues
            else []
        )
        self.state_ensured = False

    def _ensure_formal_review_state(self) -> None:
        self.state_ensured = True


class FormalReviewExportModeRoutingTests(unittest.TestCase):
    def test_export_module_does_not_expose_retired_json_or_markdown_writers(self) -> None:
        self.assertFalse(hasattr(settings_export_ops, "write_report_json"))
        self.assertFalse(hasattr(settings_export_ops, "write_report_markdown"))

    def test_word_mode_exports_xlsx_only(self) -> None:
        window = _DummyWindow(mode="word")
        with patch(
            "gui.main_window.mixins.formal_review_ops.settings_export_ops.QFileDialog.getSaveFileName",
            return_value=("D:/tmp/report", "Excel (*.xlsx)"),
        ), patch(
            "gui.main_window.mixins.formal_review_ops.settings_export_ops.build_report_payload",
            return_value={"summary": {}, "issues": []},
        ), patch(
            "gui.main_window.mixins.formal_review_ops.settings_export_ops.write_report_docx",
            return_value="D:/tmp/report.docx",
        ) as mock_docx, patch(
            "gui.main_window.mixins.formal_review_ops.settings_export_ops.write_report_xlsx",
            return_value="D:/tmp/report.xlsx",
        ) as mock_xlsx, patch(
            "gui.main_window.mixins.formal_review_ops.settings_export_ops.QMessageBox.information",
            return_value=0,
        ):
            window.on_formal_review_export_report()

        self.assertTrue(window.state_ensured)
        mock_xlsx.assert_called_once()
        xlsx_path, xlsx_payload = mock_xlsx.call_args.args
        xlsx_kwargs = dict(mock_xlsx.call_args.kwargs or {})
        self.assertEqual(Path(xlsx_path), Path("D:/tmp/report.xlsx"))
        self.assertEqual({"summary": {}, "issues": []}, xlsx_payload)
        self.assertEqual(False, xlsx_kwargs.get("include_ignored_column"))
        mock_docx.assert_not_called()

    def test_plain_text_mode_exports_docx_and_xlsx_only(self) -> None:
        window = _DummyWindow(mode="plain_text")
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "gui.main_window.mixins.formal_review_ops.settings_export_ops.QFileDialog.getExistingDirectory",
            return_value=tmpdir,
        ), patch(
            "gui.main_window.mixins.formal_review_ops.settings_export_ops.build_report_payload",
            return_value={"summary": {}, "issues": []},
        ), patch(
            "gui.main_window.mixins.formal_review_ops.settings_export_ops.write_report_docx",
            return_value=str(Path(tmpdir) / "r.docx"),
        ) as mock_docx, patch(
            "gui.main_window.mixins.formal_review_ops.settings_export_ops.write_report_xlsx",
            return_value=str(Path(tmpdir) / "r.xlsx"),
        ) as mock_xlsx, patch(
            "gui.main_window.mixins.formal_review_ops.settings_export_ops.QMessageBox.information",
            return_value=0,
        ):
            window.on_formal_review_export_report()

        self.assertTrue(window.state_ensured)
        mock_docx.assert_called_once()
        mock_xlsx.assert_called_once()
        self.assertEqual(True, dict(mock_xlsx.call_args.kwargs or {}).get("include_ignored_column"))

    def test_export_is_blocked_when_no_document_or_issues(self) -> None:
        window = _DummyWindow(mode="word", with_document=False, with_issues=False)
        with patch(
            "gui.main_window.mixins.formal_review_ops.settings_export_ops.QMessageBox.information",
            return_value=0,
        ) as mock_info, patch(
            "gui.main_window.mixins.formal_review_ops.settings_export_ops.write_report_xlsx",
            return_value="D:/tmp/report.xlsx",
        ) as mock_xlsx:
            window.on_formal_review_export_report()

        self.assertTrue(window.state_ensured)
        mock_info.assert_called_once()
        mock_xlsx.assert_not_called()


if __name__ == "__main__":
    unittest.main()
