from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from core.config import get_app_display_title, load_config
from tools.cli_main import build_parser


class ReleaseVersion100ContractTests(unittest.TestCase):
    def test_runtime_and_package_version_strings_align_to_100(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        expected_snippets = [
            ("resources/config.yaml", 'version: "1.0.0"'),
            ("resources/version_info_gui.txt", 'StringStruct("FileVersion", "1.0.0")'),
            ("resources/version_info_gui.txt", 'StringStruct("OriginalFilename", "通官文旦-专利工具_v1.0.0.exe")'),
        ]

        for relative_path, expected in expected_snippets:
            text = (repo_root / relative_path).read_text(encoding="utf-8")
            self.assertIn(expected, text, f"missing expected version snippet in {relative_path}")

        self.assertIn("filevers=(1, 0, 0, 0)", (repo_root / "resources/version_info_gui.txt").read_text(encoding="utf-8"))
        self.assertIn("prodvers=(1, 0, 0, 0)", (repo_root / "resources/version_info_gui.txt").read_text(encoding="utf-8"))
        self.assertIn(f"V{load_config()['version']}", get_app_display_title())

    def test_cli_title_uses_configured_version_and_free_identity(self) -> None:
        with patch("core.config.load_config", return_value={"version": "9.8.7"}):
            self.assertEqual("通官文旦-专利工具 V9.8.7", build_parser().description)

    def test_manual_v100_references_current_release(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        manual_text = (repo_root / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8")

        self.assertIn("适用版本：V1.0.0", manual_text)
        readme_text = (repo_root / "README.md").read_text(encoding="utf-8")
        for text in (manual_text, readme_text):
            self.assertIn("1649251313@qq.com", text)
            self.assertIn("MrEgg208", text)

    def test_packaging_contains_only_main_application(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        module_sets = json.loads((repo_root / "tools/nuitka_module_sets.json").read_text(encoding="utf-8"))
        self.assertEqual({"full_core"}, set(module_sets))
        self.assertIn("core/app_preferences.py", module_sets["full_core"]["include"])
        self.assertFalse((repo_root / "CPCXMLKeygen.spec").exists())


if __name__ == "__main__":
    unittest.main()
