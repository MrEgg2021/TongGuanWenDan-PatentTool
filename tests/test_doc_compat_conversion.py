from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.word_engine_impl.doc_ops import _save_legacy_doc_as_modern_docx, open_doc


class _FakeDoc:
    def __init__(
        self,
        *,
        convert_error: Exception | None = None,
        save_as2_error: Exception | None = None,
        compatibility_mode: int = 11,
        inline_shapes: int = 0,
        floating_shapes: int = 0,
        omaths: int = 0,
    ) -> None:
        self.CompatibilityMode = compatibility_mode
        self.convert_error = convert_error
        self.save_as2_error = save_as2_error
        self.convert_called = False
        self.save_as2_calls: list[dict] = []
        self.save_as_called = False
        self.closed: list[bool] = []
        self.Revisions = SimpleNamespace(Count=0)
        self.Comments = SimpleNamespace(Count=0)
        self.Fields = SimpleNamespace(Count=0)
        self.InlineShapes = SimpleNamespace(Count=inline_shapes)
        self.Shapes = SimpleNamespace(Count=floating_shapes)
        self.OMaths = SimpleNamespace(Count=omaths)

    def Convert(self) -> None:
        self.convert_called = True
        if self.convert_error is not None:
            raise self.convert_error
        self.CompatibilityMode = 15

    def SaveAs2(self, **kwargs) -> None:
        self.save_as2_calls.append(kwargs)
        if self.save_as2_error is not None:
            raise self.save_as2_error
        Path(str(kwargs["FileName"])).write_bytes(b"docx")

    def SaveAs(self, **_kwargs) -> None:
        self.save_as_called = True

    def Close(self, SaveChanges=False) -> None:  # noqa: N803 - COM style
        self.closed.append(bool(SaveChanges))


class _FakeDocuments:
    def __init__(self, reopen_doc: object) -> None:
        self.open_calls: list[dict] = []
        self.reopen_doc = reopen_doc

    def Open(self, **kwargs):
        self.open_calls.append(kwargs)
        return self.reopen_doc


class _FakeDocumentsSequence:
    def __init__(self, docs: list[object]) -> None:
        self.open_calls: list[dict] = []
        self.docs = list(docs)

    def Open(self, **kwargs):
        self.open_calls.append(kwargs)
        if not self.docs:
            raise AssertionError("unexpected Documents.Open call")
        return self.docs.pop(0)


def _fake_logger():
    return SimpleNamespace(info=lambda *_: None, warning=lambda *_: None, error=lambda *_: None)


