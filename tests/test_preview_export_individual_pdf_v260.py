from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.cnipa_preview.models import PreviewDocument
from gui.main_window.mixins.preview_export_impl import ops_impl


class PreviewExportIndividualPdfV260Tests(unittest.TestCase):
    def test_opens_generated_preview_with_windows_file_association(self) -> None:
        with patch.object(ops_impl.os, "startfile", create=True) as startfile:
            ops_impl._open_preview_with_system_viewer(r"C:\temp\official_preview.pdf")

        startfile.assert_called_once_with(r"C:\temp\official_preview.pdf")

    def test_display_order_controls_selected_document_order(self) -> None:
        class _Window:
            _preview_last_zip_path = "case.zip"
            _preview_export_selections = {"case.zip": {"doc-claims", "doc-abstract"}}
            _preview_pdf_map = {"doc-claims": b"claims", "doc-abstract": b"abstract"}
            _preview_documents = (
                PreviewDocument("doc-abstract", "100004", "说明书摘要", "abstract.xml"),
                PreviewDocument("doc-claims", "100001", "权利要求书", "claims.xml"),
            )

        window = _Window()
        self.assertEqual(
            ops_impl._selected_document_ids_in_display_order(window, require_pdf=True),
            ["doc-abstract", "doc-claims"],
        )

    def test_exports_selected_individual_pdfs_with_cn_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = Path(tmpdir) / "案件A_预览合并.pdf"
            exported, errors = ops_impl._export_selected_preview_pdfs(
                dest_path=str(merged_path),
                base_name="案件A",
                selected_document_ids=["doc-claims", "doc-abstract"],
                pdf_map={
                    "doc-claims": b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
                    "doc-description": b"ignored",
                    "doc-abstract": b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
                },
                labels_by_document_id={"doc-claims": "权利要求书", "doc-abstract": "说明书摘要"},
            )

            self.assertEqual(
                [Path(path).name for path in exported],
                ["案件A_权利要求书.pdf", "案件A_说明书摘要.pdf"],
            )
            self.assertEqual(errors, [])
            self.assertTrue((Path(tmpdir) / "案件A_权利要求书.pdf").exists())
            self.assertTrue((Path(tmpdir) / "案件A_说明书摘要.pdf").exists())
            self.assertFalse((Path(tmpdir) / "案件A_说明书.pdf").exists())

    def test_reports_individual_export_failures_without_stopping(self) -> None:
        writes: list[str] = []

        def _fake_writer(path: str, data: bytes) -> None:
            writes.append(Path(path).name)
            if path.endswith("说明书.pdf"):
                raise OSError("disk full")

        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = Path(tmpdir) / "案件A_预览合并.pdf"
            exported, errors = ops_impl._export_selected_preview_pdfs(
                dest_path=str(merged_path),
                base_name="案件A",
                selected_document_ids=["doc-claims", "doc-description"],
                pdf_map={
                    "doc-claims": b"a",
                    "doc-description": b"b",
                },
                labels_by_document_id={"doc-claims": "权利要求书", "doc-description": "说明书"},
                write_bytes=_fake_writer,
            )

            self.assertEqual(exported, [str(Path(tmpdir) / "案件A_权利要求书.pdf")])
            self.assertEqual(len(errors), 1)
            self.assertIn("案件A_说明书.pdf", errors[0])
            self.assertIn("disk full", errors[0])
            self.assertEqual(writes, ["案件A_权利要求书.pdf", "案件A_说明书.pdf"])


if __name__ == "__main__":
    unittest.main()
