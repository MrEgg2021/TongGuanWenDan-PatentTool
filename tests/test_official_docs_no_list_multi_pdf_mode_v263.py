from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from gui.main_window.mixins.official_docs_mixin import OfficialDocsMixin
from gui.main_window.mixins.official_docs_ops import shared

from tests.official_docs_source_loader import read_official_docs_mixin_source, read_official_docs_page_source


class OfficialDocsNoListMultiPdfModeV263Tests(unittest.TestCase):
    def test_default_settings_use_split_each_pdf_mode(self) -> None:
        defaults = shared._default_settings()
        self.assertEqual(defaults["no_list_multi_pdf_mode"], "split_each_pdf")

    def test_normalize_settings_backfills_missing_mode(self) -> None:
        dummy = OfficialDocsMixin()
        raw = {
            "version": shared.OFFICIAL_DOC_SETTINGS_VERSION,
            "write_summary": True,
            "write_archive": False,
            "confirm_each": False,
            "enable_exam_pdf_parse": False,
            "summary_root_dir": "D:/summary",
            "archive_root_dir": "D:/archive",
            "type_configs": {},
        }
        with patch("gui.main_window.mixins.official_docs_ops.state_ops.set_official_doc_settings"):
            normalized = dummy._normalize_official_doc_settings(raw)
        self.assertEqual(normalized["no_list_multi_pdf_mode"], "split_each_pdf")

    def test_settings_panel_exposes_mode_combo_and_labels(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn('mode_no_list_multi_pdf = QComboBox()', text)
        self.assertIn('mode_no_list_multi_pdf.addItem("逐个 PDF 输出（默认）", "split_each_pdf")', text)
        self.assertIn('mode_no_list_multi_pdf.addItem("整包合并输出", "merge_all")', text)
        self.assertIn("window.official_docs_no_list_multi_pdf_mode_combo = mode_no_list_multi_pdf", text)

    def test_mixin_reads_and_writes_mode_setting(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn('"no_list_multi_pdf_mode": "split_each_pdf"', text)
        self.assertIn('settings["no_list_multi_pdf_mode"] = str(', text)
        self.assertIn('source.get("no_list_multi_pdf_mode", "split_each_pdf")', text)


if __name__ == "__main__":
    unittest.main()
