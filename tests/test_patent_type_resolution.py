from __future__ import annotations

import unittest

from core.patent_type_resolution import (
    detect_direct_patent_type_heading,
    get_default_disclosure_heading,
    get_patent_type_display_label,
)


class PatentTypeResolutionTests(unittest.TestCase):
    def test_detect_direct_patent_type_heading_accepts_plain_heading(self) -> None:
        patent_type, heading = detect_direct_patent_type_heading("发明内容 提出一种改进方案。")
        self.assertEqual(patent_type, "invention")
        self.assertEqual(heading, "发明内容")

    def test_detect_direct_patent_type_heading_accepts_number_prefix(self) -> None:
        patent_type, heading = detect_direct_patent_type_heading("【0003】实用新型内容：本实用新型公开了一种装置。")
        self.assertEqual(patent_type, "utility_model")
        self.assertEqual(heading, "实用新型内容")

    def test_detect_direct_patent_type_heading_ignores_other_disclosure_titles(self) -> None:
        patent_type, heading = detect_direct_patent_type_heading("技术方案：包括处理器和存储器。")
        self.assertIsNone(patent_type)
        self.assertIsNone(heading)

    def test_default_disclosure_heading_is_binary(self) -> None:
        self.assertEqual(get_default_disclosure_heading("invention"), "发明内容")
        self.assertEqual(get_default_disclosure_heading("utility_model"), "实用新型内容")
        self.assertEqual(get_default_disclosure_heading(None), "发明内容")

    def test_patent_type_display_label_is_cn(self) -> None:
        self.assertEqual(get_patent_type_display_label("invention"), "发明")
        self.assertEqual(get_patent_type_display_label("utility_model"), "实用新型")
        self.assertEqual(get_patent_type_display_label(None), "")


if __name__ == "__main__":
    unittest.main()
