import unittest
from pathlib import Path


class FormalReviewStateOpsModeSyncGuardWiringTests(unittest.TestCase):
    def test_ensure_state_only_initializes_mode_defaults(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/state_ops.py").read_text(encoding="utf-8")
        self.assertIn("def _ensure_formal_review_state(self) -> None:", source)
        self.assertIn('if not hasattr(self, "_formal_review_input_mode"):', source)
        self.assertIn('self._formal_review_input_mode = "word"', source)
        self.assertIn('if not hasattr(self, "_formal_review_companion_submode"):', source)
        self.assertIn('self._formal_review_companion_submode = "review"', source)

    def test_ensure_state_no_longer_overwrites_mode_every_call(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/state_ops.py").read_text(encoding="utf-8")
        self.assertNotIn('self._formal_review_input_mode = "plain_text" if', source)
        self.assertNotIn('self._formal_review_companion_submode = "apply" if', source)


if __name__ == "__main__":
    unittest.main()
