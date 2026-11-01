import json
import os
import tempfile
import unittest
from unittest.mock import patch

from core.app_preferences import DESC_PARA_SPLIT_MODE_KEY, get_desc_para_split_mode
from core.user_prefs import set_pref


class DescSplitModePrefsTests(unittest.TestCase):
    def test_word_period_end_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with patch("core.user_prefs.get_user_data_dir", return_value=td):
                set_pref(DESC_PARA_SPLIT_MODE_KEY, "word_period_end")
                self.assertEqual(get_desc_para_split_mode(), "word_period_end")

                prefs_path = os.path.join(td, "user_prefs.json")
                with open(prefs_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.assertEqual(data.get("desc_para_split_mode"), "word_period_end")


if __name__ == "__main__":
    unittest.main()
