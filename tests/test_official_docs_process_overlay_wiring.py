from __future__ import annotations

import unittest
from pathlib import Path

from official_docs_source_loader import read_official_docs_mixin_source


class OfficialDocsProcessOverlayWiringTests(unittest.TestCase):
    def test_official_docs_process_uses_overlay_and_progress_callback(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn('self._show_processing_overlay(overlay_status, overlay_file)', text)
        self.assertIn('progress_cb=_progress_cb', text)
        self.assertIn('self._update_processing_overlay(percent, primary, detail)', text)
        self.assertIn('ui_pump_api.pump(allow_user_input=False)', text)
        self.assertIn('self._hide_processing_overlay()', text)

    def test_official_docs_process_hides_cancel_button(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn('cancel_button = overlay.findChild(QPushButton, "processingCancelButton")', text)
        self.assertIn('cancel_button.setVisible(False)', text)


if __name__ == "__main__":
    unittest.main()
