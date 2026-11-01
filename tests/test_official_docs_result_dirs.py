import unittest

from core.official_docs.models import ProcessItemResult, ProcessSummary
try:
    from gui.main_window.mixins.official_docs_mixin import OfficialDocsMixin

    _GUI_AVAILABLE = True
except Exception:
    OfficialDocsMixin = object  # type: ignore
    _GUI_AVAILABLE = False


class _DummyOfficialDocs(OfficialDocsMixin):
    pass


@unittest.skipUnless(_GUI_AVAILABLE, "requires PySide6")
class OfficialDocsResultDirsTests(unittest.TestCase):
    def test_collect_done_dirs_includes_run_and_success_archive_dirs(self) -> None:
        dummy = _DummyOfficialDocs.__new__(_DummyOfficialDocs)
        dummy._init_official_docs_state()

        summary = ProcessSummary(
            summary_run_dir="D:/output/run_001",
            items=[
                ProcessItemResult(source_zip_path="a.zip", status="success", archive_pdf_path="D:/archive/A/doc1.pdf"),
                ProcessItemResult(source_zip_path="b.zip", status="skip", archive_pdf_path="D:/archive/B/doc2.pdf"),
                ProcessItemResult(source_zip_path="c.zip", status="fail", archive_pdf_path="D:/archive/C/doc3.pdf"),
                ProcessItemResult(source_zip_path="d.zip", status="success", archive_pdf_path="D:/archive/A/doc4.pdf"),
            ],
        )
        dirs = dummy._collect_done_dirs(summary)
        self.assertEqual(dirs[0], "D:/output/run_001")
        self.assertIn("D:/archive/A", dirs)
        self.assertNotIn("D:/archive/B", dirs)
        self.assertNotIn("D:/archive/C", dirs)
        self.assertEqual(dirs.count("D:/archive/A"), 1)

    def test_collect_done_dirs_normalizes_mixed_separators_and_deduplicates(self) -> None:
        dummy = _DummyOfficialDocs.__new__(_DummyOfficialDocs)
        dummy._init_official_docs_state()

        summary = ProcessSummary(
            summary_run_dir=r"D:\output\run_001",
            items=[
                ProcessItemResult(source_zip_path="a.zip", status="success", archive_pdf_path=r"D:\archive\A\doc1.pdf"),
                ProcessItemResult(source_zip_path="b.zip", status="success", archive_pdf_path="D:/archive/A/doc2.pdf"),
            ],
        )
        dirs = dummy._collect_done_dirs(summary)
        self.assertEqual(dirs[0], "D:/output/run_001")
        self.assertEqual(dirs.count("D:/archive/A"), 1)


if __name__ == "__main__":
    unittest.main()
