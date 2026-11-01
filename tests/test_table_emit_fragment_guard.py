from __future__ import annotations

import unittest

from core.document_parser.table_ops.emit_fragment_ops import _emit_fragments


class _DummyEmitter:
    description_paragraph_split_mode = "word"

    def __init__(self, centered_height_mm: float) -> None:
        self.centered_height_mm = float(centered_height_mm)
        self.emitted: list[tuple[str, float, float, bool]] = []
        self.config = {
            "equation_centering": {
                "precise": {
                    "line_width_mm": 165.0,
                    "desc_reserved_mm": 20.0,
                }
            }
        }

    def _prev_paragraph_ends_with_period(self, _parent_node) -> bool:
        return True

    def _get_table_splitting_max_height_cm(self) -> float:
        return 24.0

    def _apply_table_centering_if_enabled(
        self,
        filename,
        width_mm,
        height_mm,
        *,
        current_section_key,
        target_width_mm,
    ) -> tuple[float, float]:
        _ = filename, width_mm, height_mm, current_section_key
        return float(target_width_mm), float(self.centered_height_mm)

    def _emit_final_table_image(self, parent_node, section, fn, w, h, table_obj, need_num):
        _ = parent_node, table_obj, fn
        self.emitted.append((str(section), float(w), float(h), bool(need_num)))
        return True


class _DummyClaimEmitter(_DummyEmitter):
    def __init__(self) -> None:
        super().__init__(centered_height_mm=20.0)
        self.centering_calls: list[tuple[str, str, float | None]] = []

    def _get_table_center_target_width_mm(self, current_section_key: str) -> float | None:
        if current_section_key == "claims":
            return 165.0
        return None

    def _table_range_has_ole(self, rng) -> bool:
        return bool(getattr(rng, "has_ole", False))

    def _apply_table_centering_if_enabled(
        self,
        filename,
        width_mm,
        height_mm,
        *,
        current_section_key,
        target_width_mm,
    ) -> tuple[float, float]:
        self.centering_calls.append((str(filename), str(current_section_key), target_width_mm))
        return float(target_width_mm), float(height_mm)


class _FakeCellRange:
    def __init__(self, text: str = "", *, has_ole: bool = False) -> None:
        self.Text = text
        self.has_ole = bool(has_ole)


class _FakeCell:
    def __init__(self, rng: _FakeCellRange) -> None:
        self.Range = rng


class _FakeCount:
    def __init__(self, count: int) -> None:
        self.Count = int(count)


class _FakeClaimsTable:
    def __init__(self, *, rows: int = 1, cols: int = 2, right_text: str = "( 1 )\r\x07", left_has_ole: bool = True) -> None:
        self.Rows = _FakeCount(rows)
        self.Columns = _FakeCount(cols)
        self._left = _FakeCell(_FakeCellRange("", has_ole=left_has_ole))
        self._right = _FakeCell(_FakeCellRange(right_text))

    def Cell(self, row: int, col: int):
        if int(row) == 1 and int(col) == 1:
            return self._left
        if int(row) == 1 and int(col) == 2:
            return self._right
        raise IndexError(row, col)


class TableEmitFragmentGuardTests(unittest.TestCase):
    def test_emit_fragments_rejects_fragment_when_centered_height_exceeds_limit(self) -> None:
        parser = _DummyEmitter(centered_height_mm=260.0)

        result = _emit_fragments(parser, [("frag.jpg", 104.73, 200.0)], {}, "description", object())

        self.assertFalse(result)
        self.assertEqual(parser.emitted, [])

    def test_emit_fragments_keeps_emitting_when_centered_height_is_within_limit(self) -> None:
        parser = _DummyEmitter(centered_height_mm=200.0)

        result = _emit_fragments(parser, [("frag.jpg", 104.73, 200.0)], {}, "description", object())

        self.assertTrue(result)
        self.assertEqual(parser.emitted, [("description", 145.0, 200.0, True)])

    def test_emit_fragments_centers_claims_formula_number_table_only(self) -> None:
        parser = _DummyClaimEmitter()

        result = _emit_fragments(
            parser,
            [("formula_table.jpg", 100.0, 20.0)],
            {},
            "claims",
            _FakeClaimsTable(),
        )

        self.assertTrue(result)
        self.assertEqual(parser.centering_calls, [("formula_table.jpg", "claims", 165.0)])
        self.assertEqual(parser.emitted, [("claims", 165.0, 20.0, False)])

    def test_emit_fragments_does_not_center_plain_claims_table(self) -> None:
        parser = _DummyClaimEmitter()

        result = _emit_fragments(
            parser,
            [("plain_table.jpg", 100.0, 20.0)],
            {},
            "claims",
            _FakeClaimsTable(rows=2, cols=2, right_text="not a formula number", left_has_ole=True),
        )

        self.assertTrue(result)
        self.assertEqual(parser.centering_calls, [])
        self.assertEqual(parser.emitted, [("claims", 100.0, 20.0, False)])


if __name__ == "__main__":
    unittest.main()
