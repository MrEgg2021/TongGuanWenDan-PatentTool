from __future__ import annotations

import unittest
from pathlib import Path
from tests.official_docs_source_loader import read_official_docs_mixin_source, read_official_docs_page_source


class OfficialDocsSettingsPreviewTitleWiringTests(unittest.TestCase):
    def test_filename_preview_label_is_defined_on_filename_card(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn('title = QLabel("文件名预览：-")', text)
        self.assertIn('window.official_docs_filename_preview_label = filename_preview_label', text)
        self.assertNotIn("OfficialDocsSettingsLinePreview", text)

    def test_preview_update_targets_new_label(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn('label = getattr(self, "official_docs_filename_preview_label", None)', text)
        self.assertIn("render_notice_output_preview(meta=meta, notice_kind=notice_type, options=options)", text)
        self.assertIn('output_name = str(preview.preview_pdf_name or "").strip() or "-"', text)
        self.assertIn('label.setText(f"文件名预览：{output_name}")', text)

    def test_filename_card_does_not_show_list_xml_hint(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertNotIn("OfficialDocsFilenameFieldHint", text)
        self.assertNotIn("通常依赖 list.xml", text)


if __name__ == "__main__":
    unittest.main()
