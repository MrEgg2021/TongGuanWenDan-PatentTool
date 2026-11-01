import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewClaimTreeRenderingTests(unittest.TestCase):
    def test_claim_tree_uses_compact_content_row_and_mapping_helpers(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn('content_item = QTreeWidgetItem([""])', text)
        self.assertIn("def _format_claim_refs(refs: list[int] | None) -> str:", text)
        self.assertIn('"/".join(str(value) for value in values)', text)
        self.assertIn("def _format_markers_with_mapping(markers: list[str] | None, marker_map: dict[str, str]) -> str:", text)
        self.assertIn("rows.append(f\"{marker}({name})\")", text)


if __name__ == "__main__":
    unittest.main()
