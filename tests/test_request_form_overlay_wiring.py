from __future__ import annotations

import unittest
from pathlib import Path


class RequestFormOverlayWiringTests(unittest.TestCase):
    def test_request_form_dialog_uses_overlay_controller_for_non_embedded_exec(self) -> None:
        source = Path(
            "gui/widgets_impl/request_form/dialog_impl/main_dialog_impl/dialog.py"
        ).read_text(encoding="utf-8")
        self.assertIn("from gui.windowing import overlay_controller as overlay_controller_api", source)
        self.assertIn("overlay_controller_api.attach(self._overlay_name, self, self._overlay_owner)", source)
        self.assertIn("overlay_controller_api.set_modal_active(True)", source)

    def test_request_form_dialog_finish_performs_paired_modal_cleanup(self) -> None:
        source = Path(
            "gui/widgets_impl/request_form/dialog_impl/main_dialog_impl/dialog.py"
        ).read_text(encoding="utf-8")
        self.assertIn("if bool(getattr(self, \"_overlay_modal_active\", False)):", source)
        self.assertIn("overlay_controller_api.set_modal_active(False)", source)
        self.assertIn("overlay_controller_api.detach(name)", source)


if __name__ == "__main__":
    unittest.main()
