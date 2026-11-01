import unittest
from unittest.mock import patch

from core.formal_review import range_resolver
from core.formal_review.models import Issue
from core.formal_review.range_resolver import ResolverMetrics, ResolverPolicy, check_com_find_ready, resolve_issue_range
from core.formal_review.text_projection import ParagraphProjection, ProjectionBundle, SectionProjection


class _FakeRange:
    def __init__(self, doc, start: int, end: int) -> None:
        self._doc = doc
        self.Start = int(start)
        self.End = int(end)
        self.Text = doc.text[self.Start : self.End]


class _FakeDoc:
    def __init__(self, text: str) -> None:
        self.text = text

    def Range(self, start: int, end: int):  # noqa: N802 - COM style
        start = int(start)
        end = int(end)
        if start < 0 or end < start or end > len(self.text):
            raise ValueError("invalid range")
        return _FakeRange(self, start, end)


class _FakeReplacement:
    def ClearFormatting(self) -> None:  # noqa: N802 - COM style
        return None


class _FakeFind:
    def __init__(self, rng) -> None:
        self._range = rng
        self.Text = ""
        self.Forward = True
        self.Wrap = 0
        self.Format = False
        self.MatchCase = False
        self.MatchWholeWord = False
        self.MatchWildcards = False
        self.MatchSoundsLike = False
        self.MatchAllWordForms = False
        self.Replacement = _FakeReplacement()

    def ClearFormatting(self) -> None:  # noqa: N802 - COM style
        return None

    def Execute(self, *args, **kwargs):  # noqa: N802 - COM style
        needle = str(self.Text or "")
        if not needle:
            return False
        source = str(self._range._doc.text or "")
        start = int(self._range.Start)
        end = int(self._range.End)
        idx = source.find(needle, start, end)
        if idx < 0:
            return False
        self._range.Start = int(idx)
        self._range.End = int(idx + len(needle))
        self._range.Text = source[self._range.Start : self._range.End]
        return True


class _FakeFindTextGuard(_FakeFind):
    def __init__(self, rng) -> None:
        self._text = ""
        super().__init__(rng)

    @property
    def Text(self) -> str:  # noqa: N802 - COM style
        return str(self._text or "")

    @Text.setter
    def Text(self, value: str) -> None:  # noqa: N802 - COM style
        text = str(value or "")
        if ("\n" in text) or ("\r" in text) or (len(text) > 120):
            raise ValueError("set Text failed")
        self._text = text


class _FakeFindRange(_FakeRange):
    def __init__(self, doc, start: int, end: int) -> None:
        super().__init__(doc, start, end)
        self.Find = _FakeFind(self)


class _FakeDocWithFind(_FakeDoc):
    def Range(self, start: int, end: int):  # noqa: N802 - COM style
        start = int(start)
        end = int(end)
        if start < 0 or end < start or end > len(self.text):
            raise ValueError("invalid range")
        return _FakeFindRange(self, start, end)


class _FakeFindTextGuardRange(_FakeRange):
    def __init__(self, doc, start: int, end: int) -> None:
        super().__init__(doc, start, end)
        self.Find = _FakeFindTextGuard(self)


class _FakeDocWithFindTextGuard(_FakeDoc):
    def Range(self, start: int, end: int):  # noqa: N802 - COM style
        start = int(start)
        end = int(end)
        if start < 0 or end < start or end > len(self.text):
            raise ValueError("invalid range")
        return _FakeFindTextGuardRange(self, start, end)


