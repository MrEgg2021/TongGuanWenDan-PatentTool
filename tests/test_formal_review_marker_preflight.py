import unittest

from core.formal_review.write_commands import WriteCommand
from core.formal_review.write_preflight import run_write_preflight


class _FakeRange:
    def __init__(self, text: str) -> None:
        self.Text = text


class _FakeDoc:
    def __init__(self, text: str) -> None:
        self._text = text

    def Range(self, start: int, end: int):  # noqa: N802 - COM style
        if start < 0 or end < start or end > len(self._text):
            raise ValueError("invalid range")
        return _FakeRange(self._text[start:end])


class FormalReviewMarkerPreflightTests(unittest.TestCase):
    def test_preflight_passes_when_all_fragments_match(self) -> None:
        doc = _FakeDoc("齿轮连接。")
        command = WriteCommand(
            cmd_id="cmd-1",
            action_kind="insert_after_name",
            section="claims",
            claim_num=1,
            name="齿轮",
            marker="10",
            local_start=2,
            local_end=2,
            word_start=2,
            word_end=2,
            expected_old_fragment="",
            replacement_text="（10）",
        )
        result = run_write_preflight(doc, [command])
        self.assertTrue(result.passed)
        self.assertEqual(result.checked_count, 1)
        self.assertEqual(result.failures, [])

    def test_preflight_fails_on_expected_mismatch(self) -> None:
        doc = _FakeDoc("齿轮(10)连接。")
        command = WriteCommand(
            cmd_id="cmd-2",
            action_kind="replace_marker_after_name",
            section="claims",
            claim_num=1,
            name="齿轮",
            marker="10",
            local_start=2,
            local_end=6,
            word_start=2,
            word_end=6,
            expected_old_fragment="（10）",
            replacement_text="（10）",
        )
        result = run_write_preflight(doc, [command])
        self.assertFalse(result.passed)
        self.assertEqual(result.checked_count, 1)
        self.assertEqual(len(result.failures), 1)
        self.assertIn("mismatch", result.failures[0].reason)

    def test_preflight_fails_when_name_anchor_not_at_word_start(self) -> None:
        doc = _FakeDoc("alpha valve body")
        command = WriteCommand(
            cmd_id="cmd-3",
            action_kind="insert_after_name",
            section="claims",
            claim_num=1,
            name="valve",
            marker="1",
            local_start=0,
            local_end=0,
            word_start=8,
            word_end=8,
            expected_old_fragment="",
            replacement_text="（1）",
        )
        result = run_write_preflight(doc, [command])
        self.assertFalse(result.passed)
        self.assertEqual(result.checked_count, 1)
        self.assertEqual(len(result.failures), 1)
        self.assertIn("name_anchor_mismatch", result.failures[0].reason)

    def test_preflight_passes_when_name_anchor_matches_word_start(self) -> None:
        doc = _FakeDoc("alpha valve body")
        command = WriteCommand(
            cmd_id="cmd-4",
            action_kind="insert_after_name",
            section="claims",
            claim_num=1,
            name="valve",
            marker="1",
            local_start=0,
            local_end=0,
            word_start=11,
            word_end=11,
            expected_old_fragment="",
            replacement_text="（1）",
        )
        result = run_write_preflight(doc, [command])
        self.assertTrue(result.passed)
        self.assertEqual(result.checked_count, 1)
        self.assertEqual(result.failures, [])


if __name__ == "__main__":
    unittest.main()
