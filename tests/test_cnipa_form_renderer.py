from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.cnipa_preview.form_renderer import FormRenderCancelled, _classpath, render_opinion_pdf
from core.cnipa_preview.runtime import RuntimeLayout


class FormRendererTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.layout = RuntimeLayout("test", self.root)
        self.layout.wrapper_config.parent.mkdir(parents=True)
        self.layout.wrapper_config.write_text(
            "wrapper.java.classpath.2=%COMMONS_HOME%/lib/poi.jar\n"
            "wrapper.java.classpath.1=%APP_HOME%/conf\n", encoding="utf-8",
        )
        self.xml = self.root / "100012.xml"
        self.xml.write_text("<意见陈述书/>", encoding="utf-8")

    def test_classpath_preserves_numbered_order_and_rejects_unknown_variables(self):
        cp = _classpath(self.layout)
        self.assertLess(cp.index("conf"), cp.index("poi.jar"))
        self.assertNotIn("%", cp)
        self.layout.wrapper_config.write_text("wrapper.java.classpath.1=%OTHER%/x.jar", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "未识别变量"):
            _classpath(self.layout)

    def test_absent_section_is_passed_as_empty_and_pdf_is_checked(self):
        process = Mock(returncode=0)
        process.poll.return_value = 0
        def spawn(command, **kwargs):
            self.assertEqual(command[-2], "")
            self.assertEqual(Path(command[0]).parents[5], self.layout.client_root)
            Path(command[-1]).write_bytes(b"%PDF-1.7\ncomplete")
            return process
        with patch("core.cnipa_preview.form_renderer.subprocess.Popen", side_effect=spawn):
            self.assertEqual(render_opinion_pdf(self.layout, self.xml), b"%PDF-1.7\ncomplete")
        process.kill.assert_not_called()

    def test_cancellation_and_timeout_kill_and_reap_helper(self):
        for timeout, check, error in (
            (120, Mock(side_effect=[False, True]), FormRenderCancelled),
            (0, None, TimeoutError),
        ):
            with self.subTest(error=error):
                process = Mock()
                process.poll.return_value = None
                with patch("core.cnipa_preview.form_renderer.subprocess.Popen", return_value=process):
                    with self.assertRaises(error):
                        render_opinion_pdf(self.layout, self.xml, cancelled=check, timeout_seconds=timeout)
                process.kill.assert_called_once()
                process.wait.assert_called_once()

    def test_nonzero_exit_does_not_return_partial_pdf(self):
        process = Mock(returncode=1)
        process.poll.return_value = 1
        with patch("core.cnipa_preview.form_renderer.subprocess.Popen", return_value=process):
            with self.assertRaisesRegex(RuntimeError, "退出码 1"):
                render_opinion_pdf(self.layout, self.xml)

    def test_multiple_section_files_fail_before_launch(self):
        self.xml.with_name("section_2.xml").write_bytes(b"<cn-other-file/>")
        with patch("core.cnipa_preview.form_renderer.subprocess.Popen") as spawn:
            with self.assertRaisesRegex(RuntimeError, "多个 section"):
                render_opinion_pdf(self.layout, self.xml)
            spawn.assert_not_called()
