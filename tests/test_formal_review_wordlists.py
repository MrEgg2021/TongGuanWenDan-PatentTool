import unittest
from unittest.mock import patch

from core.formal_review.wordlists import (
    DEFAULT_WORDLISTS_V2,
    FULL_PRESET_PROFILE_NAME,
    FULL_PRESET_WORDLISTS_V2,
    SLIM_DEFAULT_PROFILE_NAME,
    WORDLIST_PREF_KEY_V1,
    WORDLIST_PREF_KEY_V2,
    WORDLIST_PROFILE_STORE_KEY_V1,
    load_wordlists,
    normalize_wordlists,
    save_wordlists,
)


class FormalReviewWordlistsTests(unittest.TestCase):
    def test_load_uses_defaults_when_missing(self) -> None:
        def _fake_get_pref(key: str, default=None):
            if key == WORDLIST_PROFILE_STORE_KEY_V1:
                return None
            if key == WORDLIST_PREF_KEY_V2:
                return None
            if key == WORDLIST_PREF_KEY_V1:
                return {}
            return default

        with patch("core.formal_review.wordlists.get_pref", side_effect=_fake_get_pref), patch(
            "core.formal_review.wordlists.set_pref"
        ):
            data = load_wordlists()
        self.assertEqual(data["claims"]["forbidden"], [])
        self.assertEqual(data["claims"]["sensitive"], [])
        self.assertEqual(
            data["description"]["forbidden"],
            ["其特征在于", "其特征是", "其特征为", "如权利要求", "根据权利要求", "权利要求书"],
        )
        self.assertEqual(data["description"]["sensitive"], [])

    def test_new_user_profile_store_contains_slim_and_strict_presets(self) -> None:
        prefs: dict = {}

        def _fake_get_pref(key: str, default=None):
            return prefs.get(key, default)

        def _fake_set_pref(key: str, value):
            prefs[key] = value

        with patch("core.formal_review.wordlists.get_pref", side_effect=_fake_get_pref), patch(
            "core.formal_review.wordlists.set_pref", side_effect=_fake_set_pref
        ):
            data = load_wordlists()
        store = prefs[WORDLIST_PROFILE_STORE_KEY_V1]
        self.assertEqual(store["active"], SLIM_DEFAULT_PROFILE_NAME)
        self.assertEqual(data, DEFAULT_WORDLISTS_V2)
        self.assertEqual(store["profiles"][SLIM_DEFAULT_PROFILE_NAME], DEFAULT_WORDLISTS_V2)
        self.assertEqual(store["profiles"][FULL_PRESET_PROFILE_NAME], FULL_PRESET_WORDLISTS_V2)

    def test_save_normalizes_and_persists_v2(self) -> None:
        store = {"active": "默认", "profiles": {"默认": DEFAULT_WORDLISTS_V2}}

        def _fake_get_pref(key: str, default=None):
            if key == WORDLIST_PROFILE_STORE_KEY_V1:
                return store
            if key == WORDLIST_PREF_KEY_V2:
                return DEFAULT_WORDLISTS_V2
            if key == WORDLIST_PREF_KEY_V1:
                return {}
            return default

        with patch("core.formal_review.wordlists.get_pref", side_effect=_fake_get_pref), patch(
            "core.formal_review.wordlists.set_pref"
        ) as mocked_set:
            payload = save_wordlists(
                {
                    "claims": {"forbidden": [" 绝对 ", "绝对"], "sensitive": ["可能"]},
                    "description": {"forbidden": [" 权利要求 ", "权利要求"], "sensitive": ["例如"]},
                }
            )
        self.assertEqual(payload["claims"]["forbidden"], ["绝对"])
        self.assertEqual(payload["claims"]["sensitive"], ["可能"])
        self.assertEqual(payload["description"]["forbidden"], ["权利要求"])
        self.assertEqual(payload["description"]["sensitive"], ["例如"])
        self.assertGreaterEqual(mocked_set.call_count, 1)

    def test_explicit_empty_v2_lists_are_not_refilled_with_defaults(self) -> None:
        payload = normalize_wordlists(
            {
                "claims": {"forbidden": [], "sensitive": []},
                "description": {"forbidden": [], "sensitive": []},
            }
        )
        self.assertEqual(payload["claims"]["forbidden"], [])
        self.assertEqual(payload["claims"]["sensitive"], [])
        self.assertEqual(payload["description"]["forbidden"], [])
        self.assertEqual(payload["description"]["sensitive"], [])

    def test_explicit_empty_legacy_v1_lists_are_not_refilled_with_defaults(self) -> None:
        payload = normalize_wordlists({"forbidden": [], "sensitive": []})
        self.assertEqual(payload["claims"]["forbidden"], [])
        self.assertEqual(payload["claims"]["sensitive"], [])
        self.assertEqual(payload["description"]["forbidden"], [])
        self.assertEqual(payload["description"]["sensitive"], [])

    def test_normalize_migrates_v1_to_v2(self) -> None:
        payload = normalize_wordlists({"forbidden": ["绝对"], "sensitive": ["可能"]})
        self.assertEqual(payload["claims"]["forbidden"], ["绝对"])
        self.assertEqual(payload["description"]["forbidden"], ["绝对"])
        self.assertEqual(payload["claims"]["sensitive"], ["可能"])
        self.assertEqual(payload["description"]["sensitive"], ["可能"])


if __name__ == "__main__":
    unittest.main()
