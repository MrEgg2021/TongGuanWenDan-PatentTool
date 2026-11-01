from __future__ import annotations

import unittest
from pathlib import Path


class TgdRequestFormTourWiringTests(unittest.TestCase):
    def _read(self, rel_path: str) -> str:
        return Path(rel_path).read_text(encoding="utf-8")

    def test_data_management_page_exposes_common_info_guide_card(self) -> None:
        source = self._read("gui/ui_layout_impl/data_management_page.py")
        self.assertIn('btn_manual = QPushButton("管理常用信息")', source)
        self.assertIn('btn_guide = QPushButton("如何复用到请求书")', source)
        self.assertIn('guide_title = QLabel("这些信息如何在请求书中复用")', source)
        self.assertIn('subtitle = QLabel("集中维护请求书会复用的常用信息，支持批量导入历史案卷包、二次编辑，并可从请求书写回更新。")', source)
        self.assertIn('zip_hint = QLabel("支持批量导入历史案卷包，快速提取申请人、发明人、联系人等常用信息，导入后仍可在本页二次编辑。")', source)
        self.assertIn("window._tgd_dm_maybe_auto_expand_guide", source)

    def test_request_form_footer_keeps_only_writeback_action(self) -> None:
        source = self._read("gui/widgets_impl/request_form/dialog_ui_sections_bottom.py")
        self.assertIn('self.btn_import_to_data_mgmt = QPushButton("保存到常用信息", card)', source)
        self.assertNotIn("btn_request_tour", source)
        self.assertNotIn("新手指引", source)

    def test_request_form_dialog_no_longer_schedules_popup_tour(self) -> None:
        source = self._read("gui/widgets_impl/request_form/dialog_impl/main_dialog_impl/dialog.py")
        self.assertNotIn("btn_request_tour", source)
        self.assertNotIn("show_data_management_request_form_tour", source)

    def test_import_result_dialog_links_back_to_common_info_without_tour(self) -> None:
        source = self._read("gui/widgets_impl/request_form/dialog_impl/import_result_dialog.py")
        self.assertIn('QPushButton("前往常用信息")', source)
        self.assertNotIn("新手指引", source)
        self.assertNotIn("show_data_management_request_form_tour", source)

    def test_request_writeback_copy_uses_clear_language(self) -> None:
        source = self._read("gui/widgets_impl/request_form/fact_import_impl/orchestrator.py")
        self.assertIn("保存到常用信息", source)
        self.assertIn("保存完成", source)
        self.assertIn("确认保存", source)

    def test_navigation_auto_expands_inline_guide_from_data_management(self) -> None:
        source = self._read("gui/main_window/mixins/navigation_mixin_impl.py")
        self.assertIn("_tgd_dm_maybe_auto_expand_guide", source)
        self.assertNotIn("show_data_management_request_form_tour", source)


if __name__ == "__main__":
    unittest.main()
