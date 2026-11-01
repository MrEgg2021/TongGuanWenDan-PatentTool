import unittest
from pathlib import Path


class BatchSplitterHeightPolicyNoConflictTests(unittest.TestCase):
    def test_batch_height_policy_skips_fixed_max_height_when_splitter_exists(self) -> None:
        source = Path("gui/app_impl/mode.py").read_text(encoding="utf-8")
        self.assertIn('if getattr(window, "batch_main_splitter", None) is not None:', source)
        self.assertIn("window.file_list_widget.setMaximumHeight(16777215)", source)
        self.assertIn("window.file_list_widget.setMinimumHeight(70)", source)


if __name__ == "__main__":
    unittest.main()
