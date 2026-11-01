from __future__ import annotations

import unittest
import unicodedata

from core.config import sanitize_filename


class SanitizeFilenameTests(unittest.TestCase):
    def test_replaces_control_and_path_separators(self) -> None:
        self.assertEqual("a_b c_d", sanitize_filename("a/b\r\nc:d"))
        self.assertNotIn("\0", sanitize_filename("bad\0name"))

    def test_windows_reserved_device_names_are_made_safe(self) -> None:
        for raw in ("CON", "con", "NUL.txt", "COM1", "LPT9.docx"):
            with self.subTest(raw=raw):
                cleaned = sanitize_filename(raw)

            stem = cleaned.rsplit(".", 1)[0].upper()
            self.assertNotIn(stem, {"CON", "PRN", "AUX", "NUL", "COM1", "LPT9"})

    def test_trims_windows_trailing_dots_and_spaces_after_cleanup(self) -> None:
        self.assertEqual("report", sanitize_filename("report. "))
        self.assertEqual("output", sanitize_filename("...   "))

    def test_normalizes_unicode_to_nfc(self) -> None:
        decomposed = "Cafe\u0301"
        cleaned = sanitize_filename(decomposed)

        self.assertEqual(unicodedata.normalize("NFC", decomposed), cleaned)


if __name__ == "__main__":
    unittest.main()
