import unittest

from core.formal_review.companion_client import inspect_doc_clean_state


class _Counter:
    def __init__(self, count: int):
        self.Count = count


class _Doc:
    def __init__(self, *, saved: bool, track_revisions: bool, revisions: int, comments: int):
        self.Saved = saved
        self.TrackRevisions = track_revisions
        self.Revisions = _Counter(revisions)
        self.Comments = _Counter(comments)


class _BrokenDoc:
    @property
    def Saved(self):
        raise RuntimeError("boom")


class FormalReviewCompanionCleanGateTests(unittest.TestCase):
    def test_clean_state_is_clean_when_all_conditions_pass(self) -> None:
        state = inspect_doc_clean_state(_Doc(saved=True, track_revisions=False, revisions=0, comments=0))
        self.assertTrue(state.is_clean)
        self.assertEqual(state.errors, [])

    def test_clean_state_is_not_clean_when_any_condition_fails(self) -> None:
        state = inspect_doc_clean_state(_Doc(saved=True, track_revisions=True, revisions=0, comments=0))
        self.assertFalse(state.is_clean)

    def test_clean_state_records_errors_when_properties_unreadable(self) -> None:
        state = inspect_doc_clean_state(_BrokenDoc())
        self.assertFalse(state.is_clean)
        self.assertTrue(state.errors)


if __name__ == "__main__":
    unittest.main()

