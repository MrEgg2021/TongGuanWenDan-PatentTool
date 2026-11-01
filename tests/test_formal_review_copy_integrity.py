import unittest
from pathlib import Path


class FormalReviewCopyIntegrityTests(unittest.TestCase):
    def test_no_placeholder_or_mojibake_copy(self) -> None:
        targets = [
            Path("gui/main_window/mixins/formal_review_mixin.py"),
            Path("gui/main_window/mixins/formal_review_ops/mixin_impl.py"),
            Path("gui/main_window/mixins/formal_review_ops/shared.py"),
            Path("gui/main_window/mixins/formal_review_ops/state_ops.py"),
            Path("gui/main_window/mixins/formal_review_ops/workspace_ops.py"),
            Path("gui/main_window/mixins/formal_review_ops/edit_ops.py"),
            Path("gui/main_window/mixins/formal_review_ops/issue_view_ops.py"),
            Path("gui/main_window/mixins/formal_review_ops/companion_ops.py"),
            Path("gui/main_window/mixins/formal_review_ops/marker_ops.py"),
            Path("gui/main_window/mixins/formal_review_ops/settings_export_ops.py"),
            Path("gui/main_window/mixins/formal_review_ops/interaction_ops.py"),
            Path("gui/ui_layout_impl/formal_review_page.py"),
            Path("gui/ui_layout_impl/formal_review_page_parts/page_impl.py"),
            Path("gui/main_window/mixins/navigation_mixin.py"),
            Path("gui/main_window/mixins/navigation_mixin_impl.py"),
            Path("gui/ui_layout_impl/modern_shell.py"),
            Path("gui/ui_layout_impl/modern_shell_impl.py"),
            Path("gui/official_docs_dialogs.py"),
            Path("gui/official_docs_dialogs_impl.py"),
            Path("gui/widgets_impl/formal_review/settings_dialog.py"),
            Path("core/formal_review/comment_sync.py"),
            Path("core/formal_review/range_resolver.py"),
            Path("core/formal_review/word_locator.py"),
            Path("core/formal_review/marker_rules.py"),
            Path("core/formal_review/rule_params.py"),
            Path("core/formal_review/rules.py"),
            Path("core/formal_review/service.py"),
        ]
        # Known mojibake signatures from historical regressions.
        # Keep as escapes to avoid visual noise while preserving exact match checks.
        forbidden_tokens = [
            "???",
            "\u8930\u3220\u7d21",
            "\u5bb8\ufe3d\u722e",
            "\u9359\u866b\u722e",
            "\u93c8\ue048",
            "\ufffd",
        ]
        for path in targets:
            text = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                self.assertNotIn(token, text, f"{path} contains broken copy token: {token}")


if __name__ == "__main__":
    unittest.main()
