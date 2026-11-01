from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.release_notes import prepare_release_manifest


class ReleaseManifestGenerationTests(unittest.TestCase):
    def test_prepare_manifest_cli_writes_expected_release_metadata(self) -> None:
        commits = [
            {
                "hash": "1111111",
                "subject": "fix(response-correction): correct document slot mappings",
                "changed_files": ["core/response_correction/package_builder.py"],
            },
            {
                "hash": "2222222",
                "subject": "test(quality): add boundary hardening gates",
                "changed_files": ["tests/test_ci_quality_gate.py"],
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "v3.1.0.json"
            with (
                patch("tools.release_notes.prepare_release_manifest.collect_release_commits", return_value=commits),
                patch(
                    "tools.release_notes.prepare_release_manifest.resolve_ref",
                    side_effect=["previous-commit", "release-commit"],
                ),
            ):
                exit_code = prepare_release_manifest.main(
                    [
                        "--previous-ref",
                        "v3.0",
                        "--release-ref",
                        "HEAD",
                        "--release-version",
                        "3.1",
                        "--git-tag",
                        "v3.1.0",
                        "--output",
                        str(output_path),
                    ]
                )

            self.assertEqual(0, exit_code)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual("v3.0", payload["previous_ref"])
            self.assertEqual("HEAD", payload["release_ref"])
            self.assertEqual("3.0", payload["previous_user_version"])
            self.assertEqual("3.1", payload["release_user_version"])
            self.assertEqual("3.1", payload["product_visible_version"])
            self.assertEqual("v3.1.0", payload["git_tag"])
            self.assertEqual(
                ["test(quality): add boundary hardening gates"],
                payload["excluded_internal_only_items"],
            )
            self.assertEqual(
                ["fix(response-correction): correct document slot mappings"],
                [entry["subject"] for entry in payload["included_commits"]],
            )
            self.assertEqual([], payload["quality_gates"])
            self.assertEqual([], payload["packaging_evidence"])

    def test_prepare_manifest_cli_loads_quality_and_packaging_evidence_files(self) -> None:
        commits = [
            {
                "hash": "1111111",
                "subject": "fix(conversion): handle compatibility docx drawings fallback",
                "changed_files": ["core/word_engine_impl/doc_ops.py"],
            }
        ]

        quality_gates = [
            {"command": "python -m compileall -q .", "ok": True, "note": "passed"},
            {"command": 'python -m unittest discover -s tests -p "test_*.py"', "ok": True},
        ]
        packaging_evidence = [
            {"command": "pyinstaller --clean --noconfirm --upx-dir C:/upx CPCXMLGui.spec", "ok": True}
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            output_path = tmp_path / "v3.1.0.json"
            quality_path = tmp_path / "quality.json"
            packaging_path = tmp_path / "packaging.json"
            quality_path.write_text(json.dumps(quality_gates, ensure_ascii=False), encoding="utf-8")
            packaging_path.write_text(json.dumps(packaging_evidence, ensure_ascii=False), encoding="utf-8")

            with (
                patch("tools.release_notes.prepare_release_manifest.collect_release_commits", return_value=commits),
                patch(
                    "tools.release_notes.prepare_release_manifest.resolve_ref",
                    side_effect=["previous-commit", "release-commit"],
                ),
            ):
                exit_code = prepare_release_manifest.main(
                    [
                        "--previous-ref",
                        "v3.0",
                        "--release-ref",
                        "HEAD",
                        "--release-version",
                        "3.1",
                        "--git-tag",
                        "v3.1.0",
                        "--quality-gates-file",
                        str(quality_path),
                        "--packaging-evidence-file",
                        str(packaging_path),
                        "--output",
                        str(output_path),
                    ]
                )

            self.assertEqual(0, exit_code)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(quality_gates, payload["quality_gates"])
            self.assertEqual(packaging_evidence, payload["packaging_evidence"])