class FormalReviewRangeResolverWordFindTests(unittest.TestCase):
    def test_projection_compare_sanitizes_hidden_markers(self) -> None:
        # Word Range.Text may include hidden control markers (e.g., comment anchors).
        word_text = "A\x05B"
        review_text = "AB"

        issue = Issue(
            rule_id="wordlist.description.forbidden",
            severity="high",
            category="forbidden",
            section="description",
            message="test",
            span_start=0,
            span_end=2,
            anchor={"expected_hit": "AB", "word_range_start": 0},
            issue_id="i-1",
            ignored=False,
        )

        para = ParagraphProjection(
            section="description",
            claim_num=None,
            paragraph_index=1,
            local_start=0,
            local_end=len(review_text),
            word_start=0,
            word_end=len(word_text),
            text=review_text,
            offset_map_start=[0, 2],
            offset_map_end=[1, 3],
        )
        projections = ProjectionBundle(
            claims={},
            sections={"description": SectionProjection(section="description", claim_num=None, paragraphs=[para])},
        )

        doc = _FakeDoc(word_text)
        resolved = resolve_issue_range(doc, issue, projections, strict=True)
        self.assertTrue(resolved.ok)
        self.assertEqual(resolved.level, "projection")
        self.assertEqual(-1 if resolved.start is None else int(resolved.start), 0)
        self.assertEqual(-1 if resolved.end is None else int(resolved.end), 3)

    def test_word_find_fallback_when_linear_mapping_mismatches(self) -> None:
        word_text = "A\x05B"
        review_text = "AB"

        issue = Issue(
            rule_id="wordlist.description.forbidden",
            severity="high",
            category="forbidden",
            section="description",
            message="test",
            span_start=0,
            span_end=2,
            anchor={"expected_hit": "AB", "word_range_start": 0},
            issue_id="i-2",
            ignored=False,
        )

        # No offset_map_* provided: direct projection mapping falls back to linear offsets and mismatches.
        para = ParagraphProjection(
            section="description",
            claim_num=None,
            paragraph_index=1,
            local_start=0,
            local_end=len(review_text),
            word_start=0,
            word_end=len(word_text),
            text=review_text,
        )
        projections = ProjectionBundle(
            claims={},
            sections={"description": SectionProjection(section="description", claim_num=None, paragraphs=[para])},
        )

        doc = _FakeDoc(word_text)
        resolved = resolve_issue_range(doc, issue, projections, strict=True, allow_legacy_fallback=True)
        self.assertTrue(resolved.ok)
        self.assertEqual(resolved.level, "word_find_legacy")
        self.assertEqual(-1 if resolved.start is None else int(resolved.start), 0)
        self.assertEqual(-1 if resolved.end is None else int(resolved.end), 3)

    def test_blocks_when_com_find_unavailable_and_legacy_not_allowed(self) -> None:
        issue = Issue(
            rule_id="wordlist.description.forbidden",
            severity="high",
            category="forbidden",
            section="description",
            message="test",
            span_start=0,
            span_end=2,
            anchor={"expected_hit": "AB", "word_range_start": 0},
            issue_id="i-block-1",
            ignored=False,
        )
        para = ParagraphProjection(
            section="description",
            claim_num=None,
            paragraph_index=1,
            local_start=0,
            local_end=2,
            word_start=0,
            word_end=3,
            text="AB",
        )
        projections = ProjectionBundle(
            claims={},
            sections={"description": SectionProjection(section="description", claim_num=None, paragraphs=[para])},
        )
        doc = _FakeDoc("A\x05B")
        resolved = resolve_issue_range(doc, issue, projections, strict=True)
        self.assertFalse(resolved.ok)
        self.assertEqual(str(resolved.reason_code), "com_find_unavailable_blocked")

    def test_require_com_ready_blocks_early_and_records_metrics(self) -> None:
        issue = Issue(
            rule_id="wordlist.description.forbidden",
            severity="high",
            category="forbidden",
            section="description",
            message="test",
            span_start=0,
            span_end=2,
            anchor={"expected_hit": "AB", "word_range_start": 0},
            issue_id="i-block-2",
            ignored=False,
        )
        para = ParagraphProjection(
            section="description",
            claim_num=None,
            paragraph_index=1,
            local_start=0,
            local_end=2,
            word_start=0,
            word_end=3,
            text="AB",
        )
        projections = ProjectionBundle(
            claims={},
            sections={"description": SectionProjection(section="description", claim_num=None, paragraphs=[para])},
        )
        metrics = ResolverMetrics()
        resolved = resolve_issue_range(
            _FakeDoc("A\x05B"),
            issue,
            projections,
            policy=ResolverPolicy(strict=True, allow_legacy_fallback=False, require_com_ready=True),
            metrics=metrics,
        )
        self.assertFalse(resolved.ok)
        self.assertEqual(str(resolved.reason_code), "com_find_unavailable_blocked")
        self.assertEqual(int(metrics.total_calls), 1)
        self.assertEqual(int(dict(metrics.reason_hist).get("com_find_unavailable_blocked", 0)), 1)

    def test_check_com_find_ready_reports_availability(self) -> None:
        unavailable = check_com_find_ready(_FakeDoc("AB"))
        self.assertFalse(unavailable.ok)
        self.assertEqual(str(unavailable.reason_code), "com_find_unavailable")

        available = check_com_find_ready(_FakeDocWithFind("AB"))
        self.assertTrue(available.ok)
        self.assertEqual(str(available.reason_code), "ok")

    def test_projection_mapping_with_carriage_return_keeps_absolute_offsets(self) -> None:
        word_text = "分\r配管"
        review_text = "分配管"

        issue = Issue(
            rule_id="wordlist.description.forbidden",
            severity="high",
            category="forbidden",
            section="description",
            message="test",
            span_start=0,
            span_end=3,
            anchor={"expected_hit": "分配管", "word_range_start": 0},
            issue_id="i-cr-1",
            ignored=False,
        )

        para = ParagraphProjection(
            section="description",
            claim_num=None,
            paragraph_index=1,
            local_start=0,
            local_end=len(review_text),
            word_start=0,
            word_end=len(word_text),
            text=review_text,
            offset_map_start=[0, 2, 3],
            offset_map_end=[1, 3, 4],
        )
        projections = ProjectionBundle(
            claims={},
            sections={"description": SectionProjection(section="description", claim_num=None, paragraphs=[para])},
        )

        doc = _FakeDoc(word_text)
        resolved = resolve_issue_range(doc, issue, projections, strict=True)
        self.assertTrue(resolved.ok)
        self.assertEqual(resolved.level, "projection")
        self.assertEqual(-1 if resolved.start is None else int(resolved.start), 0)
        self.assertEqual(-1 if resolved.end is None else int(resolved.end), 4)

    def test_word_find_loose_claims_still_requires_exact(self) -> None:
        doc = _FakeDoc("A")
        paragraph = ParagraphProjection(
            section="claims",
            claim_num=1,
            paragraph_index=1,
            local_start=0,
            local_end=1,
            word_start=0,
            word_end=1,
            text="A",
        )
        resolved = range_resolver._resolve_via_word_find(  # type: ignore[attr-defined]
            doc,
            paragraph=paragraph,
            candidate="A",
            occurrence_idx=0,
            expected="AB",
            pre_context="",
            post_context="",
            strict=False,
            require_exact=True,
        )
        self.assertFalse(resolved.ok)
        self.assertEqual(str(resolved.reason_code), "word_find_mismatch")

    def test_resolve_issue_range_prefers_com_find_when_available(self) -> None:
        issue = Issue(
            rule_id="wordlist.claims.forbidden",
            severity="high",
            category="forbidden",
            section="claims",
            claim_num=1,
            message="test",
            span_start=0,
            span_end=1,
            anchor={"expected_hit": "Valve", "word_range_start": 0},
            issue_id="i-com-1",
            ignored=False,
        )
        para = ParagraphProjection(
            section="claims",
            claim_num=1,
            paragraph_index=1,
            local_start=0,
            local_end=1,
            word_start=0,
            word_end=5,
            text="X",
        )
        projections = ProjectionBundle(
            claims={1: SectionProjection(section="claims", claim_num=1, paragraphs=[para])},
            sections={},
        )
        doc = _FakeDocWithFind("Valve")
        with patch.object(range_resolver, "_resolve_via_word_find", side_effect=AssertionError("fallback should not run")):
            resolved = resolve_issue_range(doc, issue, projections, strict=True)
        self.assertTrue(resolved.ok)
        self.assertEqual(str(resolved.level), "word_find_com")
        self.assertEqual(int(resolved.start or 0), 0)
        self.assertEqual(int(resolved.end or 0), 5)

    def test_long_multiline_expected_hit_falls_back_to_snippet_for_com_find(self) -> None:
        issue = Issue(
            rule_id="description.drawings.figure.ref.missing_in_drawings_section",
            severity="error",
            category="rule",
            section="description",
            message="test",
            span_start=0,
            span_end=2,
            snippet="AB",
            anchor={"expected_hit": ("A\n" * 80).strip(), "word_range_start": 0},
            issue_id="i-com-safe-candidate",
            ignored=False,
        )
        paragraph = ParagraphProjection(
            section="description",
            claim_num=None,
            paragraph_index=1,
            local_start=0,
            local_end=4,
            word_start=0,
            word_end=3,
            text="A BX",
        )
        projections = ProjectionBundle(
            claims={},
            sections={"description": SectionProjection(section="description", claim_num=None, paragraphs=[paragraph])},
        )
        resolved = resolve_issue_range(_FakeDocWithFindTextGuard("ABX"), issue, projections, strict=True)
        self.assertTrue(resolved.ok)
        self.assertEqual(str(resolved.level), "word_find_com")
        self.assertNotEqual(str(resolved.reason_code or ""), "com_find_init_failed")

    def test_choose_candidate_uses_safe_candidate_list_entry(self) -> None:
        candidate, source = range_resolver._choose_resolver_candidate(  # type: ignore[attr-defined]
            "line1\nline2",
            "",
            ["bad\ncandidate", "说明书附图"],
        )
        self.assertEqual("说明书附图", candidate)
        self.assertEqual("candidate_list", source)

    def test_resolve_detail_contains_candidate_source_when_candidate_list_used(self) -> None:
        issue = Issue(
            rule_id="drawings.figure.ref.missing_in_description_drawings",
            severity="error",
            category="rule",
            section="drawings",
            message="test",
            span_start=0,
            span_end=1,
            snippet="",
            anchor={
                "expected_hit": "line1\nline2",
                "expected_hit_candidates": ["bad\ncandidate", "说明书附图"],
                "word_range_start": 0,
            },
            issue_id="i-candidate-source",
            ignored=False,
        )
        paragraph = ParagraphProjection(
            section="drawings",
            claim_num=None,
            paragraph_index=1,
            local_start=0,
            local_end=0,
            word_start=0,
            word_end=0,
            text="",
        )
        projections = ProjectionBundle(
            claims={},
            sections={"drawings": SectionProjection(section="drawings", claim_num=None, paragraphs=[paragraph])},
        )
        resolved = resolve_issue_range(_FakeDoc(""), issue, projections, strict=True)
        self.assertFalse(resolved.ok)
        self.assertEqual("projection_text_empty", str(resolved.reason_code))
        self.assertIn("candidate_source=candidate_list", str(resolved.detail))

    def test_logs_resolve_path_for_com_and_legacy(self) -> None:
        issue_com = Issue(
            rule_id="wordlist.claims.forbidden",
            severity="high",
            category="forbidden",
            section="claims",
            claim_num=1,
            message="test",
            span_start=0,
            span_end=1,
            anchor={"expected_hit": "Valve", "word_range_start": 0},
            issue_id="i-log-com",
            ignored=False,
        )
        para_com = ParagraphProjection(
            section="claims",
            claim_num=1,
            paragraph_index=1,
            local_start=0,
            local_end=1,
            word_start=0,
            word_end=5,
            text="X",
        )
        projections_com = ProjectionBundle(
            claims={1: SectionProjection(section="claims", claim_num=1, paragraphs=[para_com])},
            sections={},
        )

        issue_legacy = Issue(
            rule_id="wordlist.description.forbidden",
            severity="high",
            category="forbidden",
            section="description",
            message="test",
            span_start=0,
            span_end=2,
            anchor={"expected_hit": "AB", "word_range_start": 0},
            issue_id="i-log-legacy",
            ignored=False,
        )
        para_legacy = ParagraphProjection(
            section="description",
            claim_num=None,
            paragraph_index=1,
            local_start=0,
            local_end=2,
            word_start=0,
            word_end=3,
            text="AB",
        )
        projections_legacy = ProjectionBundle(
            claims={},
            sections={"description": SectionProjection(section="description", claim_num=None, paragraphs=[para_legacy])},
        )
        with self.assertLogs("main", level="DEBUG") as cap:
            resolve_issue_range(_FakeDocWithFind("Valve"), issue_com, projections_com, strict=True)
            resolve_issue_range(_FakeDoc("A\x05B"), issue_legacy, projections_legacy, strict=True, allow_legacy_fallback=True)
        joined = "\n".join(cap.output)
        self.assertIn("resolve_path=word_find_com", joined)
        self.assertIn("resolve_path=word_find_legacy", joined)

    def test_com_find_loose_claims_still_requires_exact(self) -> None:
        doc = _FakeDocWithFind("A")
        paragraph = ParagraphProjection(
            section="claims",
            claim_num=1,
            paragraph_index=1,
            local_start=0,
            local_end=1,
            word_start=0,
            word_end=1,
            text="A",
        )
        resolved = range_resolver._resolve_via_com_find(  # type: ignore[attr-defined]
            doc,
            paragraph=paragraph,
            candidate="A",
            occurrence_idx=0,
            expected="AB",
            pre_context="",
            post_context="",
            strict=False,
            require_exact=True,
        )
        self.assertFalse(resolved.ok)
        self.assertEqual(str(resolved.reason_code), "word_find_mismatch")


if __name__ == "__main__":
    unittest.main()
