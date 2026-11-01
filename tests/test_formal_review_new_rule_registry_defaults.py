import unittest

from core.formal_review.rule_registry import RULE_REGISTRY, default_rule_enabled_map, enabled_rule_id_set


class FormalReviewNewRuleRegistryDefaultsTests(unittest.TestCase):
    def test_new_rules_exist_and_default_enabled(self) -> None:
        expected_rule_ids = {
            "text.repeated_word",
            "drawings.figure.ref.missing_in_impl",
            "drawings.figure.ref.duplicate_in_drawings_section",
            "description.drawings.figure.ref.missing_in_drawings_section",
            "drawings.figure.ref.missing_in_description_drawings",
            "description.impl_heading.missing_for_figure_check",
            "description.heading.missing.required",
            "description.title.missing",
            "description.title.length.exceeded",
            "theme.claim1.multi_subject",
            "theme.title_claim1.mismatch",
            "theme.title_abstract.mismatch",
            "theme.title.unrecognized",
            "claim.ref.multi_to_multi.recursive",
            "claim.punctuation.period.extra",
            "claim.punctuation.period.tail_missing",
        }
        defaults = default_rule_enabled_map()
        for rule_id in expected_rule_ids:
            self.assertIn(rule_id, RULE_REGISTRY)
            self.assertIn(rule_id, defaults)
            self.assertTrue(defaults[rule_id], f"{rule_id} should default to enabled")

    def test_new_optional_rules_exist_and_default_disabled(self) -> None:
        expected_disabled_rule_ids = {
            "claim1.word_count.exceeded",
            "claim1.marker_count.exceeded",
            "claim.ref.marker_basis.missing",
            "claim.ref.term_basis.missing",
        }
        defaults = default_rule_enabled_map()
        for rule_id in expected_disabled_rule_ids:
            self.assertIn(rule_id, RULE_REGISTRY)
            self.assertIn(rule_id, defaults)
            self.assertFalse(defaults[rule_id], f"{rule_id} should default to disabled")

    def test_new_rules_are_present_in_enabled_rule_id_set_by_default(self) -> None:
        enabled_ids = enabled_rule_id_set(default_rule_enabled_map())
        self.assertIn("text.repeated_word", enabled_ids)
        self.assertIn("drawings.figure.ref.duplicate_in_drawings_section", enabled_ids)
        self.assertIn("description.title.length.exceeded", enabled_ids)
        self.assertIn("theme.title_abstract.mismatch", enabled_ids)
        self.assertIn("claim.ref.multi_to_multi.recursive", enabled_ids)
        self.assertIn("claim.punctuation.period.extra", enabled_ids)
        self.assertNotIn("claim1.word_count.exceeded", enabled_ids)
        self.assertNotIn("claim1.marker_count.exceeded", enabled_ids)
        self.assertNotIn("claim.ref.marker_basis.missing", enabled_ids)
        self.assertNotIn("claim.ref.term_basis.missing", enabled_ids)


if __name__ == "__main__":
    unittest.main()
