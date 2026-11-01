from __future__ import annotations

import unittest
from unittest.mock import patch

from core.word_startup_health import _finish_bound_word_health, _probe_word_pdf_export


class _FakeRange:
    Text = ""


class _FakeDocument:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.closed = False

    def Range(self, _start, _end):
        return _FakeRange()

    def ExportAsFixedFormat(self, *, OutputFileName, ExportFormat):
        assert ExportFormat == 17
        if self.mode == "raise":
            raise RuntimeError("此功能尚未安装")
        if self.mode == "missing":
            return
        payload = b"%PDF-1.7\n" if self.mode == "valid" else b"not-a-pdf"
        with open(OutputFileName, "wb") as output:
            output.write(payload)

    def Close(self, *, SaveChanges):
        assert SaveChanges == 0
        self.closed = True


class _FakeDocuments:
    def __init__(self, document: _FakeDocument) -> None:
        self.document = document

    def Add(self, **_kwargs):
        return self.document


class _FakeApp:
    Version = "16.0"

    def __init__(self, mode: str = "valid") -> None:
        self.document = _FakeDocument(mode)
        self.Documents = _FakeDocuments(self.document)
        self.quit_calls = 0

    def Quit(self, *, SaveChanges):
        assert SaveChanges == 0
        self.quit_calls += 1


class WordPdfExportHealthTests(unittest.TestCase):
    def test_probe_accepts_valid_pdf_and_closes_document(self) -> None:
        app = _FakeApp("valid")

        ok, error = _probe_word_pdf_export(app)

        self.assertTrue(ok)
        self.assertEqual("", error)
        self.assertTrue(app.document.closed)

    def test_probe_reports_com_failure_and_closes_document(self) -> None:
        app = _FakeApp("raise")

        ok, error = _probe_word_pdf_export(app)

        self.assertFalse(ok)
        self.assertIn("此功能尚未安装", error)
        self.assertTrue(app.document.closed)

    def test_probe_rejects_missing_or_invalid_output(self) -> None:
        for mode, expected in (("missing", "did not create"), ("invalid", "invalid PDF")):
            with self.subTest(mode=mode):
                app = _FakeApp(mode)
                ok, error = _probe_word_pdf_export(app)
                self.assertFalse(ok)
                self.assertIn(expected, error)
                self.assertTrue(app.document.closed)

    def test_health_default_does_not_run_pdf_probe(self) -> None:
        app = _FakeApp()
        with patch("core.word_startup_health._probe_word_pdf_export") as probe:
            result = _finish_bound_word_health(
                app,
                {},
                result_pid=42,
                expected_pid=None,
                wait_target=None,
                killed_before_check=False,
                exit_timeout=1.0,
                slow_exit_timeout=1.0,
                progress_callback=None,
            )

        probe.assert_not_called()
        self.assertTrue(result.ok)
        self.assertIsNone(result.pdf_export_ok)

    def test_opt_in_probe_failure_keeps_word_health_successful(self) -> None:
        app = _FakeApp()
        with patch(
            "core.word_startup_health._probe_word_pdf_export",
            return_value=(False, "feature unavailable"),
        ):
            result = _finish_bound_word_health(
                app,
                {},
                result_pid=42,
                expected_pid=None,
                wait_target=None,
                killed_before_check=False,
                exit_timeout=1.0,
                slow_exit_timeout=1.0,
                progress_callback=None,
                check_pdf_export=True,
            )

        self.assertTrue(result.ok)
        self.assertFalse(result.pdf_export_ok)
        self.assertEqual("feature unavailable", result.pdf_export_error)


if __name__ == "__main__":
    unittest.main()
