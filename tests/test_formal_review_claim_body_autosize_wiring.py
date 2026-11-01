import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewClaimBodyAutosizeWiringTests(unittest.TestCase):
    def test_claim_body_autosize_helpers_exist(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn("_CLAIM_BODY_MIN_HEIGHT = 56", text)
        self.assertIn("_CLAIM_BODY_MAX_HEIGHT = 360", text)
        self.assertIn("def _schedule_claims_dynamic_layout(self, *_args) -> None:", text)
        self.assertIn("def _update_claim_body_height(self, editor: QTextEdit) -> None:", text)
        self.assertIn("document.setTextWidth(float(viewport_width))", text)
        self.assertIn("target_height = max(_CLAIM_BODY_MIN_HEIGHT, min(_CLAIM_BODY_MAX_HEIGHT, content_height))", text)
        self.assertIn("needs_scroll = content_height > _CLAIM_BODY_MAX_HEIGHT", text)
        self.assertIn(
            "editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if needs_scroll else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)",
            text,
        )

    def test_claim_body_autosize_reacts_to_layout_changes(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn("claims_tree.itemExpanded.connect(self._schedule_claims_dynamic_layout)", text)
        self.assertIn("claims_tree.itemCollapsed.connect(self._schedule_claims_dynamic_layout)", text)
        self.assertIn("workspace_splitter.splitterMoved.connect(self._on_formal_review_workspace_splitter_moved)", text)
        self.assertIn("content_editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)", text)
        self.assertIn("self._schedule_claims_dynamic_layout()", text)


if __name__ == "__main__":
    unittest.main()
