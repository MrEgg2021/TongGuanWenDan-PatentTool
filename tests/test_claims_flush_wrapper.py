from __future__ import annotations

import unittest
from unittest.mock import patch

from core.document_parser.claims_mixin_impl import ClaimsMixin


class ClaimsFlushWrapperTests(unittest.TestCase):
    def test_flush_pending_claim_delegates_to_impl_with_constant(self) -> None:
        obj = ClaimsMixin()
        parent_node = {}

        with patch("core.document_parser.claims_mixin_impl.flush_pending_claim_impl", return_value="done") as mock_impl:
            result = obj._flush_pending_claim(parent_node, force=True)

        self.assertEqual(result, "done")
        self.assertEqual(mock_impl.call_count, 1)
        args, kwargs = mock_impl.call_args
        self.assertIs(args[0], obj)
        self.assertIs(args[1], parent_node)
        self.assertEqual(kwargs.get("force"), True)
        self.assertEqual(kwargs.get("claim_text_break_kind"), "__claim_text_break__")


if __name__ == "__main__":
    unittest.main()
