import unittest
from pathlib import Path


class FormalReviewRevisionWriterExtensionGuardTests(unittest.TestCase):
    def test_revision_writer_checks_source_output_suffix(self) -> None:
        text = Path("core/formal_review/revision_writer.py").read_text(encoding="utf-8")
        self.assertIn('_SUPPORTED_WORD_SUFFIXES = {".doc", ".docx"}', text)
        self.assertIn("source_suffix = _normalized_word_suffix(source_file)", text)
        self.assertIn("output_suffix = _normalized_word_suffix(output_file)", text)
        self.assertIn("if source_suffix not in _SUPPORTED_WORD_SUFFIXES:", text)
        self.assertIn("if output_suffix not in _SUPPORTED_WORD_SUFFIXES:", text)
        self.assertIn("if source_suffix != output_suffix:", text)
        self.assertIn("Output extension must match source extension", text)


if __name__ == "__main__":
    unittest.main()
