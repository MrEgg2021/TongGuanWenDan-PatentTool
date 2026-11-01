import unittest
from unittest.mock import patch

from core.formal_review.extractor import _SectionPlanProbe, extract_formal_review_document_from_doc
from core.formal_review.service import run_formal_review


CLAIM_1 = "一种装置，其特征在于，包含A。"
CLAIM_2 = "根据权利要求1所述的装置，其特征在于，包含B。"
CLAIM_3 = "根据权利要求2所述的装置，其特征在于，包含C。"
CLAIM_4 = "根据权利要求3所述的装置，其特征在于，包含D。"


class _FakeCollection:
    def __init__(self, items):
        self._items = list(items or [])
        self.Count = len(self._items)

    def __call__(self, idx):
        return self._items[int(idx) - 1]


class _FakeListFormat:
    def __init__(self, list_value=None, list_string: str = ""):
        if list_value is not None:
            self.ListValue = list_value
        self.ListString = str(list_string or "")


class _FakeRange:
    def __init__(self, start: int, text: str, *, list_value=None, list_string: str = ""):
        self.Start = int(start)
        self.Text = str(text or "")
        self.End = int(self.Start + len(self.Text))
        self.ListFormat = _FakeListFormat(list_value=list_value, list_string=list_string)
        self.InlineShapes = _FakeCollection([])
        self.OMaths = _FakeCollection([])


class _FakeParagraph:
    def __init__(self, start: int, text: str, *, list_value=None, list_string: str = ""):
        self.Range = _FakeRange(int(start), str(text or ""), list_value=list_value, list_string=list_string)


class _FakeDoc:
    def __init__(self, paragraphs):
        self.Paragraphs = _FakeCollection(list(paragraphs or []))
        self.Sections = _FakeCollection([])


def _extract_claims_from_paragraphs(paragraphs):
    doc = _FakeDoc(paragraphs)
    with patch.object(_SectionPlanProbe, "_build_section_plan_from_headers", return_value=[]), patch.object(
        _SectionPlanProbe,
        "_get_section_key_for_paragraph",
        return_value="claims",
    ):
        document, _anchors, _editable_segments, _projections = extract_formal_review_document_from_doc(doc)
    return document


