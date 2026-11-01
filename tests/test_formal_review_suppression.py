import unittest
from dataclasses import dataclass

from core.formal_review.suppression import SuppressionStore, build_instance_fingerprint


@dataclass
class _Issue:
    rule_id: str
    section: str
    category: str
    snippet: str


class FormalReviewSuppressionTests(unittest.TestCase):
    def test_instance_suppression_by_fingerprint(self) -> None:
        store = SuppressionStore()
        store.switch_file("doc-a")
        fp = build_instance_fingerprint(
            rule_id="punctuation.repeated",
            section="description",
            claim_num=None,
            pre_context="a",
            snippet="，，",
            post_context="b",
        )
        issue = _Issue(rule_id="punctuation.repeated", section="description", category="rule", snippet="，，")
        self.assertFalse(store.is_suppressed(issue, fp))
        store.mark_instance(fp, True)
        self.assertTrue(store.is_suppressed(issue, fp))
        store.mark_instance(fp, False)
        self.assertFalse(store.is_suppressed(issue, fp))

    def test_switch_file_resets_scope(self) -> None:
        store = SuppressionStore()
        store.switch_file("doc-a")
        store.mark_instance("fingerprint-1", True)
        store.switch_file("doc-b")
        issue = _Issue(rule_id="r1", section="description", category="rule", snippet="x")
        self.assertFalse(store.is_suppressed(issue, "fingerprint-1"))


if __name__ == "__main__":
    unittest.main()
