from __future__ import annotations

import unittest

from core.formal_review.marker_rules import _looks_like_revision_applied


class _FakeRevisionRange:
    def __init__(self, text: str):
        self.Text = text


class _FakeRevision:
    def __init__(self, rev_type: int, text: str):
        self.Type = int(rev_type)
        self.Range = _FakeRevisionRange(text)


class _FakeRevisions:
    def __init__(self, rows: list[_FakeRevision]):
        self._rows = list(rows or [])
        self.Count = len(self._rows)

    def __call__(self, idx: int):
        return self._rows[int(idx) - 1]


class _FakeRange:
    def __init__(self, rows: list[_FakeRevision]):
        self.Revisions = _FakeRevisions(rows)


class _FakeDoc:
    def __init__(self, rows: list[_FakeRevision]):
        self._rows = list(rows or [])

    def Range(self, _start: int, _end: int):
        return _FakeRange(self._rows)


class MarkerRevisionIdempotencyTests(unittest.TestCase):
    def test_target_prefix_plus_revisions_is_treated_as_already_applied(self):
        doc = _FakeDoc([_FakeRevision(1, "5"), _FakeRevision(2, "6")])
        self.assertTrue(
            _looks_like_revision_applied(
                doc=doc,
                name_end=100,
                suffix_text="56",
                old_fragment="56",
                replacement="5",
            )
        )

    def test_no_revisions_does_not_short_circuit(self):
        doc = _FakeDoc([])
        self.assertFalse(
            _looks_like_revision_applied(
                doc=doc,
                name_end=100,
                suffix_text="56",
                old_fragment="56",
                replacement="5",
            )
        )

    def test_old_plus_new_with_insert_revision_is_treated_as_applied(self):
        doc = _FakeDoc([_FakeRevision(1, "（3）"), _FakeRevision(2, "（2）")])
        self.assertTrue(
            _looks_like_revision_applied(
                doc=doc,
                name_end=200,
                suffix_text="（3）（2）",
                old_fragment="（3）（2）",
                replacement="（3）",
            )
        )


if __name__ == "__main__":
    unittest.main()

