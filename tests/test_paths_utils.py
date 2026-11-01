from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import paths_utils
from core.paths_utils import _ensure_writable_dir


class PathsUtilsTests(unittest.TestCase):
    def test_machine_storage_uses_writable_order_without_authorization_probes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            program_data = str(Path(directory) / "program-data")
            public_docs = str(Path(directory) / "public-documents")
            user_data = str(Path(directory) / "user-data")
            with (
                patch.object(paths_utils, "_get_windows_common_appdata", return_value=program_data),
                patch.object(paths_utils, "_get_windows_common_documents", return_value=public_docs),
                patch.object(paths_utils, "get_user_data_dir", return_value=user_data),
                patch.object(paths_utils, "_ensure_writable_dir", side_effect=[False, True]) as writable,
                patch.object(paths_utils.os.path, "isfile", side_effect=AssertionError("must not probe state files")),
            ):
                self.assertEqual(str(Path(public_docs) / "CPC-XML-Converter"), paths_utils.get_machine_data_dir())
            self.assertEqual([
                str(Path(program_data) / "CPC-XML-Converter"),
                str(Path(public_docs) / "CPC-XML-Converter"),
            ], [call.args[0] for call in writable.call_args_list])

    def test_ensure_writable_dir_does_not_use_fixed_probe_name(self) -> None:
        source = Path("core/paths_utils.py").read_text(encoding="utf-8")

        self.assertNotIn(".__write_probe__", source)

    def test_ensure_writable_dir_does_not_leave_probe_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "data"

            self.assertTrue(_ensure_writable_dir(str(target)))

            self.assertTrue(target.is_dir())
            self.assertFalse((target / ".__write_probe__").exists())
            self.assertEqual([], [p.name for p in target.iterdir()])


if __name__ == "__main__":
    unittest.main()
