import unittest
from pathlib import Path


class ResultSheetFallbackNoticeWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def _read(self, rel: str) -> str:
        return (self.repo_root / rel).read_text(encoding="utf-8")

    def test_result_sheet_modal_accepts_notice_text_and_renders_notice_block(self) -> None:
        text = self._read("gui/ui_modals.py")
        required = [
            "def build_result_sheet_modal(",
            "notice_text: str | None = None",
            'notice = str(notice_text or "").strip()',
            'notice_box.setObjectName("ResultNoticeBox")',
            'notice_body.setObjectName("ResultNoticeBody")',
        ]
        missing = [snippet for snippet in required if snippet not in text]
        self.assertFalse(missing, "Missing modal wiring snippets:\n" + "\n".join(missing))

    def test_progress_overlay_accepts_and_forwards_notice_text(self) -> None:
        text = self._read("gui/main_window/mixins/progress_mixin.py")
        required = [
            "def _show_result_overlay(",
            "notice_text: str | None = None",
            "build_result_sheet_modal(",
            "notice_text=notice_text",
        ]
        missing = [snippet for snippet in required if snippet not in text]
        self.assertFalse(missing, "Missing progress wiring snippets:\n" + "\n".join(missing))

    def test_single_path_removes_legacy_default_invention_notice(self) -> None:
        text = self._read("gui/single_run_impl/postprocess_flow.py")
        self.assertNotIn("默认按“发明内容”小标题处理", text)
        self.assertNotIn("FALLBACK_NOTICE_CORE", text)

    def test_batch_path_removes_legacy_default_invention_notice(self) -> None:
        text = self._read("gui/batch_run_impl/finalize_flow.py")
        self.assertNotIn("默认按“发明内容”小标题处理", text)
        self.assertNotIn("FALLBACK_NOTICE_CORE", text)


if __name__ == "__main__":
    unittest.main()
