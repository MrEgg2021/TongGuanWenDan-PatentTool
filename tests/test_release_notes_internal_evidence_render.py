from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.release_notes import render_internal_evidence


class ReleaseInternalEvidenceRenderingTests(unittest.TestCase):
    def test_render_internal_evidence_writes_only_internal_report(self) -> None:
        manifest = {
            "previous_user_version": "3.0",
            "previous_ref": "v3.0",
            "release_user_version": "3.1",
            "release_ref": "HEAD",
            "product_visible_version": "3.1",
            "git_tag": "v3.1.0",
            "quality_gates": [
                {"command": "python -m compileall -q .", "ok": True, "note": "passed"}
            ],
            "packaging_evidence": [
                {"command": "pyinstaller CPCXMLGui.spec", "ok": True, "note": "passed"}
            ],
            "included_commits": [
                {
                    "hash": "1111111",
                    "subject": "fix(conversion): handle compatibility docx drawings fallback",
                    "changed_files": ["core/word_engine_impl/doc_ops.py"],
                }
            ],
            "included_changes": ["legacy-doc-compat-conversion"],
            "excluded_internal_only_items": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "v3.1.0.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            exit_code = render_internal_evidence.main(
                [
                    "--manifest",
                    str(manifest_path),
                    "--output-root",
                    tmpdir,
                ]
            )

            self.assertEqual(0, exit_code)
            internal_path = Path(tmpdir) / "docs" / "release_notes" / "internal_evidence" / "v3.1.0.internal.md"
            changelog_path = Path(tmpdir) / "用户使用手册+更新日志" / "更新日志" / "v3.1.0.md"
            index_path = Path(tmpdir) / "用户使用手册+更新日志" / "更新日志.md"

            self.assertTrue(internal_path.exists())
            self.assertFalse(changelog_path.exists())
            self.assertFalse(index_path.exists())

            internal_text = internal_path.read_text(encoding="utf-8")
            self.assertIn("# v3.1.0 Internal Evidence", internal_text)
            self.assertIn("## Quality Gates", internal_text)
            self.assertIn("## Packaging Evidence", internal_text)


if __name__ == "__main__":
    unittest.main()
