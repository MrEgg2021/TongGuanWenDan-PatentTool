from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from core.cnipa_preview.models import PreviewRenderResult
from gui.tools_ui_impl.preview_impl.worker import PreviewRenderWorker


class PreviewRenderWorkerTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.source = Path(directory.name) / "case.zip"
        self.source.write_bytes(b"sample")

    def test_worker_reports_progress_and_returns_renderer_result(self) -> None:
        result = PreviewRenderResult()
        statuses: list[str] = []
        progress: list[tuple[int, int, str]] = []
        completed: list[object] = []
        test_case = self

        class _Renderer:
            def __init__(self, _service) -> None:
                pass

            def render_case(self, _zip_path, *, documents, selected_document_ids, progress, cancelled, startup_wait):
                if cancelled():
                    raise AssertionError("worker unexpectedly reported cancellation")
                test_case.assertIsNone(documents)
                test_case.assertIsNone(selected_document_ids)
                startup_wait(12.0)
                progress(0, 2, "权利要求书")
                progress(2, 2, "")
                return result

        class _ColdManager:
            @staticmethod
            def is_running() -> bool:
                return False

        worker = PreviewRenderWorker(str(self.source))
        worker.status.connect(statuses.append)
        worker.progress.connect(lambda done, total, name: progress.append((done, total, name)))
        worker.completed.connect(completed.append)
        with (
            patch("gui.tools_ui_impl.preview_impl.worker.CnipaXmlRenderer", _Renderer),
            patch("gui.tools_ui_impl.preview_impl.worker.get_default_runtime_manager", return_value=_ColdManager()),
        ):
            worker.run()

        self.assertTrue(statuses)
        self.assertIn("首次加载", statuses[0])
        self.assertIn("12", statuses[1])
        self.assertEqual([(0, 2, "权利要求书"), (2, 2, "")], progress)
        self.assertEqual([result], completed)

    def test_worker_labels_a_healthy_manager_as_already_started(self) -> None:
        result = PreviewRenderResult()
        statuses: list[str] = []

        class _Renderer:
            def __init__(self, _service) -> None:
                pass

            def render_case(self, *_args, **_kwargs):
                return result

        class _WarmManager:
            @staticmethod
            def is_running() -> bool:
                return True

        worker = PreviewRenderWorker(str(self.source))
        worker.status.connect(statuses.append)
        with (
            patch("gui.tools_ui_impl.preview_impl.worker.CnipaXmlRenderer", _Renderer),
            patch("gui.tools_ui_impl.preview_impl.worker.get_default_runtime_manager", return_value=_WarmManager()),
        ):
            worker.run()

        self.assertEqual(["正在连接已启动的全量预览官方渲染器……"], statuses)


if __name__ == "__main__":
    unittest.main()
