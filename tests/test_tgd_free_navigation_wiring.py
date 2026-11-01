import unittest
from pathlib import Path

try:
    from gui_source_loader import read_navigation_mixin_source
except ModuleNotFoundError:  # pragma: no cover
    from tests.gui_source_loader import read_navigation_mixin_source


class TgdFreeNavigationWiringTests(unittest.TestCase):
    def test_data_management_entry_has_no_trial_prompt_path(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_navigation_mixin_source(repo_root)

        self.assertIn("def _nav_to_data_management", text)
        self.assertNotIn('"START_TRIAL"', text)
        self.assertNotIn("check_feature_gate(FeatureId.TGD_WRITE)", text)


if __name__ == "__main__":
    unittest.main()
