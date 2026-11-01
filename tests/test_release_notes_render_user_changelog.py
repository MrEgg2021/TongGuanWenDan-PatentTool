from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.release_notes import render_user_changelog


class ReleaseChangelogGuardTests(unittest.TestCase):
    def test_render_user_changelog_refuses_to_overwrite_manual_user_files(self) -> None:
        manifest = {
            "previous_user_version": "3.0",
            "previous_ref": "v3.0",
            "release_user_version": "3.1",
            "release_ref": "HEAD",
            "product_visible_version": "3.1",
            "git_tag": "v3.1.0",
            "quality_gates": [],
            "packaging_evidence": [],
            "included_commits": [],
            "included_changes": [],
            "excluded_internal_only_items": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "v3.1.0.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            exit_code = render_user_changelog.main(
                [
                    "--manifest",
                    str(manifest_path),
                    "--output-root",
                    tmpdir,
                ]
            )

            self.assertEqual(2, exit_code)
            changelog_path = Path(tmpdir) / "用户使用手册+更新日志" / "更新日志" / "v3.1.0.md"
            index_path = Path(tmpdir) / "用户使用手册+更新日志" / "更新日志.md"
            self.assertFalse(changelog_path.exists())
            self.assertFalse(index_path.exists())


if __name__ == "__main__":
    unittest.main()
