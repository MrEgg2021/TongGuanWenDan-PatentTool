from __future__ import annotations

import unittest

from core.document_parser.paragraph_inline_impl.output_writer import write_segments


class _DummyPara:
    class _Range:
        Start = 0

    Range = _Range()


class _DummyParser:
    def __init__(self, *, pending_num=None, pending_segments=None) -> None:
        self._claims_pending_num = pending_num
        self._claims_pending_segments = list(pending_segments or [])
        self.captured = None

    def _get_list_marker(self, _para) -> str:
        return ""

    def _append_claim_segments(self, _parent_node, segments, is_new_start=False, claim_num=None) -> None:
        first_text = ""
        for seg in list(segments or []):
            if seg.get("kind") == "text":
                first_text = seg.get("text_plain") or seg.get("text") or ""
                break
        self.captured = {
            "is_new_start": bool(is_new_start),
            "claim_num": claim_num,
            "first_text": first_text,
        }


def _run_case(text: str, *, pending_num=None, pending_segments=None) -> dict:
    parser = _DummyParser(pending_num=pending_num, pending_segments=pending_segments)
    seg = {"kind": "text", "text": text, "text_plain": text}
    write_segments(parser, _DummyPara(), None, [seg], is_claim=True)
    return dict(parser.captured or {})


class ClaimsPrefixDedupeOutputWriterTests(unittest.TestCase):
    def test_strip_prefix_for_first_claim_when_pending_none(self) -> None:
        result = _run_case("1.一种装置，其特征在于：包括A。", pending_num=None, pending_segments=[])
        self.assertTrue(result["is_new_start"])
        self.assertEqual(1, result["claim_num"])
        self.assertTrue(str(result["first_text"]).startswith("一种装置"))

    def test_strip_prefix_when_lt_pending_and_no_pending_buffer_claim16_style(self) -> None:
        result = _run_case("1. 一种液晶化合物，其具有式I所示的结构：", pending_num=16, pending_segments=[])
        self.assertFalse(result["is_new_start"])
        self.assertEqual(1, result["claim_num"])
        self.assertTrue(str(result["first_text"]).startswith("一种液晶化合物"))

    def test_strip_prefix_when_lt_pending_and_no_pending_buffer_claim24_style(self) -> None:
        result = _run_case(
            "10. 根据权利要求1-6中任一项所述的液晶化合物或权利要求9所述的组合物在液晶显示领域中的应用。",
            pending_num=24,
            pending_segments=[],
        )
        self.assertFalse(result["is_new_start"])
        self.assertEqual(10, result["claim_num"])
        self.assertTrue(str(result["first_text"]).startswith("根据权利要求1-6中任一项"))

    def test_strip_prefix_when_equal_pending_and_no_pending_buffer(self) -> None:
        result = _run_case("2.根据权利要求1所述的装置。", pending_num=2, pending_segments=[])
        self.assertFalse(result["is_new_start"])
        self.assertEqual(2, result["claim_num"])
        self.assertTrue(str(result["first_text"]).startswith("根据权利要求1"))

    def test_do_not_strip_when_equal_pending_but_buffer_not_empty(self) -> None:
        result = _run_case("2.根据权利要求1所述的装置。", pending_num=2, pending_segments=[{"kind": "text"}])
        self.assertFalse(result["is_new_start"])
        self.assertEqual(2, result["claim_num"])
        self.assertTrue(str(result["first_text"]).startswith("2."))

    def test_strip_common_delimiters_dunhao_fullwidth_dot_fullwidth_paren(self) -> None:
        for source in ("2、根据权利要求1所述的装置。", "2．根据权利要求1所述的装置。", "2）根据权利要求1所述的装置。"):
            result = _run_case(source, pending_num=2, pending_segments=[])
            self.assertEqual(2, result["claim_num"])
            self.assertTrue(str(result["first_text"]).startswith("根据权利要求1"))

    def test_do_not_strip_non_common_numeric_leading_text(self) -> None:
        result_dash = _run_case("2-氯代化合物用于催化。", pending_num=None, pending_segments=[])
        self.assertIsNone(result_dash["claim_num"])
        self.assertTrue(str(result_dash["first_text"]).startswith("2-氯"))

        result_year = _run_case("2026年开始实施该方案。", pending_num=None, pending_segments=[])
        self.assertIsNone(result_year["claim_num"])
        self.assertTrue(str(result_year["first_text"]).startswith("2026年"))

    def test_do_not_treat_decimal_as_claim_prefix(self) -> None:
        result_decimal = _run_case("3.5% 的样本用于对照实验。", pending_num=24, pending_segments=[])
        self.assertIsNone(result_decimal["claim_num"])
        self.assertTrue(str(result_decimal["first_text"]).startswith("3.5%"))


if __name__ == "__main__":
    unittest.main()
