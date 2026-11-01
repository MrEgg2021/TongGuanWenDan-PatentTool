import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_mixin_source
from gui_source_loader import read_navigation_mixin_source

class FormalReviewGateWiringStaticTests(unittest.TestCase):

    def test_formal_review_entry_calls_workspace_state_hook(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        nav_text = read_navigation_mixin_source(repo_root)
        mixin_text = read_formal_review_mixin_source(repo_root)
        self.assertIn('getattr(self, "_apply_formal_review_entry_window_state", None)', nav_text)
        self.assertIn('def _apply_formal_review_entry_window_state(self)', mixin_text)
        self.assertIn('get_formal_review_auto_maximize', mixin_text)
        self.assertIn('if auto_maximize:', mixin_text)
if __name__ == '__main__':
    unittest.main()
