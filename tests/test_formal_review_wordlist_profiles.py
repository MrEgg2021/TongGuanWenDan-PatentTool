import unittest
from unittest.mock import patch

from core.formal_review.wordlists import (
    DEFAULT_WORDLISTS_V2,
    FULL_PRESET_PROFILE_NAME,
    FULL_PRESET_WORDLISTS_V2,
    SLIM_DEFAULT_PROFILE_NAME,
    WORDLIST_PREF_KEY_V2,
    WORDLIST_PREF_KEY_V1,
    WORDLIST_PROFILE_STORE_KEY_V1,
    load_wordlist_profile_store,
    normalize_wordlists,
    set_active_wordlist_profile,
)


class FormalReviewWordlistProfilesTests(unittest.TestCase):
    def _patch_prefs(self, prefs: dict):
        def _get_pref(key: str, default=None):
            return prefs.get(key, default)

        def _set_pref(key: str, value):
            prefs[key] = value

        return patch("core.formal_review.wordlists.get_pref", side_effect=_get_pref), patch(
            "core.formal_review.wordlists.set_pref", side_effect=_set_pref
        )

    def test_migrate_when_store_missing(self) -> None:
        prefs: dict = {}
        p_get, p_set = self._patch_prefs(prefs)
        with p_get, p_set:
            active, profiles = load_wordlist_profile_store()
        self.assertEqual(active, SLIM_DEFAULT_PROFILE_NAME)
        self.assertIn(SLIM_DEFAULT_PROFILE_NAME, profiles)
        self.assertIn(FULL_PRESET_PROFILE_NAME, profiles)
        self.assertEqual(profiles[SLIM_DEFAULT_PROFILE_NAME], DEFAULT_WORDLISTS_V2)
        self.assertEqual(profiles[FULL_PRESET_PROFILE_NAME], FULL_PRESET_WORDLISTS_V2)
        self.assertIn(WORDLIST_PROFILE_STORE_KEY_V1, prefs)
        self.assertIn(WORDLIST_PREF_KEY_V2, prefs)
        self.assertEqual(prefs[WORDLIST_PREF_KEY_V2], profiles[active])

    def test_legacy_v2_snapshot_migrates_without_forcing_slim_default(self) -> None:
        legacy_wordlists = {
            "claims": {"forbidden": ["自定义权要禁用"], "sensitive": []},
            "description": {"forbidden": ["自定义说明书禁用"], "sensitive": []},
        }
        prefs: dict = {WORDLIST_PREF_KEY_V2: legacy_wordlists}
        p_get, p_set = self._patch_prefs(prefs)
        with p_get, p_set:
            active, profiles = load_wordlist_profile_store()
        self.assertEqual(active, "默认")
        self.assertEqual(profiles["默认"], legacy_wordlists)
        self.assertNotEqual(profiles["默认"], DEFAULT_WORDLISTS_V2)

    def test_legacy_v1_snapshot_migrates_without_forcing_slim_default(self) -> None:
        prefs: dict = {WORDLIST_PREF_KEY_V1: {"forbidden": ["旧禁用"], "sensitive": ["旧敏感"]}}
        p_get, p_set = self._patch_prefs(prefs)
        with p_get, p_set:
            active, profiles = load_wordlist_profile_store()
        self.assertEqual(active, "默认")
        self.assertEqual(profiles["默认"]["claims"]["forbidden"], ["旧禁用"])
        self.assertEqual(profiles["默认"]["description"]["sensitive"], ["旧敏感"])

    def test_set_active_updates_mirror(self) -> None:
        prefs: dict = {
            WORDLIST_PROFILE_STORE_KEY_V1: {
                "active": "默认",
                "profiles": {
                    "默认": DEFAULT_WORDLISTS_V2,
                    "化学": {
                        "claims": {"forbidden": ["AAA"], "sensitive": []},
                        "description": {"forbidden": [], "sensitive": []},
                    },
                },
            },
            WORDLIST_PREF_KEY_V2: normalize_wordlists(DEFAULT_WORDLISTS_V2),
        }
        p_get, p_set = self._patch_prefs(prefs)
        with p_get, p_set:
            set_active_wordlist_profile("化学")
        store = prefs[WORDLIST_PROFILE_STORE_KEY_V1]
        self.assertEqual(store["active"], "化学")
        self.assertEqual(prefs[WORDLIST_PREF_KEY_V2], normalize_wordlists(store["profiles"]["化学"]))

if __name__ == "__main__":
    unittest.main()

