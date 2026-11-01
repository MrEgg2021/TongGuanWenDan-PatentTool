import unittest
from pathlib import Path


class FormalReviewOverlayCardWidthAlignmentWiringTests(unittest.TestCase):
    def test_processing_modal_card_width_is_dynamic(self) -> None:
        source = Path("gui/ui_modals.py").read_text(encoding="utf-8")
        self.assertIn("def _resolve_modal_card_width(", source)
        self.assertIn("def _resolve_processing_card_width(parent: QWidget | None) -> int:", source)
        self.assertIn("return _resolve_modal_card_width(parent, preferred=680, min_width=220, max_width=900, safety_margin=48)", source)
        self.assertIn("initial_width = _resolve_processing_card_width(parent)", source)
        self.assertIn("card.setMinimumWidth(initial_width)", source)
        self.assertIn("card.setMaximumWidth(initial_width)", source)
        self.assertNotIn("card.setFixedWidth(460)", source)
        self.assertNotIn("card.setFixedWidth(420)", source)
        self.assertNotIn("card.setFixedWidth(680)", source)

    def test_formal_review_overlay_card_uses_left_panel_width(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/companion_ops.py").read_text(encoding="utf-8")
        self.assertIn("def _fit_formal_review_overlay_card_width(self) -> None:", source)
        self.assertIn("left_panel = getattr(self, \"formal_review_left_panel\", None)", source)
        self.assertIn("owner_width = _widget_width(owner)", source)
        self.assertIn("viewport_cap = max(180, int(owner_width - 24))", source)
        self.assertIn("self._fit_formal_review_overlay_card_width()", source)

    def test_resize_event_recalculates_overlay_card_width(self) -> None:
        source = Path("gui/main_window/mixins/progress_mixin.py").read_text(encoding="utf-8")
        self.assertIn("if hasattr(self, \"_fit_formal_review_overlay_card_width\"):", source)
        self.assertIn("self._fit_formal_review_overlay_card_width()", source)


if __name__ == "__main__":
    unittest.main()
