from __future__ import annotations

import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_mixin_source, read_official_docs_page_source


class OfficialDocsDetailWrapWiringTests(unittest.TestCase):
    def test_detail_preview_label_enables_wrap(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn("one_line_preview.setWordWrap(True)", text)

    def test_mixin_uses_multiline_text_for_detail_and_preview(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn(
            "preview = render_notice_output_preview(meta=parsed.meta, notice_kind=parsed.notice_kind, options=options)",
            text,
        )
        self.assertIn('meta_label.setText("\\n".join(meta_lines))', text)
        self.assertIn('return "\\n".join(preview_parts), error_text', text)
        self.assertIn('return "\\n".join(result_parts + ["", *preview_parts]), error_text', text)
        self.assertIn("preview_label.setText(preview_text)", text)
        self.assertNotIn('meta_label.setText(" | ".join(meta_lines))', text)
        self.assertNotIn('preview_label.setText(" | ".join(preview_parts))', text)


if __name__ == "__main__":
    unittest.main()
