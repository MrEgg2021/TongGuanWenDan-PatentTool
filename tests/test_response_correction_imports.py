from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gui.app_impl.response_correction_imports import (
    collect_response_correction_files,
    role_label_for_code,
    role_options_for_flow,
    should_attempt_notice_parse,
    suggest_role_for_path,
)


class ResponseCorrectionImportsTests(unittest.TestCase):
    def test_collect_response_correction_files_scans_directory_tree_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "claims.docx").write_text("x", encoding="utf-8")
            (root / "bundle.zip").write_text("x", encoding="utf-8")
            (root / "~$temp.docx").write_text("x", encoding="utf-8")
            nested = root / "nested"
            nested.mkdir()
            (nested / "nested.docx").write_text("x", encoding="utf-8")
            deep = nested / "deep"
            deep.mkdir()
            (deep / "deep.pdf").write_text("x", encoding="utf-8")

            valid, ignored = collect_response_correction_files([str(root)])

        self.assertIn(str(root / "claims.docx"), valid)
        self.assertIn(str(root / "bundle.zip"), valid)
        self.assertIn(str(nested / "nested.docx"), valid)
        self.assertIn(str(deep / "deep.pdf"), valid)
        self.assertTrue(any("temp.docx" in item for item in ignored))

    def test_collect_response_correction_files_reports_tree_when_no_supported_files_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "nested").mkdir()
            (root / "nested" / "notes.txt").write_text("x", encoding="utf-8")

            valid, ignored = collect_response_correction_files([str(root)])

        self.assertEqual(valid, [])
        self.assertTrue(any("整个目录树" in item for item in ignored))

    def test_directory_collection_uses_single_canonicalization_step_for_seen_keys(self) -> None:
        source = Path("gui/app_impl/response_correction_imports.py").read_text(encoding="utf-8")

        self.assertNotIn("full_path = os.path.normpath(os.path.join(current_root, entry))", source)

    def test_role_options_follow_flow_capabilities(self) -> None:
        response_roles = [code for _label, code in role_options_for_flow("response")]
        correction_roles = [code for _label, code in role_options_for_flow("correction")]

        self.assertIn("opinion_body", response_roles)
        self.assertNotIn("opinion_body", correction_roles)
        self.assertNotIn("comparison_pdf", response_roles)
        self.assertNotIn("comparison_pdf", correction_roles)
        self.assertIn("100001", correction_roles)

    def test_role_options_use_canonical_document_slot_labels(self) -> None:
        response_roles = dict(role_options_for_flow("response"))
        correction_roles = dict(role_options_for_flow("correction"))

        self.assertEqual(response_roles["说明书附图"], "100003")
        self.assertEqual(response_roles["说明书摘要"], "100004")
        self.assertEqual(correction_roles["说明书附图"], "100003")
        self.assertEqual(correction_roles["说明书摘要"], "100004")
        self.assertEqual(role_label_for_code("100003"), "说明书附图")
        self.assertEqual(role_label_for_code("100004"), "说明书摘要")

    def test_should_attempt_notice_parse_supports_active_flows_for_zip_and_pdf(self) -> None:
        self.assertTrue(should_attempt_notice_parse("D:/notice.zip", "active_response"))
        self.assertTrue(should_attempt_notice_parse("D:/notice.pdf", "active_response"))
        self.assertTrue(should_attempt_notice_parse("D:/notice.zip", "active_correction"))
        self.assertTrue(should_attempt_notice_parse("D:/notice.pdf", "active_correction"))
        self.assertFalse(should_attempt_notice_parse("D:/claims.docx", "active_response"))

    def test_suggest_role_uses_filename_keywords_without_auto_confirming(self) -> None:
        self.assertEqual(suggest_role_for_path("D:/意见陈述书.docx", "response"), "opinion_body")
        self.assertEqual(suggest_role_for_path("D:/修改对照页.docx", "response"), "")
        self.assertEqual(suggest_role_for_path("D:/claims.docx", "correction"), "100001")

    def test_suggest_role_maps_abstract_and_drawings_keywords_to_canonical_slots(self) -> None:
        for path in ("D:/摘要.docx", "D:/abstract.docx", "D:/说明书摘要.docx"):
            with self.subTest(path=path):
                self.assertEqual(suggest_role_for_path(path, "correction"), "100004")

        for path in ("D:/附图.docx", "D:/drawings.docx", "D:/说明书附图.docx", "D:/摘要附图.docx"):
            with self.subTest(path=path):
                self.assertEqual(suggest_role_for_path(path, "correction"), "100003")

        self.assertEqual(suggest_role_for_path("D:/说明书.docx", "correction"), "100002")
        self.assertEqual(suggest_role_for_path("D:/description.docx", "correction"), "100002")


if __name__ == "__main__":
    unittest.main()
