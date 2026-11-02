from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tools import build_release_exes


class BuildReleaseExesTests(unittest.TestCase):
    def test_build_release_commands_do_not_include_upx_options(self) -> None:
        commands = build_release_exes.build_release_commands()
        self.assertIn([build_release_exes.sys.executable, "-m", "ruff", "check", "."], commands)
        self.assertTrue(any("tools/quality/pyflakes_gate.py" in command for command in commands))
        pyinstaller_commands = [command for command in commands if command and command[0] == "pyinstaller"]

        self.assertEqual(1, len(pyinstaller_commands))
        self.assertEqual(["pyinstaller", "--clean", "--noconfirm", "CPCXMLGui.spec"], pyinstaller_commands[0])

        flattened = [part for command in pyinstaller_commands for part in command]
        self.assertNotIn("--upx-dir", flattened)
        self.assertNotIn("--upx-path", flattened)
        self.assertNotIn("--noupx", flattened)

    def test_build_release_commands_pass_compiler_backend(self) -> None:
        commands = build_release_exes.build_release_commands(compiler="mingw64")
        nuitka_commands = [command for command in commands if any("build_nuitka_pyd.py" in part for part in command)]

        self.assertEqual(1, len(nuitka_commands))
        self.assertEqual("mingw64", nuitka_commands[0][nuitka_commands[0].index("--compiler") + 1])

    def test_build_release_commands_skip_openspec_when_directory_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            commands = build_release_exes.build_release_commands(Path(tmp))

        self.assertFalse(any("openspec" in " ".join(command) for command in commands))
        self.assertTrue(any("build_nuitka_pyd.py" in " ".join(command) for command in commands))
        self.assertTrue(any(command[0] == "pyinstaller" for command in commands))

    def test_build_release_commands_include_openspec_when_directory_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "openspec").mkdir()
            commands = build_release_exes.build_release_commands(Path(tmp))

        openspec_commands = [command for command in commands if "openspec" in " ".join(command)]
        expected = (
            ["cmd", "/c", "openspec", "validate", "--all"]
            if os.name == "nt"
            else ["openspec", "validate", "--all"]
        )
        self.assertEqual([expected], openspec_commands)

    def test_main_rejects_removed_upx_path_argument(self) -> None:
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                build_release_exes.main(["--upx-path", "C:/upx/upx.exe"])

        self.assertEqual(2, ctx.exception.code)

    def test_run_release_commands_uses_repo_root_as_cwd(self) -> None:
        repo_root = Path("D:/demo/repo")
        commands = [["python", "-V"], ["pyinstaller", "--version"]]

        with patch(
            "tools.build_release_exes.subprocess.run",
            side_effect=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0),
        ) as run_mock:
            build_release_exes.run_release_commands(commands, repo_root=repo_root)

        self.assertEqual(2, run_mock.call_count)
        for call in run_mock.call_args_list:
            self.assertEqual(str(repo_root), call.kwargs["cwd"])


if __name__ == "__main__":
    unittest.main()
