from __future__ import annotations

from pathlib import Path
import unittest


class OfficialDocsPreviewWiringMaskScopeV251Tests(unittest.TestCase):
    @staticmethod
    def _read(rel_path: str) -> str:
        repo_root = Path(__file__).resolve().parents[1]
        return (repo_root / rel_path).read_text(encoding="utf-8")

    def _read_type_configuration_sources(self) -> str:
        return "\n".join(
            self._read(path)
            for path in (
                "gui/main_window/mixins/official_docs_ops/type_list_ops.py",
                "gui/main_window/mixins/official_docs_ops/type_tree_ops.py",
                "gui/main_window/mixins/official_docs_ops/naming_group_ops.py",
                "gui/main_window/mixins/official_docs_ops/type_card_ops.py",
            )
        )

    def test_detail_preview_uses_masked_preview_name_and_masked_archive_display_path(self) -> None:
        text = self._read("gui/main_window/mixins/official_docs_ops/detail_ops.py")
        self.assertIn(
            'preview_name = str(preview.preview_pdf_name or rendered.output_pdf_name or "").strip()',
            text,
        )
        self.assertIn("archive_rel_dir_preview = str(rendered.archive_rel_dir or \"\").strip()", text)
        self.assertIn("mask_app_no_for_preview(raw_app_no)", text)
        self.assertIn("archive_rel_dir_preview.replace(raw_app_no, masked_app_no)", text)

    def test_settings_preview_line_consumes_preview_name_with_defensive_masking(self) -> None:
        text = self._read_type_configuration_sources()
        self.assertIn('output_name = str(preview.preview_pdf_name or "").strip() or "-"', text)
        self.assertIn(
            "output_name = output_name.replace(raw_app_no, mask_app_no_for_preview(raw_app_no))",
            text,
        )


if __name__ == "__main__":
    unittest.main()
