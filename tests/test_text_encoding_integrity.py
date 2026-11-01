from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import check_text_encoding_integrity as checker


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TextEncodingIntegrityTests(unittest.TestCase):
    def test_default_target_files_include_root_workspace_text_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_text(root / "AGENTS.md", "# rules\n")
            _write_text(root / "README.md", "# readme\n")
            _write_text(root / "settings.json", "{}\n")
            _write_text(root / "config.yaml", "name: demo\n")
            _write_text(root / "bootstrap.ps1", "Write-Host 'ok'\n")
            _write_text(root / ".editorconfig", "root = true\n")
            _write_text(root / ".vscode" / "settings.json", "{\n  \"files.encoding\": \"utf8\"\n}\n")
            _write_text(root / "core" / "sample.py", "print('ok')\n")

            files = checker.iter_target_files(
                root,
                checker.DEFAULT_INCLUDE_GLOBS,
                checker.DEFAULT_EXCLUDE_GLOBS,
            )

        rel_paths = {path.relative_to(root).as_posix() for path in files}
        self.assertIn("AGENTS.md", rel_paths)
        self.assertIn("README.md", rel_paths)
        self.assertIn("settings.json", rel_paths)
        self.assertIn("config.yaml", rel_paths)
        self.assertIn("bootstrap.ps1", rel_paths)
        self.assertIn(".editorconfig", rel_paths)
        self.assertIn(".vscode/settings.json", rel_paths)
        self.assertIn("core/sample.py", rel_paths)

    def test_main_flags_root_agents_file_with_illegal_control_char(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_text(root / "AGENTS.md", "good\nbad\0line\n")
            _write_text(root / "tools" / "text_encoding_allowlist.txt", "")
            stdout = io.StringIO()

            with patch("sys.argv", ["check_text_encoding_integrity.py", "--root", str(root)]):
                with contextlib.redirect_stdout(stdout):
                    code = checker.main()

        self.assertEqual(code, 1)
        output = stdout.getvalue()
        self.assertIn("AGENTS.md", output)
        self.assertIn("illegal_control_char", output)

    def test_main_flags_vscode_settings_file_with_illegal_control_char(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_text(root / ".vscode" / "settings.json", "{\0}\n")
            _write_text(root / "tools" / "text_encoding_allowlist.txt", "")
            stdout = io.StringIO()

            with patch("sys.argv", ["check_text_encoding_integrity.py", "--root", str(root)]):
                with contextlib.redirect_stdout(stdout):
                    code = checker.main()

        self.assertEqual(code, 1)
        output = stdout.getvalue()
        self.assertIn(".vscode/settings.json", output)
        self.assertIn("illegal_control_char", output)


if __name__ == "__main__":
    unittest.main()
