import unittest

from core.formal_review.write_commands import WriteCommand
from core.formal_review.write_executor import apply_write_commands


class _FakeRevisions:
    def __init__(self) -> None:
        self.Count = 0


class _FakeUndoRecord:
    def __init__(self) -> None:
        self.started = 0
        self.ended = 0

    def StartCustomRecord(self, _title):  # noqa: N802
        self.started += 1

    def EndCustomRecord(self):  # noqa: N802
        self.ended += 1


class _FakeApp:
    def __init__(self, doc) -> None:
        self._doc = doc
        self.UndoRecord = _FakeUndoRecord()
        self.undo_called = 0
        self.ActiveWindow = None

    def Undo(self):  # noqa: N802
        self.undo_called += 1
        self._doc._text = self._doc._before_last_write


class _FakeRange:
    def __init__(self, doc, start: int, end: int) -> None:
        self._doc = doc
        self._start = int(start)
        self._end = int(end)

    @property
    def Text(self):  # noqa: N802
        return self._doc._text[self._start : self._end]

    @Text.setter
    def Text(self, value):  # noqa: N802
        replacement = str(value or "")
        self._doc._before_last_write = self._doc._text
        self._doc._text = self._doc._text[: self._start] + replacement + self._doc._text[self._end :]
        self._end = self._start + len(replacement)
        if bool(self._doc._track_revisions) and bool(self._doc._increment_revisions):
            self._doc.Revisions.Count += 1


class _FakeDoc:
    def __init__(self, text: str, *, track_available: bool = True, increment_revisions: bool = True) -> None:
        self._text = text
        self._before_last_write = text
        self._track_available = bool(track_available)
        self._track_revisions = False
        self._increment_revisions = bool(increment_revisions)
        self.Revisions = _FakeRevisions()
        self.Application = _FakeApp(self)

    @property
    def TrackRevisions(self):  # noqa: N802
        return bool(self._track_revisions)

    @TrackRevisions.setter
    def TrackRevisions(self, value):  # noqa: N802
        if bool(self._track_available):
            self._track_revisions = bool(value)
        else:
            self._track_revisions = False

    def Range(self, start: int, end: int):  # noqa: N802
        start = int(start)
        end = int(end)
        if start < 0 or end < start or end > len(self._text):
            raise ValueError("invalid range")
        return _FakeRange(self, start, end)


def _sample_cmd() -> WriteCommand:
    return WriteCommand(
        cmd_id="c1",
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


class FormalReviewWriteExecutorRevisionGuardTests(unittest.TestCase):
    def test_track_revisions_unavailable_blocks_commit(self) -> None:
        doc = _FakeDoc("齿轮(10)连接", track_available=False)
        report = apply_write_commands(doc, commands=[_sample_cmd()], enforce_track_revisions=True)
        self.assertFalse(report.committed)
        self.assertIn("修订模式未生效", "\n".join(report.errors))
        self.assertEqual(doc._text, "齿轮(10)连接")

    def test_no_revision_growth_blocks_and_rolls_back(self) -> None:
        doc = _FakeDoc("齿轮(10)连接", track_available=True, increment_revisions=False)
        report = apply_write_commands(doc, commands=[_sample_cmd()], enforce_track_revisions=True)
        self.assertFalse(report.committed)
        self.assertIn("未检测到修订痕迹增长", "\n".join(report.errors))
        self.assertEqual(doc.Application.undo_called, 1)
        self.assertEqual(doc._text, "齿轮(10)连接")

    def test_revision_growth_allows_commit(self) -> None:
        doc = _FakeDoc("齿轮(10)连接", track_available=True, increment_revisions=True)
        report = apply_write_commands(doc, commands=[_sample_cmd()], enforce_track_revisions=True)
        self.assertTrue(report.committed)
        self.assertGreater(int(doc.Revisions.Count), 0)
        self.assertEqual(doc._text, "齿轮（10）连接")


if __name__ == "__main__":
    unittest.main()
