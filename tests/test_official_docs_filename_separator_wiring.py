from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from gui.main_window.mixins.official_docs_mixin import OfficialDocsMixin
from gui.main_window.mixins.official_docs_ops import shared
from tests.official_docs_source_loader import read_official_docs_mixin_source, read_official_docs_page_source


class OfficialDocsFilenameSeparatorWiringTests(unittest.TestCase):
    def test_settings_panel_exposes_global_separator_input(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)

        self.assertIn('separator_label = QLabel("字段连接符：")', text)
        self.assertIn('separator_edit.setObjectName("OfficialDocsFilenameSeparatorEdit")', text)
        self.assertIn('separator_edit.textChanged.connect(window.on_official_docs_settings_changed)', text)
        self.assertIn("window.official_docs_filename_separator_edit = separator_edit", text)

    def test_settings_default_and_normalization_preserve_global_separator(self) -> None:
        defaults = shared._default_settings()
        self.assertEqual(defaults["filename_separator"], "+")

        dummy = OfficialDocsMixin()
        raw = dict(defaults)
        raw["filename_separator"] = " - "
        with patch("gui.main_window.mixins.official_docs_ops.state_ops.set_official_doc_settings"):
            normalized = dummy._normalize_official_doc_settings(raw)

        self.assertEqual(normalized["filename_separator"], " - ")

    def test_settings_snapshot_feeds_process_options_separator(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)

        self.assertIn('filename_separator=str(source.get("filename_separator", "+")', text)
        self.assertIn('filename_separator=str(settings.get("filename_separator", "+")', text)

    def test_default_mode_copy_updates_with_separator(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)

        self.assertIn("def _refresh_official_docs_naming_mode_labels(self) -> None:", text)
        self.assertIn("mode_combo.setItemText(index, default_text)", text)


if __name__ == "__main__":
    unittest.main()
