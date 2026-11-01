import unittest
from unittest.mock import patch

from core.formal_review.rule_params import (
    RULE_PARAMS_PREF_KEY,
    default_rule_params,
    load_rule_params,
    merged_refer_words,
    normalize_rule_params,
    save_rule_params,
)


class FormalReviewRuleParamsConfigTests(unittest.TestCase):
    def _patch_prefs(self, prefs: dict):
        def _get_pref(key: str, default=None):
            return prefs.get(key, default)

        def _set_pref(key: str, value):
            prefs[key] = value

        return patch("core.formal_review.rule_params.get_pref", side_effect=_get_pref), patch(
            "core.formal_review.rule_params.set_pref", side_effect=_set_pref
        )

    def test_default_values(self) -> None:
        params = default_rule_params()
        self.assertEqual(500, int(params["claim1_word_limit"]))
        self.assertEqual(20, int(params["claim1_marker_limit"]))
        self.assertEqual([], list(params["refer_words_extra"]))

    def test_normalize_invalid_payload(self) -> None:
        params = normalize_rule_params(
            {
                "claim1_word_limit": "0",
                "claim1_marker_limit": "abc",
                "refer_words_extra": ["  ", "TermA", "terma", "TermB"],
            }
        )
        self.assertEqual(500, int(params["claim1_word_limit"]))
        self.assertEqual(20, int(params["claim1_marker_limit"]))
        self.assertEqual(["TermA", "TermB"], list(params["refer_words_extra"]))

    def test_load_rule_params_normalizes_and_persists(self) -> None:
        prefs: dict = {RULE_PARAMS_PREF_KEY: {"claim1_word_limit": -1, "claim1_marker_limit": 0, "refer_words_extra": "A\nA\nB"}}
        p_get, p_set = self._patch_prefs(prefs)
        with p_get, p_set:
            params = load_rule_params()
        self.assertEqual(500, int(params["claim1_word_limit"]))
        self.assertEqual(20, int(params["claim1_marker_limit"]))
        self.assertEqual(["A", "B"], list(params["refer_words_extra"]))
        self.assertEqual(params, prefs[RULE_PARAMS_PREF_KEY])

    def test_save_rule_params_caps_limit_and_returns_normalized(self) -> None:
        prefs: dict = {}
        p_get, p_set = self._patch_prefs(prefs)
        with p_get, p_set:
            params = save_rule_params(
                {
                    "claim1_word_limit": 9999999,
                    "claim1_marker_limit": 9999999,
                    "refer_words_extra": ["Alpha", "alpha"],
                }
            )
        self.assertEqual(100000, int(params["claim1_word_limit"]))
        self.assertEqual(100000, int(params["claim1_marker_limit"]))
        self.assertEqual(["Alpha"], list(params["refer_words_extra"]))
        self.assertEqual(params, prefs[RULE_PARAMS_PREF_KEY])

    def test_merged_refer_words_includes_user_extra_without_duplicates(self) -> None:
        merged = merged_refer_words({"refer_words_extra": ["Alpha", "alpha", "Beta"]})
        self.assertIn("Alpha", merged)
        self.assertIn("Beta", merged)
        self.assertEqual(1, sum(1 for item in merged if str(item).casefold() == "alpha"))


if __name__ == "__main__":
    unittest.main()