class LegacyDocCompatConversionTests(unittest.TestCase):
    def test_legacy_doc_conversion_converts_saves_with_modern_compat_and_reopens_temp_docx(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = str(Path(td) / "legacy.doc")
            temp_docx = str(Path(td) / "temp_clean.docx")
            Path(source).write_bytes(b"legacy")
            source_doc = _FakeDoc(inline_shapes=2, floating_shapes=1)
            reopened = SimpleNamespace(
                FullName=temp_docx,
                CompatibilityMode=15,
                InlineShapes=SimpleNamespace(Count=2),
                Shapes=SimpleNamespace(Count=1),
                OMaths=SimpleNamespace(Count=0),
            )
            app = SimpleNamespace(DisplayAlerts=99, Documents=_FakeDocuments(reopened))
            engine = SimpleNamespace(app=app, doc=source_doc, _logger=SimpleNamespace(info=lambda *_: None, warning=lambda *_: None))

            result = _save_legacy_doc_as_modern_docx(engine, source, temp_docx)

        self.assertEqual(temp_docx, result)
        self.assertTrue(source_doc.convert_called)
        self.assertEqual(1, len(source_doc.save_as2_calls))
        self.assertEqual(12, source_doc.save_as2_calls[0]["FileFormat"])
        self.assertEqual(15, source_doc.save_as2_calls[0]["CompatibilityMode"])
        self.assertFalse(source_doc.save_as_called)
        self.assertEqual([False], source_doc.closed)
        self.assertIs(engine.doc, reopened)
        self.assertEqual(99, app.DisplayAlerts)
        self.assertEqual(temp_docx, app.Documents.open_calls[-1]["FileName"])
        self.assertFalse(app.Documents.open_calls[-1]["ReadOnly"])
        self.assertFalse(app.Documents.open_calls[-1]["Visible"])
        self.assertEqual(
            {"inline_shapes": 2, "floating_shapes": 1},
            engine._legacy_drawings_inventory["source"],
        )
        self.assertEqual(engine._legacy_drawings_inventory["source"], engine._legacy_drawings_inventory["reopened"])

    def test_legacy_doc_conversion_failure_does_not_plain_saveas_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = str(Path(td) / "legacy.doc")
            temp_docx = str(Path(td) / "temp_clean.docx")
            Path(source).write_bytes(b"legacy")
            source_doc = _FakeDoc(convert_error=RuntimeError("convert failed"))
            app = SimpleNamespace(DisplayAlerts=99, Documents=_FakeDocuments(SimpleNamespace()))
            engine = SimpleNamespace(app=app, doc=source_doc, _logger=SimpleNamespace(info=lambda *_: None, warning=lambda *_: None))

            with self.assertRaisesRegex(RuntimeError, "手动另存为 DOCX"):
                _save_legacy_doc_as_modern_docx(engine, source, temp_docx)

        self.assertTrue(source_doc.convert_called)
        self.assertFalse(source_doc.save_as_called)
        self.assertEqual([], source_doc.save_as2_calls)
        self.assertEqual(99, app.DisplayAlerts)

    def test_legacy_doc_saveas2_failure_is_explicit_without_plain_saveas_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = str(Path(td) / "legacy.doc")
            temp_docx = str(Path(td) / "temp_clean.docx")
            Path(source).write_bytes(b"legacy")
            source_doc = _FakeDoc(save_as2_error=RuntimeError("save failed"))
            app = SimpleNamespace(DisplayAlerts=99, Documents=_FakeDocuments(SimpleNamespace()))
            engine = SimpleNamespace(app=app, doc=source_doc, _logger=SimpleNamespace(info=lambda *_: None, warning=lambda *_: None))

            with self.assertRaisesRegex(RuntimeError, "手动另存为 DOCX"):
                _save_legacy_doc_as_modern_docx(engine, source, temp_docx)

        self.assertTrue(source_doc.convert_called)
        self.assertEqual(1, len(source_doc.save_as2_calls))
        self.assertEqual(12, source_doc.save_as2_calls[0]["FileFormat"])
        self.assertFalse(source_doc.save_as_called)
        self.assertEqual([], app.Documents.open_calls)
        self.assertEqual(99, app.DisplayAlerts)

    def test_docx_at_compat11_keeps_open_without_saveas_or_convert(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = str(Path(td) / "compat.docx")
            Path(source).write_bytes(b"compat docx")
            source_doc = _FakeDoc(compatibility_mode=11)
            docs = _FakeDocumentsSequence([source_doc])
            app = SimpleNamespace(DisplayAlerts=99, Documents=docs, Version="15.0")
            engine = SimpleNamespace(
                app=app,
                doc=None,
                version=15.0,
                config={"temp_dir": td},
                _logger=_fake_logger(),
                _runtime_guard_check=lambda: None,
                close_doc=lambda: None,
            )

            open_doc(engine, source)

        self.assertFalse(source_doc.convert_called)
        self.assertEqual([], source_doc.save_as2_calls)
        self.assertEqual([], source_doc.closed)
        self.assertIs(engine.doc, source_doc)
        self.assertEqual([source], [call["FileName"] for call in docs.open_calls])

    def test_word2010_docx_at_compat14_keeps_open_without_saveas_or_convert(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = str(Path(td) / "word2010.docx")
            Path(source).write_bytes(b"word 2010 docx")
            source_doc = _FakeDoc(compatibility_mode=14)
            docs = _FakeDocumentsSequence([source_doc])
            app = SimpleNamespace(DisplayAlerts=99, Documents=docs, Version="14.0")
            engine = SimpleNamespace(
                app=app,
                doc=None,
                version=14.0,
                config={"temp_dir": td},
                _logger=_fake_logger(),
                _runtime_guard_check=lambda: None,
                close_doc=lambda: None,
            )

            open_doc(engine, source)

        self.assertFalse(source_doc.convert_called)
        self.assertEqual([], source_doc.save_as2_calls)
        self.assertEqual([source], [call["FileName"] for call in docs.open_calls])
        self.assertIs(engine.doc, source_doc)

    def test_word2013_docx_at_compat14_keeps_open_without_saveas_or_convert(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = str(Path(td) / "word2010.docx")
            Path(source).write_bytes(b"word 2010 docx")
            source_doc = _FakeDoc(compatibility_mode=14)
            docs = _FakeDocumentsSequence([source_doc])
            app = SimpleNamespace(DisplayAlerts=99, Documents=docs, Version="15.0")
            engine = SimpleNamespace(
                app=app,
                doc=None,
                version=15.0,
                config={"temp_dir": td},
                _logger=_fake_logger(),
                _runtime_guard_check=lambda: None,
                close_doc=lambda: None,
            )

            open_doc(engine, source)

        self.assertFalse(source_doc.convert_called)
        self.assertEqual([], source_doc.save_as2_calls)
        self.assertIs(engine.doc, source_doc)
        self.assertEqual([source], [call["FileName"] for call in docs.open_calls])

    def test_word2007_docx_with_higher_compatibility_mode_keeps_open(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = str(Path(td) / "word2010.docx")
            Path(source).write_bytes(b"word 2010 docx")
            source_doc = _FakeDoc(compatibility_mode=14)
            docs = _FakeDocumentsSequence([source_doc])
            app = SimpleNamespace(DisplayAlerts=99, Documents=docs, Version="12.0")
            engine = SimpleNamespace(
                app=app,
                doc=None,
                version=12.0,
                config={"temp_dir": td},
                _logger=_fake_logger(),
                _runtime_guard_check=lambda: None,
                close_doc=lambda: None,
            )

            open_doc(engine, source)

        self.assertFalse(source_doc.convert_called)
        self.assertEqual([], source_doc.save_as2_calls)
        self.assertEqual([source], [call["FileName"] for call in docs.open_calls])
        self.assertIs(engine.doc, source_doc)

    def test_word2010_docx_at_compat15_keeps_open_without_version_guard(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = str(Path(td) / "modern.docx")
            Path(source).write_bytes(b"modern docx")
            source_doc = _FakeDoc(compatibility_mode=15)
            docs = _FakeDocumentsSequence([source_doc])
            app = SimpleNamespace(DisplayAlerts=99, Documents=docs, Version="14.0")
            engine = SimpleNamespace(
                app=app,
                doc=None,
                version=14.0,
                config={"temp_dir": td},
                _logger=_fake_logger(),
                _runtime_guard_check=lambda: None,
                close_doc=lambda: None,
            )

            open_doc(engine, source)

        self.assertFalse(source_doc.convert_called)
        self.assertEqual([], source_doc.save_as2_calls)
        self.assertEqual([source], [call["FileName"] for call in docs.open_calls])
        self.assertIs(engine.doc, source_doc)

    def test_docx_never_preprocess_saveas_across_word_versions_and_modes(self) -> None:
        cases = [
            ("12.0", 11),
            ("12.0", 14),
            ("12.0", 15),
            ("14.0", 11),
            ("14.0", 14),
            ("14.0", 15),
            ("15.0", 11),
            ("15.0", 14),
            ("15.0", 15),
        ]
        for version, compatibility_mode in cases:
            with self.subTest(version=version, compatibility_mode=compatibility_mode):
                with tempfile.TemporaryDirectory() as td:
                    source = str(Path(td) / f"v{version}-m{compatibility_mode}.docx")
                    Path(source).write_bytes(b"docx")
                    source_doc = _FakeDoc(compatibility_mode=compatibility_mode)
                    docs = _FakeDocumentsSequence([source_doc])
                    engine = SimpleNamespace(
                        app=SimpleNamespace(DisplayAlerts=99, Documents=docs, Version=version),
                        doc=None,
                        version=float(version),
                        config={"temp_dir": td},
                        _logger=_fake_logger(),
                        _runtime_guard_check=lambda: None,
                        close_doc=lambda: None,
                    )

                    open_doc(engine, source)

                self.assertFalse(source_doc.convert_called)
                self.assertEqual([], source_doc.save_as2_calls)
                self.assertEqual([source], [call["FileName"] for call in docs.open_calls])
                self.assertIs(engine.doc, source_doc)

    def test_modern_docx_keeps_open_without_saveas_or_convert(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = str(Path(td) / "modern.docx")
            Path(source).write_bytes(b"modern docx")
            source_doc = _FakeDoc(compatibility_mode=15)
            docs = _FakeDocumentsSequence([source_doc])
            app = SimpleNamespace(DisplayAlerts=99, Documents=docs)
            engine = SimpleNamespace(
                app=app,
                doc=None,
                config={"temp_dir": td},
                _logger=_fake_logger(),
                _runtime_guard_check=lambda: None,
                close_doc=lambda: None,
            )

            open_doc(engine, source)

        self.assertFalse(source_doc.convert_called)
        self.assertEqual([], source_doc.save_as2_calls)
        self.assertEqual(1, len(docs.open_calls))
        self.assertIs(engine.doc, source_doc)


if __name__ == "__main__":
    unittest.main()