class FormalReviewExtractorClaimNumberingListFormatTests(unittest.TestCase):
    def test_list_value_only_claims_are_split(self) -> None:
        paragraphs = [
            _FakeParagraph(100, CLAIM_1, list_value=1),
            _FakeParagraph(200, CLAIM_2, list_value=2),
            _FakeParagraph(300, CLAIM_3, list_value=3),
        ]
        document = _extract_claims_from_paragraphs(paragraphs)
        self.assertEqual([1, 2, 3], [int(row.num) for row in document.claims])

    def test_text_prefix_and_list_value_do_not_merge_following_claims(self) -> None:
        paragraphs = [
            _FakeParagraph(100, f"1. {CLAIM_1}", list_value=1, list_string="1."),
            _FakeParagraph(200, CLAIM_2, list_value=2, list_string="2."),
            _FakeParagraph(300, CLAIM_3, list_value=3, list_string="3."),
        ]
        document = _extract_claims_from_paragraphs(paragraphs)
        self.assertEqual(3, len(document.claims))
        self.assertFalse(str(document.claims[0].text).startswith("1."))
        self.assertTrue(str(document.claims[1].text).startswith("根据权利要求1"))

    def test_fullwidth_list_string_digits_are_supported(self) -> None:
        paragraphs = [
            _FakeParagraph(100, CLAIM_1, list_string="１．"),
            _FakeParagraph(200, CLAIM_2, list_string="２．"),
            _FakeParagraph(300, CLAIM_3, list_string="３．"),
        ]
        document = _extract_claims_from_paragraphs(paragraphs)
        self.assertEqual([1, 2, 3], [int(row.num) for row in document.claims])

    def test_list_value_stuck_while_list_string_increments_still_splits(self) -> None:
        paragraphs = [
            _FakeParagraph(100, CLAIM_1, list_value=1, list_string="1."),
            _FakeParagraph(200, CLAIM_2, list_value=1, list_string="2."),
            _FakeParagraph(300, CLAIM_3, list_value=1, list_string="3."),
        ]
        document = _extract_claims_from_paragraphs(paragraphs)
        self.assertEqual([1, 2, 3], [int(row.num) for row in document.claims])

    def test_conflicting_candidates_use_incremental_priority_order(self) -> None:
        paragraphs = [
            _FakeParagraph(100, CLAIM_1, list_value=1, list_string="1."),
            _FakeParagraph(
                200,
                "2、根据权利要求1所述的装置，其特征在于，包含B。",
                list_value=9,
                list_string="5.",
            ),
            _FakeParagraph(300, CLAIM_3, list_value=2, list_string="3."),
        ]
        document = _extract_claims_from_paragraphs(paragraphs)
        self.assertEqual([1, 2, 3], [int(row.num) for row in document.claims])
        self.assertFalse(str(document.claims[1].text).startswith("2、"))

    def test_text_prefix_with_dunhao_without_list_info_is_split(self) -> None:
        paragraphs = [
            _FakeParagraph(100, f"1、{CLAIM_1}"),
            _FakeParagraph(200, f"2、{CLAIM_2}"),
            _FakeParagraph(300, f"3、{CLAIM_3}"),
        ]
        document = _extract_claims_from_paragraphs(paragraphs)
        self.assertEqual([1, 2, 3], [int(row.num) for row in document.claims])

    def test_zero_width_space_prefix_is_split(self) -> None:
        paragraphs = [
            _FakeParagraph(100, f"1、{CLAIM_1}"),
            _FakeParagraph(200, f"\u200b2、{CLAIM_2}"),
            _FakeParagraph(300, f"\u200b3、{CLAIM_3}"),
        ]
        document = _extract_claims_from_paragraphs(paragraphs)
        self.assertEqual([1, 2, 3], [int(row.num) for row in document.claims])
        self.assertTrue(str(document.claims[1].text).startswith("根据权利要求1"))

    def test_bom_prefix_is_split(self) -> None:
        paragraphs = [
            _FakeParagraph(100, f"1、{CLAIM_1}"),
            _FakeParagraph(200, f"\ufeff2、{CLAIM_2}"),
            _FakeParagraph(300, f"\ufeff3、{CLAIM_3}"),
        ]
        document = _extract_claims_from_paragraphs(paragraphs)
        self.assertEqual([1, 2, 3], [int(row.num) for row in document.claims])

    def test_word_joiner_prefix_is_split(self) -> None:
        paragraphs = [
            _FakeParagraph(100, f"1、{CLAIM_1}"),
            _FakeParagraph(200, f"\u20602、{CLAIM_2}"),
            _FakeParagraph(300, f"\u20603、{CLAIM_3}"),
            _FakeParagraph(400, f"\u20604、{CLAIM_4}"),
        ]
        document = _extract_claims_from_paragraphs(paragraphs)
        self.assertEqual([1, 2, 3, 4], [int(row.num) for row in document.claims])
        self.assertTrue(str(document.claims[3].text).startswith("根据权利要求3"))

    def test_hidden_prefixes_avoid_false_future_and_self(self) -> None:
        paragraphs = [
            _FakeParagraph(100, f"1、{CLAIM_1}"),
            _FakeParagraph(200, f"\u200b2、{CLAIM_2}"),
            _FakeParagraph(300, f"\ufeff3、{CLAIM_3}"),
            _FakeParagraph(400, f"\u20604、{CLAIM_4}"),
        ]
        document = _extract_claims_from_paragraphs(paragraphs)
        self.assertEqual([1, 2, 3, 4], [int(row.num) for row in document.claims])
        result = run_formal_review(
            document,
            wordlists={},
            ignored_issue_ids=set(),
            abstract_threshold=300,
        )
        issues = list(result.get("issues", []) or [])
        rule_ids = {str(getattr(row, "rule_id", "") or "") for row in issues}
        self.assertNotIn("claim.ref.future", rule_ids)
        self.assertNotIn("claim.ref.self", rule_ids)

    def test_split_claims_avoid_false_future_reference_issue(self) -> None:
        paragraphs = [
            _FakeParagraph(100, CLAIM_1, list_value=1, list_string="1."),
            _FakeParagraph(200, CLAIM_2, list_value=1, list_string="2."),
            _FakeParagraph(300, CLAIM_3, list_value=1, list_string="3."),
        ]
        document = _extract_claims_from_paragraphs(paragraphs)
        self.assertEqual([1, 2, 3], [int(row.num) for row in document.claims])
        result = run_formal_review(
            document,
            wordlists={},
            ignored_issue_ids=set(),
            abstract_threshold=300,
        )
        issues = list(result.get("issues", []) or [])
        rule_ids = {str(getattr(row, "rule_id", "") or "") for row in issues}
        self.assertNotIn("claim.ref.future", rule_ids)


if __name__ == "__main__":
    unittest.main()
