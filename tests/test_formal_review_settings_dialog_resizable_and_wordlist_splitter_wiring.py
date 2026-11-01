import unittest

from core.formal_review.wordlists import DEFAULT_WORDLISTS_V2, SLIM_DEFAULT_PROFILE_NAME
from gui.widgets_impl.formal_review.settings_dialog_parts.wordlist_tab import WordlistTabMixin
from tests.formal_review_settings_dialog_source_loader import load_formal_review_settings_dialog_source


class _WordlistPresetSwitchDummy(WordlistTabMixin):
    def __init__(self) -> None:
        self._profiles = {SLIM_DEFAULT_PROFILE_NAME: DEFAULT_WORDLISTS_V2}
        self._active_profile = "自定义"
        self.refreshed: list[str] = []
        self.switched: list[str] = []
        self.stored = False

    def _store_current_profile_edits(self) -> None:
        self.stored = True

    def _refresh_profile_combo(self, *, select_name: str | None = None) -> None:
        self.refreshed.append(str(select_name or ""))

    def _switch_to_profile(self, name: str) -> None:
        self.switched.append(str(name or ""))
        self._active_profile = str(name or "")


class FormalReviewSettingsDialogResizableAndWordlistSplitterWiringTests(unittest.TestCase):
    def test_dialog_is_resizable(self) -> None:
        source = load_formal_review_settings_dialog_source()
        self.assertIn("self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)", source)
        self.assertIn("self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)", source)
        self.assertIn("self.setSizeGripEnabled(True)", source)
        self.assertIn("self.setMinimumSize(860, 620)", source)
        self.assertIn("self.resize(980, 700)", source)

    def test_wordlist_tab_uses_compact_two_by_two_splitter_layout(self) -> None:
        source = load_formal_review_settings_dialog_source()
        self.assertIn("top_splitter = QSplitter(Qt.Horizontal)", source)
        self.assertIn("bottom_splitter = QSplitter(Qt.Horizontal)", source)
        self.assertIn("wordlist_splitter = QSplitter(Qt.Vertical)", source)
        self.assertIn("top_splitter.setChildrenCollapsible(False)", source)
        self.assertIn("bottom_splitter.setChildrenCollapsible(False)", source)
        self.assertIn("wordlist_splitter.setChildrenCollapsible(False)", source)
        self.assertIn(
            "top_splitter.addWidget(_build_wordlist_column(\"权利要求禁用词库\", \"禁用词\", \"_claims_forbidden_edit\"))",
            source,
        )
        self.assertIn(
            "top_splitter.addWidget(_build_wordlist_column(\"权利要求敏感词库\", \"敏感词\", \"_claims_sensitive_edit\"))",
            source,
        )
        self.assertIn(
            "bottom_splitter.addWidget(_build_wordlist_column(\"说明书禁用词库\", \"禁用词\", \"_description_forbidden_edit\"))",
            source,
        )
        self.assertIn(
            "bottom_splitter.addWidget(_build_wordlist_column(\"说明书敏感词库\", \"敏感词\", \"_description_sensitive_edit\"))",
            source,
        )
        self.assertIn("layout.addWidget(wordlist_splitter, 1)", source)

    def test_wordlist_tab_exposes_preset_guidance_and_counts(self) -> None:
        source = load_formal_review_settings_dialog_source()
        self.assertIn("当前词库会直接影响形式审查命中", source)
        self.assertIn('btn_slim = QPushButton("使用精简默认")', source)
        self.assertIn('btn_full = QPushButton("使用严格预设")', source)
        self.assertIn("_refresh_wordlist_count_labels", source)
        self.assertIn("每行一个，当前", source)

    def test_builtin_profile_button_refreshes_combo_even_when_profile_exists(self) -> None:
        dummy = _WordlistPresetSwitchDummy()
        dummy._on_use_builtin_profile(SLIM_DEFAULT_PROFILE_NAME, DEFAULT_WORDLISTS_V2)
        self.assertTrue(dummy.stored)
        self.assertEqual([SLIM_DEFAULT_PROFILE_NAME], dummy.refreshed)
        self.assertEqual([SLIM_DEFAULT_PROFILE_NAME], dummy.switched)


if __name__ == "__main__":
    unittest.main()
