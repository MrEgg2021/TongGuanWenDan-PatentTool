from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import qt_i18n


class _DummyLogger:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warnings: list[str] = []

    def info(self, msg: str, *args) -> None:
        self.infos.append(msg % args if args else msg)

    def warning(self, msg: str, *args) -> None:
        self.warnings.append(msg % args if args else msg)


class _DummyApp:
    def __init__(self, install_ok: bool = True) -> None:
        self._install_ok = bool(install_ok)
        self.installed = []

    def installTranslator(self, translator) -> bool:
        self.installed.append(translator)
        return bool(self._install_ok)


class _FakeTranslator:
    def __init__(self, _app) -> None:
        self.loaded = []

    def load(self, path: str) -> bool:
        self.loaded.append(path)
        return True


class QtI18nHelperV251Tests(unittest.TestCase):
    def test_install_success_with_qtbase_zh_cn(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            qm = root / "qtbase_zh_CN.qm"
            qm.write_bytes(b"dummy")
            app = _DummyApp(install_ok=True)
            logger = _DummyLogger()

            with patch.object(qt_i18n.QLibraryInfo, "path", return_value=str(root)), patch.object(
                qt_i18n, "QTranslator", _FakeTranslator
            ):
                ok = qt_i18n.install_qt_zh_translator(app, logger=logger)

            self.assertTrue(ok)
            self.assertEqual(len(app.installed), 1)
            self.assertTrue(hasattr(app, "_qt_runtime_translators"))
            self.assertIn("installed translator", " | ".join(logger.infos))

    def test_missing_qm_is_warning_and_non_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            app = _DummyApp(install_ok=True)
            logger = _DummyLogger()
            with patch.object(qt_i18n.QLibraryInfo, "path", return_value=str(tmpdir)), patch.object(
                qt_i18n, "QTranslator", _FakeTranslator
            ):
                ok = qt_i18n.install_qt_zh_translator(app, logger=logger)
            self.assertFalse(ok)
            self.assertEqual(len(app.installed), 0)
            self.assertTrue(logger.warnings)


if __name__ == "__main__":
    unittest.main()
