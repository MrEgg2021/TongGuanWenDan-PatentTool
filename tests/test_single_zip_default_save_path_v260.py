from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path

from gui.single_run_impl import save_flow


class SingleZipDefaultSavePathV260Tests(unittest.TestCase):
    def test_prefers_input_document_directory_over_last_saved_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            last_dir = root / "last"
            input_dir = root / "input"
            last_dir.mkdir()
            input_dir.mkdir()
            window = SimpleNamespace(_last_single_saved_zip_path=str(last_dir / "old.zip"))

            path = save_flow._build_default_save_path(
                window,
                input_path=str(input_dir / "说明书.docx"),
                safe_name="发明-标题.zip",
            )

            self.assertEqual(path, str(input_dir / "发明-标题.zip"))


if __name__ == "__main__":
    unittest.main()
