import unittest

from core.formal_review.write_commands import WriteCommand
from core.formal_review.write_executor import apply_write_commands


class _FakeUndoRecord:
    def __init__(self) -> None:
        self.started = 0
        self.ended = 0

    def StartCustomRecord(self, _title):  # noqa: N802 - COM style
        self.started += 1

    def EndCustomRecord(self):  # noqa: N802 - COM style
        self.ended += 1


class _FakeRevisions:
    def __init__(self) -> None:
        self.Count = 0


class _FakeApp:
    def __init__(self, doc) -> None:
        self._doc = doc
        self.UndoRecord = _FakeUndoRecord()
        self.undo_called = 0

    def Undo(self):  # noqa: N802 - COM style
        self.undo_called += 1
        self._doc._text = self._doc._before_last_write


class _FakeRange:
    def __init__(self, doc, start: int, end: int) -> None:
        self._doc = doc
        self._start = int(start)
        self._end = int(end)

    @property
    def Text(self):  # noqa: N802 - COM style
        return self._doc._text[self._start : self._end]

    @Text.setter
    def Text(self, value):  # noqa: N802 - COM style
        replacement = str(value or "")
        self._doc._before_last_write = self._doc._text
        self._doc._text = self._doc._text[: self._start] + replacement + self._doc._text[self._end :]
        self._end = self._start + len(replacement)
        if bool(getattr(self._doc, "TrackRevisions", False)):
            self._doc.Revisions.Count += 1


class _FakeDoc:
    def __init__(self, text: str) -> None:
        self._text = text
        self._before_last_write = text
        self.Revisions = _FakeRevisions()
        self.Application = _FakeApp(self)
        self.TrackRevisions = False

    def Range(self, start: int, end: int):  # noqa: N802 - COM style
        if start < 0 or end < start or end > len(self._text):
            raise ValueError("invalid range")
        return _FakeRange(self, start, end)


class FormalReviewWriteAtomicCommitTests(unittest.TestCase):
    def test_apply_write_commands_success(self) -> None:
        doc = _FakeDoc("齿轮(10)连接")
        cmd = WriteCommand(
            cmd_id="cmd-1",
            action_kind="replace_marker_after_name",
            section="claims",
            claim_num=1,
            name="齿轮",
            marker="10",
            local_start=2,
            local_end=6,
            word_start=2,
            word_end=6,
            expected_old_fragment="(10)",
            replacement_text="（10）",
        )
        report = apply_write_commands(doc, commands=[cmd], enforce_track_revisions=True)
        self.assertTrue(report.committed)
        self.assertEqual(report.applied_count, 1)
        self.assertTrue(doc.TrackRevisions)
        self.assertGreater(int(doc.Revisions.Count), 0)
        self.assertEqual(doc._text, "齿轮（10）连接")

    def test_apply_write_commands_fails_on_expected_mismatch_and_zero_commit(self) -> None:
        doc = _FakeDoc("齿轮(10)连接")
        cmd = WriteCommand(
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
        report = apply_write_commands(doc, commands=[cmd], enforce_track_revisions=True)
        self.assertFalse(report.committed)
        self.assertEqual(report.applied_count, 0)
        self.assertIn("expected", "\n".join(report.errors))
        self.assertEqual(doc._text, "齿轮(10)连接")


if __name__ == "__main__":
    unittest.main()
