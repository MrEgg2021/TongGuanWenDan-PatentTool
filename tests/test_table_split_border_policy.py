from __future__ import annotations

import unittest

from core.document_parser.table_topology_impl import (
    CanvasSplitter,
    wdBorderBottom,
    wdBorderTop,
    wdLineStyleNone,
)


class _FakeBorder:
    def __init__(self, style: int) -> None:
        self.LineStyle = int(style)


class _FakeBorderAccessor:
    def __init__(self, mapping: dict[int, _FakeBorder]) -> None:
        self._mapping = mapping

    def __call__(self, border_type: int) -> _FakeBorder:
        return self._mapping.setdefault(int(border_type), _FakeBorder(wdLineStyleNone))


class _FakeRow:
    def __init__(self, *, top_style: int, bottom_style: int) -> None:
        self._borders = _FakeBorderAccessor(
            {
                wdBorderTop: _FakeBorder(top_style),
                wdBorderBottom: _FakeBorder(bottom_style),
            }
        )

    def Borders(self, border_type: int) -> _FakeBorder:
        return self._borders(border_type)


class _FakeRows:
    def __init__(self, rows: list[_FakeRow]) -> None:
        self._rows = rows
        self.Count = len(rows)
        self.First = rows[0]
        self.Last = rows[-1]

    def __call__(self, idx: int) -> _FakeRow:
        return self._rows[int(idx) - 1]


class _FakeCell(_FakeRow):
    pass


class _FakeColumns:
    def __init__(self, count: int) -> None:
        self.Count = int(count)


class _FakeTable:
    def __init__(self, cell_map: dict[tuple[int, int], _FakeCell] | None = None) -> None:
        self.Rows = _FakeRows(
            [
                _FakeRow(top_style=7, bottom_style=7),
                _FakeRow(top_style=7, bottom_style=7),
            ]
        )
        self.Columns = _FakeColumns(2)
        self._cell_map = cell_map or {}

    def Cell(self, row_idx: int, col_idx: int) -> _FakeCell:
        return self._cell_map[(int(row_idx), int(col_idx))]


class TableSplitBorderPolicyTests(unittest.TestCase):
    def test_apply_cut_border_policy_closed_restores_row_edges(self) -> None:
        splitter = CanvasSplitter(engine=object())
        upper = _FakeTable()
        lower = _FakeTable()

        upper.Rows.Last.Borders(wdBorderTop).LineStyle = 9
        upper.Rows.Last.Borders(wdBorderBottom).LineStyle = wdLineStyleNone
        lower.Rows.First.Borders(wdBorderTop).LineStyle = wdLineStyleNone
        lower.Rows.First.Borders(wdBorderBottom).LineStyle = 11

        splitter.apply_cut_border_policy(upper, lower, strategy="closed")

        self.assertEqual(upper.Rows.Last.Borders(wdBorderBottom).LineStyle, 9)
        self.assertEqual(lower.Rows.First.Borders(wdBorderTop).LineStyle, 11)

    def test_repair_split_borders_closed_restores_cell_edges(self) -> None:
        splitter = CanvasSplitter(engine=object())
        upper_left = _FakeCell(top_style=13, bottom_style=wdLineStyleNone)
        upper_right = _FakeCell(top_style=17, bottom_style=wdLineStyleNone)
        lower_left = _FakeCell(top_style=wdLineStyleNone, bottom_style=15)
        lower_right = _FakeCell(top_style=wdLineStyleNone, bottom_style=19)

        table = _FakeTable(
            cell_map={
                (1, 1): upper_left,
                (1, 2): upper_right,
                (2, 1): lower_left,
                (2, 2): lower_right,
            }
        )

        splitter._repair_split_borders(table, 2, strategy="closed")

        self.assertEqual(upper_left.Borders(wdBorderBottom).LineStyle, 13)
        self.assertEqual(upper_right.Borders(wdBorderBottom).LineStyle, 17)
        self.assertEqual(lower_left.Borders(wdBorderTop).LineStyle, 15)
        self.assertEqual(lower_right.Borders(wdBorderTop).LineStyle, 19)


if __name__ == "__main__":
    unittest.main()
