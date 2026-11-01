import unittest

from core.formal_review.rule_registry import rule_items_for_ui


class FormalReviewRuleRegistryUiMetaTests(unittest.TestCase):
    def test_rule_items_include_ui_domain_and_ui_level(self) -> None:
        rows = list(rule_items_for_ui())
        self.assertGreater(len(rows), 0)
        sample = rows[0]
        self.assertIn("ui_domain", sample)
        self.assertIn("ui_level", sample)
        self.assertIn("category", sample)
        self.assertIn("severity", sample)

    def test_expected_domain_and_level_mappings(self) -> None:
        rows = {str(item["rule_id"]): item for item in rule_items_for_ui()}
        self.assertEqual(rows["abstract.word_count.exceeded"]["ui_domain"], "abstract")
        self.assertEqual(rows["abstract.word_count.exceeded"]["ui_level"], "forbid")
        self.assertEqual(rows["claim.ref.missing_target"]["ui_domain"], "claims")
        self.assertEqual(rows["claim.ref.missing_target"]["ui_level"], "forbid")
        self.assertEqual(rows["claim.ref.self"]["ui_level"], "warn")
        self.assertEqual(rows["theme.title_claim1.mismatch"]["ui_level"], "remind")
        self.assertEqual(rows["drawings.figure.ref.missing_in_impl"]["ui_domain"], "drawings")
        self.assertEqual(rows["drawings.figure.ref.duplicate_in_drawings_section"]["ui_domain"], "drawings")
        self.assertEqual(rows["drawings.figure.ref.duplicate_in_drawings_section"]["ui_level"], "forbid")
        self.assertEqual(rows["description.drawings.figure.ref.missing_in_drawings_section"]["ui_domain"], "description")
        self.assertEqual(rows["description.drawings.figure.ref.missing_in_drawings_section"]["ui_level"], "forbid")
        self.assertEqual(rows["drawings.figure.ref.missing_in_description_drawings"]["ui_domain"], "description")
        self.assertEqual(rows["drawings.figure.ref.missing_in_description_drawings"]["ui_level"], "forbid")
        self.assertEqual(rows["punctuation.invalid_combo"]["ui_domain"], "general")
        self.assertEqual(rows["claim.number.gap"]["category"], "claims")
        self.assertEqual(rows["claim.number.gap"]["severity"], "error")
        self.assertEqual(rows["claim.language.weak_limitation"]["severity"], "info")


if __name__ == "__main__":
    unittest.main()
