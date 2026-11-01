import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewClaimMarkerAutosizeStabilityWiringTests(unittest.TestCase):
    def test_marker_height_uses_visual_rect_and_resets_constraints(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn("marker_rect = tree.visualItemRect(marker_item)", text)
        self.assertIn("available_width = int(marker_rect.width() or 0) - _CLAIM_MARKER_HORIZONTAL_PADDING", text)
        self.assertIn("available_width = int(tree.viewport().width() or 0) - _CLAIM_MARKER_HORIZONTAL_PADDING", text)
        self.assertIn("label.setMinimumHeight(0)", text)
        self.assertIn("_WIDGET_SIZE_MAX = 16777215", text)
        self.assertIn("label.setMaximumHeight(_WIDGET_SIZE_MAX)", text)
        self.assertIn("container.setMinimumHeight(0)", text)
        self.assertIn("container.setMaximumHeight(_WIDGET_SIZE_MAX)", text)
        self.assertIn("metrics.boundingRect(0, 0, available_width, 0, int(Qt.TextFlag.TextWordWrap), str(label.text() or \"\"))", text)

    def test_marker_autosize_reacts_to_layout_triggers(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn("claims_tree.itemExpanded.connect(self._schedule_claims_dynamic_layout)", text)
        self.assertIn("claims_tree.itemCollapsed.connect(self._schedule_claims_dynamic_layout)", text)
        self.assertIn("workspace_splitter.splitterMoved.connect(self._on_formal_review_workspace_splitter_moved)", text)
        self.assertIn("self._schedule_claims_dynamic_layout()", text)


if __name__ == "__main__":
    unittest.main()
