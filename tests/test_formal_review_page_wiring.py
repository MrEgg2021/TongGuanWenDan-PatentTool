import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_page_source


class FormalReviewPageWiringTests(unittest.TestCase):
    def test_page_contains_workspace_splitter_and_center_panel_binding(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_page_source(repo_root)
        self.assertIn('workspace_splitter.setObjectName("FormalReviewWorkspaceSplitter")', text)
        self.assertIn("window.formal_review_workspace_splitter = workspace_splitter", text)
        self.assertIn("window.formal_review_plain_center_panel = center_panel", text)
        self.assertIn("window.formal_review_center_panel_attached = True", text)
        self.assertIn("window.formal_review_results_tree = results_tree", text)
        self.assertIn("window.formal_review_issue_context_before = context_before", text)
        self.assertIn("window.formal_review_issue_context_hit = context_hit", text)
        self.assertIn("window.formal_review_issue_context_after = context_after", text)
        self.assertIn("window.formal_review_claim_metrics_table = claims_table", text)

    def test_page_wires_issue_navigation_and_workspace_toggle_handlers(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_page_source(repo_root)
        self.assertIn("results_tree.itemClicked.connect(window.on_formal_review_summary_item_clicked)", text)
        self.assertIn("table.cellClicked.connect(window.on_formal_review_issue_table_cell_clicked)", text)
        self.assertIn("marker_apply_btn.clicked.connect(window.on_formal_review_apply_marker_revision_direct)", text)
        self.assertNotIn('btn_toggle_left.clicked.connect(lambda: window.on_formal_review_toggle_workspace_panel("left"))', text)
        self.assertNotIn('btn_toggle_right.clicked.connect(lambda: window.on_formal_review_toggle_workspace_panel("right"))', text)


if __name__ == "__main__":
    unittest.main()
