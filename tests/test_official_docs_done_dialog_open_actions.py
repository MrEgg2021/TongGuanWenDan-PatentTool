from __future__ import annotations

import unittest
from pathlib import Path
from gui_source_loader import read_official_docs_dialogs_source


class OfficialDocsDoneDialogOpenActionsTests(unittest.TestCase):
    def test_open_selected_file_prefers_generated_pdf_target(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_dialogs_source(repo_root)
        self.assertIn('str(payload.get("summary_pdf_path", "") or "").strip()', text)
        self.assertIn('str(payload.get("archive_pdf_path", "") or "").strip()', text)
        self.assertIn('str(payload.get("source_zip_path", "") or "").strip()', text)
        self.assertNotIn('if status_key == "success":', text)
        self.assertIn("for target in targets:", text)
        self.assertIn("if target and _safe_startfile(target):", text)

    def test_open_run_dir_prefers_current_run_dir(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_dialogs_source(repo_root)
        self.assertIn('primary_run_dir = str(run_dir or "").strip() or (dirs[0] if dirs else "")', text)
        self.assertIn("def _open_run_dir() -> None:", text)
        self.assertIn("if target and _safe_startfile(target):", text)


if __name__ == "__main__":
    unittest.main()
