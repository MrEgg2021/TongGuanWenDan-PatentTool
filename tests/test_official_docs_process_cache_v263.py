from __future__ import annotations

import unittest

from core.official_docs.models import ProcessItemResult, ProcessSummary
from gui.main_window.mixins.official_docs_ops.process_ops import _cache_official_docs_process_results


class _DummyWindow:
    def __init__(self) -> None:
        self._official_docs_leaves = {
            "leaf-1": {
                "id": "leaf-1",
                "zip_path": "D:/temp/leaf-1.zip",
                "display_name": "A.pdf",
            }
        }
        self._official_docs_last_process_leaf_ids = ["leaf-1"]

    def _init_official_docs_state(self) -> None:
        return None

    def _find_leaf_id_by_zip_path(self, _zip_path: str) -> str:
        return ""


class OfficialDocsProcessCacheV263Tests(unittest.TestCase):
    def test_cache_uses_last_process_leaf_order_when_source_zip_is_readable_label(self) -> None:
        window = _DummyWindow()
        summary = ProcessSummary(
            total=1,
            success=1,
            items=[
                ProcessItemResult(
                    source_zip_path="outer.zip > A.pdf",
                    status="success",
                    output_pdf_name="done.pdf",
                    summary_pdf_path="D:/summary/done.pdf",
                    archive_pdf_path="D:/archive/done.pdf",
                )
            ],
        )

        _cache_official_docs_process_results(window, summary)

        payload = window._official_docs_leaves["leaf-1"].get("last_result")
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["output_pdf_name"], "done.pdf")
        self.assertEqual(payload["summary_pdf_path"], "D:/summary/done.pdf")


if __name__ == "__main__":
    unittest.main()
