from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.check_pyinstaller_data_integrity import find_lfs_pointer_data_inputs, iter_pyinstaller_data_sources


class PyInstallerDataIntegrityTests(unittest.TestCase):
    def test_extracts_literal_analysis_data_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            spec = Path(tmpdir) / "app.spec"
            spec.write_text("a = Analysis(['app.py'], datas=[('resources/a.bin', 'resources')])\n", encoding="utf-8")
            self.assertEqual(["resources/a.bin"], list(iter_pyinstaller_data_sources(spec)))

    def test_detects_lfs_pointer_but_ignores_regular_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            resources = root / "resources"
            resources.mkdir()
            pointer = resources / "pointer.bin"
            pointer.write_text(
                "version https://git-lfs.github.com/spec/v1\noid sha256:" + "0" * 64 + "\nsize 123\n",
                encoding="utf-8",
            )
            (resources / "regular.bin").write_bytes(b"regular")
            spec = root / "app.spec"
            spec.write_text(
                "a = Analysis(['app.py'], datas=[('resources/pointer.bin', 'resources'), ('resources/regular.bin', 'resources')])\n",
                encoding="utf-8",
            )

            self.assertEqual([pointer], find_lfs_pointer_data_inputs([spec], repo_root=root))


if __name__ == "__main__":
    unittest.main()
