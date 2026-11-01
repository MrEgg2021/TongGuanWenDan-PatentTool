import symtable
import unittest
from pathlib import Path

from gui.main_window.mixins import settings_env_registry
from gui.main_window.mixins.formal_review_mixin import FormalReviewMixin
from gui.main_window.mixins.formal_review_ops import shared
from gui.main_window.mixins import official_docs_mixin
from gui.main_window.mixins.official_docs_ops import shared as official_docs_shared
from gui.main_window.mixins.official_docs_ops import state_ops as official_docs_state_ops
from gui.main_window.mixins.official_docs_ops import type_list_ops as official_docs_type_list_ops


REPO_ROOT = Path(__file__).resolve().parents[1]
FORMAL_REVIEW_OPS_DIR = REPO_ROOT / "gui/main_window/mixins/formal_review_ops"
FORMAL_REVIEW_STAR_CONSUMERS = (
    "companion_ops.py",
    "edit_ops.py",
    "issue_view_ops.py",
    "marker_ops.py",
    "settings_export_ops.py",
    "state_ops.py",
    "workspace_ops.py",
)


def _loaded_global_names(path: Path) -> set[str]:
    table = symtable.symtable(path.read_text(encoding="utf-8"), str(path), "exec")
    loaded_globals: set[str] = set()

    def collect(scope: symtable.SymbolTable) -> None:
        for symbol in scope.get_symbols():
            if symbol.is_global() and symbol.is_referenced():
                loaded_globals.add(symbol.get_name())
        for child in scope.get_children():
            collect(child)

    collect(table)
    return loaded_globals


class CompatibilityExportContractTests(unittest.TestCase):
    def test_runtime_sources_do_not_use_star_imports(self) -> None:
        star_imports: list[str] = []
        for source_root in ("core", "gui", "licensing", "tools"):
            for path in (REPO_ROOT / source_root).rglob("*.py"):
                if " import *" in path.read_text(encoding="utf-8-sig"):
                    star_imports.append(str(path.relative_to(REPO_ROOT)))

        self.assertEqual([], star_imports)

    def test_formal_review_mixin_binds_shared_instance_helpers(self) -> None:
        self.assertIs(FormalReviewMixin._ask_continue_cancel_cn, shared._ask_continue_cancel_cn)

    def test_formal_review_shared_exports_only_consumer_dependencies(self) -> None:
        exported = set(shared.__all__)
        required: set[str] = set()
        shared_names = set(vars(shared))
        for filename in FORMAL_REVIEW_STAR_CONSUMERS:
            required.update(_loaded_global_names(FORMAL_REVIEW_OPS_DIR / filename) & shared_names)

        self.assertFalse(required - exported)
        self.assertTrue(
            {
                "re",
                "traceback",
                "dataclass",
                "QObject",
                "Signal",
                "Slot",
                "TOOL_COMMENT_PREFIX",
                "rule_items_for_ui",
            }.isdisjoint(exported)
        )

    def test_settings_registry_declares_its_compatibility_exports(self) -> None:
        self.assertEqual(
            {
                "discover_ms_word_versions_from_registry",
                "parse_localserver_exe_path",
                "probe_word_env_from_registry",
                "progid_localserver32",
                "reg_read_default",
            },
            set(settings_env_registry.__all__),
        )

    def test_official_docs_mixin_preserves_shared_exports_and_method_bindings(self) -> None:
        self.assertIs(
            getattr(official_docs_mixin, "_default_settings"),
            official_docs_shared._default_settings,
        )
        self.assertIs(
            official_docs_mixin.OfficialDocsMixin._init_official_docs_state,
            official_docs_state_ops._init_official_docs_state,
        )
        self.assertIs(
            official_docs_mixin.OfficialDocsMixin._type_tree_context_from_item,
            official_docs_type_list_ops._type_tree_context_from_item,
        )


if __name__ == "__main__":
    unittest.main()
