import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewClaimMarkerVisibilityWiringTests(unittest.TestCase):
    def test_marker_block_is_wrapped_and_has_dynamic_height_guard(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        mixin_text = read_formal_review_mixin_source(repo_root)
        self.assertIn("def _update_claim_marker_height(self, tree, row: dict[str, object]) -> None:", mixin_text)
        self.assertIn("marker_rect = tree.visualItemRect(marker_item)", mixin_text)
        self.assertIn("label.setMaximumHeight(_WIDGET_SIZE_MAX)", mixin_text)
        self.assertIn("container.setMaximumHeight(_WIDGET_SIZE_MAX)", mixin_text)
        self.assertIn("label.setFixedHeight(target_height)", mixin_text)
        self.assertIn("container.setFixedHeight(target_height)", mixin_text)
        self.assertIn("QFontMetrics(label.font())", mixin_text)
        self.assertIn('marker_label.setObjectName("FormalReviewClaimMarkerLabel")', mixin_text)
        self.assertIn("marker_label.setWordWrap(True)", mixin_text)
        self.assertIn("marker_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)", mixin_text)
        self.assertIn("self._formal_review_claim_marker_rows[claim_num] = {", mixin_text)

    def test_marker_block_style_uses_visible_card_and_spacing(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        qss_text = (repo_root / "gui/ui_layout_impl/theme.qss").read_text(encoding="utf-8")
        self.assertIn("QLabel#FormalReviewClaimMarkerLabel {", qss_text)
        self.assertIn("margin: 2px 0 4px 0;", qss_text)
        self.assertIn("min-height: 24px;", qss_text)
        self.assertIn("background-color: #EEF6FF;", qss_text)


if __name__ == "__main__":
    unittest.main()
