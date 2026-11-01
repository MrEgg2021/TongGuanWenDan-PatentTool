from __future__ import annotations

import unittest
from pathlib import Path


class SingleRunRequestFormOverlaySuspendWiringTests(unittest.TestCase):
    def test_single_run_pauses_overlay_before_preflight_request_form(self) -> None:
        source = Path("gui/single_run.py").read_text(encoding="utf-8")
        self.assertIn(
            "paused_processing_overlay_for_request_form = False",
            source,
        )
        self.assertIn(
            'logger.info("[SINGLE_RUN] processing_overlay_paused_for_request_form file=%s", str(input_path))',
            source,
        )
        self.assertIn(
            "ctx = prepare_single_run_context(window, input_path, config_path=config_path)",
            source,
        )

    def test_single_run_resumes_overlay_only_after_valid_ctx(self) -> None:
        source = Path("gui/single_run.py").read_text(encoding="utf-8")
        self.assertIn("if ctx is None:", source)
        self.assertIn("return", source)
        self.assertIn("if paused_processing_overlay_for_request_form:", source)
        self.assertIn(
            'logger.info("[SINGLE_RUN] processing_overlay_resumed_after_request_form file=%s", str(input_path))',
            source,
        )
        self.assertIn(
            'window.update_progress(0, "正在准备转换...", "页眉检测完成，正在准备后台转换...")',
            source,
        )


if __name__ == "__main__":
    unittest.main()
