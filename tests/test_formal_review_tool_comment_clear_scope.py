import unittest

from core.formal_review.annotator import TOOL_COMMENT_PREFIX, clear_tool_comments, is_tool_comment


class _FakeRange:
    def __init__(self, text: str) -> None:
        self.Text = text


class _FakeComment:
    def __init__(self, text: str, owner: "_FakeComments") -> None:
        self.Range = _FakeRange(text)
        self._owner = owner

    def Delete(self) -> None:
        self._owner._rows.remove(self)


class _FakeComments:
    def __init__(self, texts: list[str]) -> None:
        self._rows = [_FakeComment(row, self) for row in texts]

    @property
    def Count(self) -> int:
        return len(self._rows)

    def __call__(self, idx: int) -> _FakeComment:
        return self._rows[int(idx) - 1]


class _FakeDoc:
    def __init__(self, texts: list[str]) -> None:
        self.Comments = _FakeComments(texts)


class FormalReviewToolCommentClearScopeTests(unittest.TestCase):
    def test_is_tool_comment_prefix(self) -> None:
        self.assertTrue(is_tool_comment(f"{TOOL_COMMENT_PREFIX}\n测试"))
        self.assertFalse(is_tool_comment("[人工批注]\n测试"))

    def test_clear_tool_comments_preserves_manual_comments(self) -> None:
        doc = _FakeDoc(
            [
                f"{TOOL_COMMENT_PREFIX}\nA",
                "[人工批注]\nB",
                f"{TOOL_COMMENT_PREFIX}\nC",
            ]
        )
        removed = clear_tool_comments(doc, prefix=TOOL_COMMENT_PREFIX)
        self.assertEqual(removed, 2)
        self.assertEqual(doc.Comments.Count, 1)
        self.assertEqual(doc.Comments(1).Range.Text, "[人工批注]\nB")


if __name__ == "__main__":
    unittest.main()
