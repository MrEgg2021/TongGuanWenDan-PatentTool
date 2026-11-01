import unittest

from core.formal_review.rule_registry import default_rule_enabled_map, enabled_rule_id_set, normalize_rule_enabled


class FormalReviewRuleEnableConfigTests(unittest.TestCase):
    def test_normalize_rule_enabled_uses_defaults(self) -> None:
        normalized = normalize_rule_enabled({})
        defaults = default_rule_enabled_map()
        self.assertEqual(set(normalized.keys()), set(defaults.keys()))
        self.assertTrue(all(isinstance(value, bool) for value in normalized.values()))

    def test_enabled_rule_id_set_respects_payload(self) -> None:
        defaults = default_rule_enabled_map()
        target_rule = next(iter(defaults.keys()))
        payload = dict(defaults)
        payload[target_rule] = False
        enabled_ids = enabled_rule_id_set(payload)
        self.assertNotIn(target_rule, enabled_ids)
        self.assertGreater(len(enabled_ids), 0)


if __name__ == "__main__":
    unittest.main()
