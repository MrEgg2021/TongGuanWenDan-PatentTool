import unittest
from unittest.mock import patch

from core.formal_review import marker_rules
from core.formal_review.models import ClaimItem, FormalReviewDocument
from core.formal_review.range_resolver import ResolveResult


class _FakeRange:
    def __init__(self, text: str, start: int, end: int) -> None:
        self.Start = int(start)
        self.End = int(end)
        self.Text = str(text or "")[self.Start : self.End]


class _FakeDoc:
    def __init__(self, text: str) -> None:
        self._text = str(text or "")

    def Range(self, start: int, end: int):  # noqa: N802 - COM style
        s = max(0, int(start))
        e = max(s, int(end))
        e = min(e, len(self._text))
        return _FakeRange(self._text, s, e)


class FormalReviewMarkerClaimLocatorRescueTests(unittest.TestCase):
    def test_word_mode_correct_hit_skips_resolver_fast_path(self) -> None:
        claim_text = "the Valve\uff081\uff09 connects."
        document = FormalReviewDocument(
            claims=[ClaimItem(num=1, text=claim_text, anchor_start=0, anchor_end=len(claim_text))],
            description="",
        )
        with patch.object(marker_rules, "resolve_issue_range", side_effect=AssertionError("resolver should not run")):
            plan = marker_rules.build_marker_normalization_write_plan(
                document=document,
                name_to_marker={"Valve": "1"},
                description_segments=[],
                doc=object(),
                projections=object(),
            )

        self.assertEqual(int(getattr(plan, "candidate_claims", 0) or 0), 1)
        self.assertEqual(int(getattr(plan, "skipped_correct_count", 0) or 0), 1)
        self.assertEqual(int(getattr(plan, "command_count", 0) or 0), 0)

    def test_claim_locator_name_nearby_rescue_restores_full_name_end(self) -> None:
        claim_text = "the Valve(56) connects."
        document = FormalReviewDocument(
            claims=[ClaimItem(num=1, text=claim_text, anchor_start=0, anchor_end=len(claim_text))],
            description="",
        )
        doc = _FakeDoc(claim_text)
        strict_fail = ResolveResult(
            ok=False,
            level="fail",
            start=None,
            end=None,
            reason="strict failed",
            reason_code="word_find_mismatch",
            detail="",
            expected="Valve",
            actual="",
        )
        loose_partial = ResolveResult(
            ok=True,
            level="word_find_com",
            start=4,
            end=8,
            reason="loose rescued",
            reason_code="word_find_hit",
            detail="",
            expected="Valve",
            actual="Valve",
        )
        with patch.object(marker_rules, "resolve_issue_range", side_effect=[strict_fail, loose_partial]):
            plan = marker_rules.build_marker_normalization_write_plan(
                document=document,
                name_to_marker={"Valve": "1"},
                description_segments=[],
                doc=doc,
                projections=object(),
            )

        self.assertEqual(int(getattr(plan, "claim_resolve_strict_failed_count", 0) or 0), 1)
        self.assertEqual(int(getattr(plan, "claim_resolve_loose_rescued_count", 0) or 0), 1)
        self.assertEqual(int(getattr(plan, "claim_resolve_word_find_com_count", 0) or 0), 1)
        self.assertEqual(int(getattr(plan, "claim_resolve_word_find_legacy_count", 0) or 0), 0)
        self.assertEqual(int(getattr(plan, "claim_name_exact_check_failed_count", 0) or 0), 1)
        self.assertEqual(int(getattr(plan, "claim_name_nearby_rescued_count", 0) or 0), 1)
        self.assertEqual(int(getattr(plan, "claim_name_unsafe_continue_count", 0) or 0), 0)
        self.assertEqual(int(getattr(plan, "command_count", 0) or 0), 1)
        cmd = list(getattr(plan, "commands", []))[0]
        self.assertEqual(str(getattr(cmd, "expected_old_fragment", "")), "(56)")
        self.assertEqual(str(getattr(cmd, "replacement_text", "")), "（1）")
        self.assertEqual(int(getattr(cmd, "word_start", -1)), 9)

    def test_claim_locator_skips_when_nearby_rescue_fails(self) -> None:
        claim_text = "the Valve(56) connects."
        document = FormalReviewDocument(
            claims=[ClaimItem(num=1, text=claim_text, anchor_start=0, anchor_end=len(claim_text))],
            description="",
        )
        doc = _FakeDoc(claim_text)
        strict_fail = ResolveResult(
            ok=False,
            level="fail",
            start=None,
            end=None,
            reason="strict failed",
            reason_code="word_find_mismatch",
            detail="",
            expected="Valve",
            actual="",
        )
        loose_partial = ResolveResult(
            ok=True,
            level="word_find_com",
            start=4,
            end=8,
            reason="loose rescued",
            reason_code="word_find_hit",
            detail="",
            expected="Valve",
            actual="Valve",
        )
        with patch.object(marker_rules, "resolve_issue_range", side_effect=[strict_fail, loose_partial]):
            with patch.object(marker_rules, "_rescue_claim_name_word_range", return_value=None):
                plan = marker_rules.build_marker_normalization_write_plan(
                    document=document,
                    name_to_marker={"Valve": "1"},
                    description_segments=[],
                    doc=doc,
                    projections=object(),
                )

        self.assertEqual(int(getattr(plan, "claim_name_exact_check_failed_count", 0) or 0), 1)
        self.assertEqual(int(getattr(plan, "claim_name_nearby_rescued_count", 0) or 0), 0)
        self.assertEqual(int(getattr(plan, "claim_name_unsafe_continue_count", 0) or 0), 1)
        self.assertEqual(int(getattr(plan, "claim_resolve_word_find_com_count", 0) or 0), 1)
        self.assertEqual(int(getattr(plan, "claim_resolve_word_find_legacy_count", 0) or 0), 0)
        self.assertEqual(int(getattr(plan, "skipped_unsupported_count", 0) or 0), 1)
        self.assertEqual(int(getattr(plan, "command_count", 0) or 0), 0)


if __name__ == "__main__":
    unittest.main()
