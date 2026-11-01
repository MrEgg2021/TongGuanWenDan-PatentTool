from __future__ import annotations

import unittest
from unittest.mock import patch

from core.word_startup_health import WordStartupHealthResult


class _FakePythonCom:
    def __init__(self) -> None:
        self.initialized = 0
        self.uninitialized = 0

    def CoInitialize(self) -> None:  # noqa: N802 - pywin32 API
        self.initialized += 1

    def CoUninitialize(self) -> None:  # noqa: N802 - pywin32 API
        self.uninitialized += 1


class WordHealthWorkerTests(unittest.TestCase):
    def test_worker_initializes_com_and_forwards_progress(self) -> None:
        from gui.word_health_worker import WordHealthWorker

        fake_com = _FakePythonCom()
        captured_kwargs: dict = {}

        def _health_check(**kwargs):
            captured_kwargs.update(kwargs)
            progress_callback = kwargs.get("progress_callback")
            self.assertTrue(callable(progress_callback))
            progress_callback("start_word", {"message": "starting"})
            progress_callback("slow_exit_wait", {"message": "slow"})
            return WordStartupHealthResult(
                ok=True,
                pid=42,
                binding_progid="Word.Application.16",
                error=None,
                killed_before_check=bool(kwargs.get("killed_before_check")),
            )

        worker = WordHealthWorker(killed_before_check=True, health_check=_health_check)
        progress_events: list[tuple[int, str, str]] = []
        finished: list[WordStartupHealthResult] = []
        worker.progress.connect(lambda percent, primary, detail: progress_events.append((percent, primary, detail)))
        worker.finished.connect(lambda result: finished.append(result))

        with patch("gui.word_health_worker.pythoncom", fake_com):
            worker.run()

        self.assertEqual(1, fake_com.initialized)
        self.assertEqual(1, fake_com.uninitialized)
        self.assertTrue(captured_kwargs["killed_before_check"])
        self.assertEqual(2, len(progress_events))
        self.assertTrue(any("Word" in event[1] for event in progress_events))
        self.assertEqual(1, len(finished))
        self.assertTrue(finished[0].ok)


if __name__ == "__main__":
    unittest.main()
