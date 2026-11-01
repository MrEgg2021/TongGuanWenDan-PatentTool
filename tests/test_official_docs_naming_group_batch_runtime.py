from __future__ import annotations

import unittest

from gui.main_window.mixins.official_docs_ops.type_list_ops import (
    _build_type_action_button_states,
    _merge_checked_type_tree_targets,
)


class OfficialDocsNamingGroupBatchRuntimeTests(unittest.TestCase):
    def test_merge_checked_targets_deduplicates_group_and_child_entries(self) -> None:
        checked = _merge_checked_type_tree_targets(
            [
                {
                    "node_kind": "group",
                    "group_id": "group-a",
                    "type_key": "exam_opinion",
                    "member_contexts": [
                        {
                            "node_kind": "group_member",
                            "group_id": "group-a",
                            "type_key": "exam_opinion",
                            "member_keys": ["exam_opinion"],
                        },
                        {
                            "node_kind": "group_member",
                            "group_id": "group-a",
                            "type_key": "exam_decision",
                            "member_keys": ["exam_decision"],
                        },
                    ],
                },
                {
                    "node_kind": "group_member",
                    "group_id": "group-a",
                    "type_key": "exam_opinion",
                    "member_keys": ["exam_opinion"],
                },
                {
                    "node_kind": "ungrouped_type",
                    "group_id": "",
                    "type_key": "certificate",
                    "member_keys": ["certificate"],
                },
            ]
        )

        self.assertEqual(checked["group_ids"], ["group-a"])
        self.assertEqual(
            [context["type_key"] for context in checked["type_contexts"]],
            ["exam_opinion", "exam_decision", "certificate"],
        )
        self.assertEqual(
            [context["type_key"] for context in checked["group_member_contexts"]],
            ["exam_opinion", "exam_decision"],
        )
        self.assertEqual(
            [context["type_key"] for context in checked["ungrouped_type_contexts"]],
            ["certificate"],
        )
        self.assertEqual(checked["checked_group_count"], 1)
        self.assertEqual(checked["checked_type_count"], 3)

    def test_button_states_use_focus_and_checked_targets_separately(self) -> None:
        states = _build_type_action_button_states(
            focus_node_kind="group",
            has_ungrouped_entries=True,
            checked_targets={
                "group_ids": ["group-a"],
                "type_contexts": [
                    {"type_key": "exam_opinion"},
                    {"type_key": "certificate"},
                ],
                "group_member_contexts": [{"type_key": "exam_opinion"}],
                "ungrouped_type_contexts": [{"type_key": "certificate"}],
            },
        )

        self.assertTrue(states["official_docs_create_group_button"])
        self.assertTrue(states["official_docs_rename_group_button"])
        self.assertTrue(states["official_docs_delete_group_button"])
        self.assertTrue(states["official_docs_add_group_member_button"])
        self.assertTrue(states["official_docs_join_group_button"])
        self.assertTrue(states["official_docs_move_group_button"])
        self.assertTrue(states["official_docs_remove_group_button"])

    def test_button_states_fall_back_to_focus_only_when_nothing_checked(self) -> None:
        states = _build_type_action_button_states(
            focus_node_kind="ungrouped_root",
            has_ungrouped_entries=True,
            checked_targets={
                "group_ids": [],
                "type_contexts": [],
                "group_member_contexts": [],
                "ungrouped_type_contexts": [],
            },
        )

        self.assertTrue(states["official_docs_create_group_button"])
        self.assertFalse(states["official_docs_rename_group_button"])
        self.assertFalse(states["official_docs_delete_group_button"])
        self.assertFalse(states["official_docs_add_group_member_button"])
        self.assertFalse(states["official_docs_join_group_button"])
        self.assertFalse(states["official_docs_move_group_button"])
        self.assertFalse(states["official_docs_remove_group_button"])

    def test_button_states_enable_group_actions_from_focus_when_nothing_checked(self) -> None:
        states = _build_type_action_button_states(
            focus_node_kind="group",
            has_ungrouped_entries=True,
            checked_targets={
                "group_ids": [],
                "type_contexts": [],
                "group_member_contexts": [],
                "ungrouped_type_contexts": [],
            },
        )

        self.assertTrue(states["official_docs_create_group_button"])
        self.assertTrue(states["official_docs_rename_group_button"])
        self.assertTrue(states["official_docs_delete_group_button"])
        self.assertTrue(states["official_docs_add_group_member_button"])
        self.assertFalse(states["official_docs_join_group_button"])
        self.assertFalse(states["official_docs_move_group_button"])
        self.assertFalse(states["official_docs_remove_group_button"])

    def test_button_states_enable_member_actions_from_focus_when_nothing_checked(self) -> None:
        ungrouped_states = _build_type_action_button_states(
            focus_node_kind="ungrouped_type",
            has_ungrouped_entries=True,
            checked_targets={
                "group_ids": [],
                "type_contexts": [],
                "group_member_contexts": [],
                "ungrouped_type_contexts": [],
            },
        )
        self.assertTrue(ungrouped_states["official_docs_join_group_button"])
        self.assertTrue(ungrouped_states["official_docs_move_group_button"])
        self.assertFalse(ungrouped_states["official_docs_remove_group_button"])

        grouped_states = _build_type_action_button_states(
            focus_node_kind="group_member",
            has_ungrouped_entries=True,
            checked_targets={
                "group_ids": [],
                "type_contexts": [],
                "group_member_contexts": [],
                "ungrouped_type_contexts": [],
            },
        )
        self.assertFalse(grouped_states["official_docs_join_group_button"])
        self.assertTrue(grouped_states["official_docs_move_group_button"])
        self.assertTrue(grouped_states["official_docs_remove_group_button"])


if __name__ == "__main__":
    unittest.main()
