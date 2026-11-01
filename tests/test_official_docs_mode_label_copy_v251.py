from __future__ import annotations

from pathlib import Path
import unittest


class OfficialDocsModeLabelCopyV251Tests(unittest.TestCase):
    def test_default_mode_label_includes_invention_name(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = (repo_root / "gui/ui_layout_impl/official_docs_page_parts/settings_panel.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'mode_combo.addItem("默认（专利类型+发明名称+申请号+通知书名称+发文日）", "default")',
            text,
        )


if __name__ == "__main__":
    unittest.main()
