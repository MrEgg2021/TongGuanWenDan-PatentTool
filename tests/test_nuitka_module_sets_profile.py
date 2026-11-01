from __future__ import annotations

import json
import unittest
from pathlib import Path


class NuitkaModuleSetsProfileTests(unittest.TestCase):
    def test_full_core_profile_contains_required_patterns(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        cfg_path = repo_root / "tools" / "nuitka_module_sets.json"
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))

        self.assertIn("full_core", raw)
        profile = raw["full_core"]
        self.assertIsInstance(profile, dict)

        includes = set(profile.get("include", []))
        required = {
            "core/logging_utils.py",
            "core/app_preferences.py",
            "core/tgd_data_management_impl/**/*.py",
            "core/official_docs/**/*.py",
            "core/formal_review/**/*.py",
            "core/document_parser/**/*.py",
            "core/conversion.py",
            "core/xml_generator.py",
            "core/word_engine.py",
            "core/word_engine_impl/**/*.py",
            "core/img_processor.py",
        }
        missing = sorted(required.difference(includes))
        self.assertFalse(missing, "missing required full_core include patterns: " + ", ".join(missing))
        self.assertNotIn("licensing/issuer/license_v2_issuer.py", includes)
        self.assertNotIn("licensing/issuer/issuer_settings.py", includes)



if __name__ == "__main__":
    unittest.main()
