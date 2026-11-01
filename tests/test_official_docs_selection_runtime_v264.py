from __future__ import annotations

import unittest

from PySide6.QtCore import Qt

from gui.main_window.mixins.official_docs_ops.task_tree_ops import (
    TREE_NODE_BUNDLE,
    TREE_NODE_LEAF,
    on_official_docs_item_check_changed,
    on_official_docs_selection_changed,
)


class _FakeItem:
    def __init__(self, data=None, children=None, *, check_state=Qt.Checked, parent=None, text="") -> None:
        self._data = data
        self._children = list(children or [])
        self._check_state = check_state
        self._parent = parent
        self._text = text
        for child in self._children:
            child._parent = self

    def data(self, _column: int, _role: int):
        return self._data

    def childCount(self) -> int:
        return len(self._children)

    def child(self, index: int):
        if 0 <= index < len(self._children):
            return self._children[index]
        return None

    def checkState(self, _column: int) -> int:
        return self._check_state

    def parent(self):
        return self._parent

    def text(self, _column: int) -> str:
        return self._text

    def setText(self, _column: int, value: str) -> None:
        self._text = value


class _DeletedQtItem:
    def data(self, _column: int, _role: int):
        raise RuntimeError("Internal C++ object already deleted.")


class _DummyWindow:
    def __init__(self) -> None:
        self._official_docs_tree_rebuilding = False
        self._official_docs_selected_leaf_id = "leaf-old"
        self.refresh_calls = 0
        self.render_calls = 0
        self._official_docs_leaves = {
            "leaf-old": {"id": "leaf-old", "checked": True},
            "leaf-child": {"id": "leaf-child", "checked": True},
        }
        self._official_docs_bundles = {
            "bundle-1": {"key": "bundle-1", "display_name": "Bundle A"},
        }
        self.start_button = _DummyButton()
        self.official_docs_start_button = self.start_button
        self._official_docs_working_settings = {
            "write_summary": True,
            "summary_root_dir": "D:/summary",
            "write_archive": False,
            "archive_root_dir": "",
            "type_configs": {},
        }

    def _init_official_docs_state(self) -> None:
        return None

    def _refresh_official_docs_detail(self) -> None:
        self.refresh_calls += 1

    def _render_official_docs_tree(self) -> None:
        self.render_calls += 1

    def _validate_official_docs_settings(self, _settings) -> list[str]:
        return []

    def _iter_checked_leaf_ids(self):
        for leaf_id, payload in self._official_docs_leaves.items():
            if bool(payload.get("checked", True)):
                yield leaf_id


class _DummyButton:
    def __init__(self) -> None:
        self.enabled = None

    def setEnabled(self, value: bool) -> None:
        self.enabled = bool(value)


class OfficialDocsSelectionRuntimeV264Tests(unittest.TestCase):
    def test_ignores_selection_signal_while_tree_rebuilding(self) -> None:
        window = _DummyWindow()
        window._official_docs_tree_rebuilding = True
        window._official_docs_selected_leaf_id = "leaf-rendered"
        current = _FakeItem({"type": TREE_NODE_LEAF, "id": "leaf-signal"})

        on_official_docs_selection_changed(window, current, None)

        self.assertEqual(window._official_docs_selected_leaf_id, "leaf-rendered")
        self.assertEqual(window.refresh_calls, 0)

    def test_bundle_selection_uses_first_child_leaf_id(self) -> None:
        window = _DummyWindow()
        child = _FakeItem({"type": TREE_NODE_LEAF, "id": "leaf-child"})
        bundle = _FakeItem({"type": TREE_NODE_BUNDLE, "key": "bundle-1"}, [child])

        on_official_docs_selection_changed(window, bundle, None)

        self.assertEqual(window._official_docs_selected_leaf_id, "leaf-child")
        self.assertEqual(window.refresh_calls, 1)

    def test_invalid_selection_clears_stale_leaf_id(self) -> None:
        window = _DummyWindow()
        invalid = _FakeItem({"type": "unknown"})

        on_official_docs_selection_changed(window, invalid, None)

        self.assertEqual(window._official_docs_selected_leaf_id, "")
        self.assertEqual(window.refresh_calls, 1)

    def test_deleted_qt_item_selection_clears_stale_leaf_id(self) -> None:
        window = _DummyWindow()

        on_official_docs_selection_changed(window, _DeletedQtItem(), None)

        self.assertEqual(window._official_docs_selected_leaf_id, "")
        self.assertEqual(window.refresh_calls, 1)

    def test_item_check_changed_avoids_tree_rebuild_and_updates_bundle_count(self) -> None:
        window = _DummyWindow()
        child_a = _FakeItem({"type": TREE_NODE_LEAF, "id": "leaf-old"}, check_state=Qt.Unchecked)
        child_b = _FakeItem({"type": TREE_NODE_LEAF, "id": "leaf-child"}, check_state=Qt.Checked)
        bundle = _FakeItem({"type": TREE_NODE_BUNDLE, "key": "bundle-1"}, [child_a, child_b], text="Bundle A (2/2)")

        on_official_docs_item_check_changed(window, child_a, 0)

        self.assertFalse(window._official_docs_leaves["leaf-old"]["checked"])
        self.assertEqual(window.render_calls, 0)
        self.assertEqual(window.refresh_calls, 0)
        self.assertEqual(bundle.text(0), "Bundle A (1/2)")
        self.assertTrue(window.start_button.enabled)


if __name__ == "__main__":
    unittest.main()
