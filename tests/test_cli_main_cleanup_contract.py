import subprocess
import sys
import unittest
from pathlib import Path

from core.template_export import export_template
from tools import cli_main


REPO_ROOT = Path(__file__).resolve().parents[1]


class CliMainCleanupContractTests(unittest.TestCase):
    def test_cli_reuses_canonical_template_export(self) -> None:
        self.assertIs(cli_main.export_template, export_template)

    def test_cli_does_not_define_a_duplicate_document_parser(self) -> None:
        self.assertFalse(hasattr(cli_main, "DocumentParser"))

    def test_cli_parser_exposes_template_export_option(self) -> None:
        option_strings = {
            option
            for action in cli_main.build_parser()._actions
            for option in action.option_strings
        }
        self.assertIn("--export-template", option_strings)

    def test_cli_script_can_run_from_repository_root(self) -> None:
        completed = subprocess.run(
            [sys.executable, "tools/cli_main.py", "--help"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
