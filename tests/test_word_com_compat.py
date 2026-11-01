from __future__ import annotations

import unittest

from core.word_engine_impl.com_compat import add_hidden_document


class _FakeDocuments:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def Add(self, **kwargs):  # noqa: N802 - COM style
        self.calls.append(dict(kwargs))
        if "Visible" in kwargs:
            raise TypeError("Visible is not supported")
        return "doc"


class WordComCompatTests(unittest.TestCase):
    def test_add_hidden_document_retries_without_visible_argument(self) -> None:
        docs = _FakeDocuments()
        result = add_hidden_document(type("App", (), {"Documents": docs})())

        self.assertEqual("doc", result)
        self.assertEqual([{"Visible": False}, {}], docs.calls)


if __name__ == "__main__":
    unittest.main()
