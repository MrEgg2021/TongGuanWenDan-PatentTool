import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewHighlightScopeWiringTests(unittest.TestCase):
    def test_apply_highlights_signature_carries_editor_scope(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn("def _apply_highlights(", text)
        self.assertIn("section: str", text)
        self.assertIn("claim_num: int | None = None", text)

    def test_selected_overlay_checks_issue_editor_scope(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn("_issue_matches_editor(selected_issue, section=section, claim_num=claim_num)", text)

    def test_refresh_highlights_passes_section_and_claim_num(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn('section="claims"', text)
        self.assertIn('section="description"', text)
        self.assertIn('section="abstract"', text)
        self.assertIn('section="drawings"', text)
        self.assertIn("claim_num=int(claim_num)", text)

    def test_issues_for_editor_uses_same_scope_helper(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn("if not _issue_matches_editor(issue, section=section, claim_num=claim_num):", text)


if __name__ == "__main__":
    unittest.main()
