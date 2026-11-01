from __future__ import annotations

import unittest
from pathlib import Path


class ProcessingOverlayPatentTypeWiringTests(unittest.TestCase):
    def test_processing_modal_has_multiline_patent_type_slot(self) -> None:
        text = Path("gui/ui_modals.py").read_text(encoding="utf-8")
        required = [
            'cfg_patent_type = QLabel("")',
            'cfg_patent_type.setObjectName("processingCfgPatentType")',
            "cfg_patent_type.setWordWrap(True)",
            "cfg_layout.addWidget(cfg_patent_type)",
        ]
        missing = [snippet for snippet in required if snippet not in text]
        self.assertFalse(missing, "Missing processing modal patent type snippets:\n" + "\n".join(missing))
        self.assertNotIn("cfg_row = QHBoxLayout()", text)

    def test_progress_mixin_refreshes_processing_config_box(self) -> None:
        text = Path("gui/main_window/mixins/progress_mixin.py").read_text(encoding="utf-8")
        required = [
            "def _refresh_processing_config_box",
            'overlay.findChild(QLabel, "processingCfgPatentType")',
            "format_processing_patent_type_text",
        ]
        missing = [snippet for snippet in required if snippet not in text]
        self.assertFalse(missing, "Missing progress patent type snippets:\n" + "\n".join(missing))
        self.assertIn("self._refresh_processing_config_box(overlay)", text)

    def test_progress_mixin_hides_patent_type_using_effective_sections(self) -> None:
        text = Path("gui/main_window/mixins/progress_mixin.py").read_text(encoding="utf-8")
        required = [
            "def _should_show_processing_patent_type",
            "_last_single_effective_enabled_sections",
            "_batch_effective_enabled_sections_map",
            "lb_patent_type.clear()",
            "lb_patent_type.setVisible(False)",
        ]
        missing = [snippet for snippet in required if snippet not in text]
        self.assertFalse(missing, "Missing progress patent type hide snippets:\n" + "\n".join(missing))


if __name__ == "__main__":
    unittest.main()
