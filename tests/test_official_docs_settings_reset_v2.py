import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_mixin_source


class OfficialDocsSettingsResetV3Tests(unittest.TestCase):
    def test_defaults_are_version_3(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn('"version": OFFICIAL_DOC_SETTINGS_VERSION', text)

    def test_refresh_resets_and_persists_old_versions(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn('if int((raw or {}).get("version", 0) or 0) != OFFICIAL_DOC_SETTINGS_VERSION:', text)
        self.assertIn("set_official_doc_settings(defaults)", text)


if __name__ == "__main__":
    unittest.main()
