from __future__ import annotations

import unittest
from pathlib import Path

from gui.main_window.mixins.response_correction_mixin import SUPPORTED_DOCUMENT_SLOTS
from tests.gui_source_loader import read_modern_shell_source, read_navigation_mixin_source


class ResponseCorrectionUiWiringTests(unittest.TestCase):
    def test_sidebar_places_response_correction_between_conversion_and_preview(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_modern_shell_source(repo_root)

        i_domestic = text.find("layout.addWidget(domestic_conversion_container)")
        i_response = text.find("layout.addWidget(response_correction_header)")
        i_response_container = text.find("layout.addWidget(response_correction_container)")
        i_preview = text.find("layout.addWidget(nav_preview)")

        self.assertGreaterEqual(i_domestic, 0)
        self.assertGreaterEqual(i_response, 0)
        self.assertGreaterEqual(i_response_container, 0)
        self.assertGreaterEqual(i_preview, 0)
        self.assertLess(i_domestic, i_response)
        self.assertLess(i_response, i_response_container)
        self.assertLess(i_response_container, i_preview)

    def test_navigation_registers_response_correction_gate_and_page(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_navigation_mixin_source(repo_root)

        self.assertIn('"response": getattr(shell, "nav_response", None)', text)
        self.assertIn('"correction": getattr(shell, "nav_correction", None)', text)
        self.assertIn('"active_response": getattr(shell, "nav_active_response", None)', text)
        self.assertIn('"active_correction": getattr(shell, "nav_active_correction", None)', text)
        self.assertIn("def _show_response_page", text)
        self.assertIn("def _show_correction_page", text)
        self.assertIn("def _show_active_response_page", text)
        self.assertIn("def _show_active_correction_page", text)

    def test_about_page_confirms_dirty_state_before_hiding_current_pages(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_navigation_mixin_source(repo_root)
        start = text.index("def show_about_page")
        end = text.index("def _nav_to_settings", start)
        snippet = text[start:end]

        self.assertLess(
            snippet.index("_confirm_leave_settings_before_navigation"),
            snippet.index("_hide_response_correction_page"),
        )

    def test_response_correction_generation_uses_worker_thread(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = (repo_root / "gui/main_window/mixins/response_correction_mixin.py").read_text(encoding="utf-8")

        self.assertIn("QThread", text)
        self.assertIn("_ResponseCorrectionWorker", text)
        self.assertIn("_response_correction_worker_thread", text)
        self.assertIn("_start_response_correction_worker", text)

    def test_response_correction_page_has_collapsible_notice_and_single_materials_table_ui(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = (repo_root / "gui/ui_layout_impl/response_correction_page.py").read_text(encoding="utf-8")

        self.assertIn("SingleFileDropWidget", text)
        self.assertIn("notice_section_toggle", text)
        self.assertIn("notice_section_body", text)
        self.assertIn("materials_table", text)
        self.assertIn("processing_pane", text)
        self.assertIn("processing_handle", text)
        self.assertIn('setFixedHeight(160)', text)
        self.assertIn('["原文件名", "操作", "建议映射", "当前映射", "上传状态", "上传时间", "处理结果"]', text)
        self.assertNotIn("来源类型", text)
        self.assertIn("setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)", text)
        self.assertIn("上传状态", text)
        self.assertIn("上传时间", text)
        self.assertIn("confirm_imports_btn", text)
        self.assertIn("browse_import_files", text)
        self.assertIn("browse_import_folder", text)
        self.assertIn('setObjectName("RunButton")', text)
        self.assertIn('setProperty("class", "Primary")', text)

    def test_response_correction_mixin_uses_staged_import_confirmation_and_preprocessing(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = (repo_root / "gui/main_window/mixins/response_correction_mixin.py").read_text(encoding="utf-8")

        self.assertIn("StagedImportItem", text)
        self.assertIn("_confirm_staged_imports_for_flow", text)
        self.assertIn("progress_callback", text)
        self.assertIn("_refresh_materials_table", text)
        self.assertIn("_ingest_import_paths_for_flow", text)
        self.assertIn("_set_notice_section_expanded", text)
        self.assertIn("unsupported_material_reason", text)
        self.assertIn("打开文件所在目录", text)
        self.assertIn("reveal_path_in_explorer", text)

    def test_response_correction_static_slot_constants_match_core_contract(self) -> None:
        mixin_slots = dict(SUPPORTED_DOCUMENT_SLOTS)

        self.assertEqual(mixin_slots["100003"], "说明书附图")
        self.assertEqual(mixin_slots["100004"], "说明书摘要")


if __name__ == "__main__":
    unittest.main()
