from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]


def _openspec_validation_command(repo_root: Path) -> list[str] | None:
    """OpenSpec 校验命令；本地没有 openspec/ 时返回 None（该目录不随 Git 分发）。"""
    if not (repo_root / "openspec").is_dir():
        return None
    if os.name == "nt":
        return ["cmd", "/c", "openspec", "validate", "--all"]
    return ["openspec", "validate", "--all"]


def build_release_commands(repo_root: Path = REPO_ROOT, *, compiler: str = "msvc") -> list[list[str]]:
    py = sys.executable
    commands = [
        [py, "-m", "compileall", "-q", "."],
        [py, "-m", "ruff", "check", "."],
        [py, "tools/quality/pyflakes_gate.py", "gui_app.py", "core", "gui", "tools", "tests"],
        [py, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
        [py, "tools/check_text_encoding_integrity.py"],
        [py, "tools/check_pyinstaller_data_integrity.py"],
    ]
    openspec_cmd = _openspec_validation_command(repo_root)
    if openspec_cmd is None:
        print("[build_release_exes] openspec/ not found locally; skipping OpenSpec validation")
    else:
        commands.append(openspec_cmd)
    commands.extend(
        [
            [py, "tools/build_nuitka_pyd.py", "--profile", "full_core", "--output-root", "build/nuitka_pyd", "--compiler", compiler, "--clean"],
            ["pyinstaller", "--clean", "--noconfirm", "CPCXMLGui.spec"],
        ]
    )
    return commands


def _format_command(command: Sequence[str]) -> str:
    return subprocess.list2cmdline(list(command))


def run_release_commands(commands: Sequence[Sequence[str]], *, repo_root: Path = REPO_ROOT) -> None:
    for command in commands:
        print(f"[build_release_exes] {_format_command(command)}")
        completed = subprocess.run(list(command), cwd=str(repo_root))
        if completed.returncode != 0:
            raise SystemExit(
                f"command failed with exit code {completed.returncode}: {_format_command(command)}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the local Windows EXE release build chain with UPX disabled."
    )
    parser.add_argument(
        "--compiler",
        choices=("msvc", "mingw64"),
        default="msvc",
        help="Windows compiler backend for the Nuitka step: msvc (default) or mingw64.",
    )
    args = parser.parse_args(argv)

    print(f"[build_release_exes] repo root: {REPO_ROOT}")
    print("[build_release_exes] UPX disabled: no --upx-dir will be passed to PyInstaller")
    print(f"[build_release_exes] compiler: {args.compiler}")

    run_release_commands(build_release_commands(REPO_ROOT, compiler=str(args.compiler)), repo_root=REPO_ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
