from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class LoggingUtilsFilePolicyTests(unittest.TestCase):
    def _run_probe(
        self,
        *,
        frozen: bool,
        app_dir: Path | None = None,
        user_dir: Path | None = None,
    ) -> dict[str, object]:
        repo_root = Path(__file__).resolve().parents[1]
        code = textwrap.dedent(
            """
            import json
            import logging
            import sys
            from pathlib import Path

            import core.paths_utils as paths

            app_dir = Path(sys.argv[1])
            user_dir = Path(sys.argv[2])
            frozen = sys.argv[3] == "1"

            paths.get_app_dir = lambda: str(app_dir)
            paths.get_user_data_dir = lambda: str(user_dir)

            if frozen:
                sys.frozen = True

            import core.logging_utils as logging_utils
            logging_utils.logger.info("logger line from probe")
            logging_utils.logger.debug("debug logger line from probe")
            sys.stderr.write("raw stderr from probe\\n")

            log_path = logging_utils.get_conversion_log_path()
            payload = {
                "current_log_path": getattr(logging_utils, "_CURRENT_LOG_PATH", None),
                "reported_log_path": log_path,
                "stdio_capture_installed": getattr(logging_utils, "_STDIO_CAPTURE_INSTALLED", None),
                "root_has_file_handler": any(
                    isinstance(h, logging.FileHandler) for h in logging.getLogger().handlers
                ),
                "app_log_exists": (app_dir / "conversion.log").exists(),
                "user_log_exists": (user_dir / "conversion.log").exists(),
                "log_has_logger_line": False,
                "log_has_debug_line": False,
                "log_has_raw_stderr": False,
                "log_has_session_marker": False,
            }
            if log_path:
                for handler in logging.getLogger().handlers:
                    try:
                        handler.flush()
                    except Exception:
                        pass
                text = Path(log_path).read_text(encoding="utf-8", errors="replace")
                payload["log_has_logger_line"] = "logger line from probe" in text
                payload["log_has_debug_line"] = "debug logger line from probe" in text
                payload["log_has_raw_stderr"] = "raw stderr from probe" in text
                payload["log_has_session_marker"] = "[DIAGNOSTIC_SESSION_START]" in text
            print(json.dumps(payload, ensure_ascii=False))
            """
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_dir = Path(app_dir) if app_dir is not None else root / "app"
            user_dir = Path(user_dir) if user_dir is not None else root / "user"
            app_dir.mkdir(parents=True, exist_ok=True)
            user_dir.mkdir(parents=True, exist_ok=True)

            proc = subprocess.run(
                [sys.executable, "-c", code, str(app_dir), str(user_dir), "1" if frozen else "0"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=True,
            )

        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        return json.loads(lines[-1])

    def test_dev_mode_writes_log_file(self) -> None:
        payload = self._run_probe(frozen=False)

        self.assertTrue(payload["root_has_file_handler"])
        self.assertTrue(payload["stdio_capture_installed"])
        self.assertTrue(payload["app_log_exists"])
        self.assertFalse(payload["user_log_exists"])
        self.assertEqual(payload["current_log_path"], payload["reported_log_path"])
        self.assertTrue(str(payload["reported_log_path"]).endswith("conversion.log"))
        self.assertTrue(payload["log_has_logger_line"])
        self.assertTrue(payload["log_has_debug_line"])
        self.assertTrue(payload["log_has_raw_stderr"])
        self.assertTrue(payload["log_has_session_marker"])

    def test_frozen_mode_also_writes_log_file(self) -> None:
        payload = self._run_probe(frozen=True)

        self.assertTrue(payload["root_has_file_handler"])
        self.assertTrue(payload["stdio_capture_installed"])
        self.assertTrue(payload["app_log_exists"])
        self.assertEqual(payload["current_log_path"], payload["reported_log_path"])
        self.assertTrue(str(payload["reported_log_path"]).endswith("conversion.log"))
        self.assertTrue(payload["log_has_logger_line"])
        self.assertTrue(payload["log_has_debug_line"])
        self.assertTrue(payload["log_has_raw_stderr"])
        self.assertTrue(payload["log_has_session_marker"])

    def test_second_session_appends_and_keeps_history_without_nul_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_dir = root / "app"
            user_dir = root / "user"
            app_dir.mkdir()
            user_dir.mkdir()

            self._run_probe(frozen=False, app_dir=app_dir, user_dir=user_dir)
            self._run_probe(frozen=False, app_dir=app_dir, user_dir=user_dir)

            raw = (app_dir / "conversion.log").read_bytes()
            self.assertNotIn(b"\x00", raw)
            self.assertGreaterEqual(raw.count(b"[DIAGNOSTIC_SESSION_START]"), 2)

    def test_oversized_log_is_rotated_at_startup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_dir = root / "app"
            user_dir = root / "user"
            app_dir.mkdir()
            user_dir.mkdir()
            log_path = app_dir / "conversion.log"
            log_path.write_bytes(b"OLD-SESSION" + b"x" * (5 * 1024 * 1024))

            self._run_probe(frozen=False, app_dir=app_dir, user_dir=user_dir)

            backup = app_dir / "conversion.log.1"
            self.assertTrue(backup.exists())
            self.assertTrue(backup.read_bytes().startswith(b"OLD-SESSION"))
            raw = log_path.read_bytes()
            self.assertNotIn(b"\x00", raw)
            self.assertNotIn(b"OLD-SESSION", raw)
            self.assertIn(b"[DIAGNOSTIC_SESSION_START]", raw)


if __name__ == "__main__":
    unittest.main()
