import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_mixin_source


class OfficialDocsNamingAliasSplitterPersistenceWiringTests(unittest.TestCase):
    def test_splitter_preference_key_is_normalized(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn('NAMING_ALIAS_SPLITTER_KEY = "naming_alias_splitter_sizes_v1"', text)
        self.assertIn("NAMING_ALIAS_SPLITTER_DEFAULT = [3, 2]", text)
        self.assertIn(
            "splitter_sizes = _normalize_naming_alias_splitter_sizes(raw.get(NAMING_ALIAS_SPLITTER_KEY))",
            text,
        )
        self.assertIn("normalized[NAMING_ALIAS_SPLITTER_KEY] = splitter_sizes", text)

    def test_splitter_move_uses_debounce_and_persists_without_save_button(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn("timer.setSingleShot(True)", text)
        self.assertIn("timer.timeout.connect(self._persist_official_docs_naming_splitter_sizes)", text)
        self.assertIn("def on_official_docs_naming_splitter_moved(", text)
        self.assertIn("timer.start(250)", text)
        self.assertIn("def _persist_official_docs_naming_splitter_sizes(", text)
        self.assertIn("set_official_doc_settings(persisted)", text)
        self.assertIn("self._apply_official_docs_naming_splitter_sizes(settings.get(NAMING_ALIAS_SPLITTER_KEY))", text)


if __name__ == "__main__":
    unittest.main()
