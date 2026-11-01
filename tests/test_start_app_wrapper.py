from __future__ import annotations

import unittest
from unittest.mock import patch

from core.word_engine_impl.start_app_impl import start_app


class StartAppWrapperTests(unittest.TestCase):
    def test_start_app_runs_hooks_and_returns_dispatch_result(self) -> None:
        engine = object()

        def faq(message):
            return message

        with (
            patch("core.word_engine_impl.start_app_impl.run_start_app_preflight") as mock_pre,
            patch("core.word_engine_impl.start_app_impl.start_app_dispatch_flow", return_value="ok") as mock_dispatch,
            patch("core.word_engine_impl.start_app_impl.run_start_app_post_setup") as mock_post,
            patch("core.word_engine_impl.start_app_impl.record_start_app_ownership") as mock_owner,
        ):
            result = start_app(engine, faq)

        self.assertEqual(result, "ok")
        mock_pre.assert_called_once_with(engine)
        mock_dispatch.assert_called_once_with(engine, faq)
        mock_post.assert_called_once_with(engine)
        mock_owner.assert_called_once_with(engine)


if __name__ == "__main__":
    unittest.main()
