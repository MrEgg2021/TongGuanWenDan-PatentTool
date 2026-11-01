import unittest
from unittest.mock import patch

from core.formal_review.annotator import CommentTargetFailure, preflight_comment_targets
from core.formal_review.models import Issue


class FormalReviewCommentSyncLooseRecoveryTests(unittest.TestCase):
    def _build_issue(self) -> Issue:
        return Issue(
            rule_id="wordlist.description.sensitive",
            severity="medium",
            category="sensitive",
            section="description",
            message="说明书中出现敏感词：\"避免\"",
            span_start=10,
            span_end=12,
            snippet="避免",
            issue_id="i-1",
            anchor={"expected_hit": "避免", "word_range_start": 100},
            ignored=False,
        )

    def test_preflight_recovers_with_loose_fallback(self) -> None:
        issue = self._build_issue()
        strict_fail = type(
            "_R",
            (),
            {
                "ok": False,
                "level": "fail",
                "reason_code": "word_find_mismatch",
                "detail": "strict mismatch",
                "reason": "strict mismatch",
            },
        )()
        loose_ok = type("_R", (), {"ok": True, "level": "word_find_com", "start": 120, "end": 122})()

        with patch("core.formal_review.annotator.resolve_issue_range", side_effect=[strict_fail, loose_ok]):
            data = preflight_comment_targets(
                object(),
                issues=[issue],
                allow_loose_fallback=True,
            )

        self.assertEqual(int(data.get("strict_failed", 0)), 1)
        self.assertEqual(int(data.get("loose_rescued", 0)), 1)
        self.assertEqual(int(data.get("final_failed", 0)), 0)
        self.assertEqual(int(dict(data.get("strict_level_hist", {})).get("fail", 0)), 1)
        self.assertEqual(int(dict(data.get("loose_level_hist", {})).get("word_find_com", 0)), 1)
        self.assertEqual(int(dict(data.get("resolver_path_hist", {})).get("word_find_com", 0)), 1)
        self.assertEqual(int(dict(data.get("resolver_reason_hist", {})).get("word_find_mismatch", 0)), 1)
        targets = list(data.get("targets", []) or [])
        self.assertEqual(len(targets), 1)
        self.assertEqual(str(getattr(targets[0], "resolve_mode", "")), "loose")

    def test_preflight_without_loose_keeps_failure(self) -> None:
        issue = self._build_issue()
        strict_fail = type(
            "_R",
            (),
            {
                "ok": False,
                "level": "fail",
                "reason_code": "word_find_mismatch",
                "detail": "strict mismatch",
                "reason": "strict mismatch",
            },
        )()
        with patch("core.formal_review.annotator.resolve_issue_range", return_value=strict_fail):
            data = preflight_comment_targets(
                object(),
                issues=[issue],
                allow_loose_fallback=False,
            )

        self.assertEqual(int(data.get("strict_failed", 0)), 1)
        self.assertEqual(int(data.get("loose_rescued", 0)), 0)
        self.assertEqual(int(data.get("final_failed", 0)), 1)
        self.assertEqual(int(dict(data.get("strict_level_hist", {})).get("fail", 0)), 1)
        self.assertEqual(dict(data.get("loose_level_hist", {})), {})
        self.assertEqual(int(dict(data.get("resolver_reason_hist", {})).get("word_find_mismatch", 0)), 1)
        self.assertEqual(len(list(data.get("targets", []) or [])), 0)
        failures = list(data.get("failures", []) or [])
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], CommentTargetFailure)


if __name__ == "__main__":
    unittest.main()
