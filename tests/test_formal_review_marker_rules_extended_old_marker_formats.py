import unittest

from core.formal_review.marker_rules import _detect_marker_action


class FormalReviewMarkerRulesExtendedOldMarkerFormatsTests(unittest.TestCase):
    def test_claim_hyphen_marker_is_replaced(self) -> None:
        status, old_fragment, replacement = _detect_marker_action("claims", "（5-1）连接。", "5/1")
        self.assertEqual(status, "replace")
        self.assertEqual(old_fragment, "（5-1）")
        self.assertEqual(replacement, "（5/1）")

    def test_claim_comma_marker_is_replaced(self) -> None:
        status, old_fragment, replacement = _detect_marker_action("claims", "（5，1）连接。", "5/1")
        self.assertEqual(status, "replace")
        self.assertEqual(old_fragment, "（5，1）")
        self.assertEqual(replacement, "（5/1）")

    def test_claim_dunhao_marker_is_replaced(self) -> None:
        status, old_fragment, replacement = _detect_marker_action("claims", "（5、1）连接。", "5/1")
        self.assertEqual(status, "replace")
        self.assertEqual(old_fragment, "（5、1）")
        self.assertEqual(replacement, "（5/1）")

    def test_claim_square_bracket_marker_is_replaced(self) -> None:
        status, old_fragment, replacement = _detect_marker_action("claims", "[5]连接。", "5")
        self.assertEqual(status, "replace")
        self.assertEqual(old_fragment, "[5]")
        self.assertEqual(replacement, "（5）")

    def test_claim_fullwidth_square_bracket_marker_is_replaced(self) -> None:
        status, old_fragment, replacement = _detect_marker_action("claims", "【5】连接。", "5")
        self.assertEqual(status, "replace")
        self.assertEqual(old_fragment, "【5】")
        self.assertEqual(replacement, "（5）")

    def test_claim_bare_number_marker_is_replaced(self) -> None:
        status, old_fragment, replacement = _detect_marker_action("claims", "56连接。", "5")
        self.assertEqual(status, "replace")
        self.assertEqual(old_fragment, "56")
        self.assertEqual(replacement, "（5）")

    def test_claim_fullwidth_bare_number_marker_is_replaced(self) -> None:
        status, old_fragment, replacement = _detect_marker_action("claims", "５６连接。", "5")
        self.assertEqual(status, "replace")
        self.assertEqual(old_fragment, "５６")
        self.assertEqual(replacement, "（5）")

    def test_description_fullwidth_space_and_em_dash_marker_is_replaced(self) -> None:
        status, old_fragment, replacement = _detect_marker_action("description", "5　—　1连接。", "5/1")
        self.assertEqual(status, "replace")
        self.assertEqual(old_fragment, "5　—　1")
        self.assertEqual(replacement, "5/1")

    def test_exact_target_format_still_treated_as_correct(self) -> None:
        status, old_fragment, replacement = _detect_marker_action("claims", "（5/1）连接。", "5/1")
        self.assertEqual(status, "correct")
        self.assertEqual(old_fragment, "（5/1）")
        self.assertEqual(replacement, "（5/1）")


if __name__ == "__main__":
    unittest.main()
