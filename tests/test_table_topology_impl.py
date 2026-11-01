from __future__ import annotations

import unittest

from core.document_parser.table_topology_impl import TableTopologyScanner


class _CountHolder:
    def __init__(self, count: int) -> None:
        self.Count = int(count)


class _Cell:
    def __init__(self, vertical_merge: int = 0) -> None:
        self.VerticalMerge = int(vertical_merge)


class _Table:
    def __init__(self, mapping: dict[tuple[int, int], object], *, rows: int, cols: int) -> None:
        self._mapping = dict(mapping)
        self.Rows = _CountHolder(rows)
        self.Columns = _CountHolder(cols)

    def Cell(self, row: int, col: int):
        value = self._mapping[(int(row), int(col))]
        if isinstance(value, Exception):
            raise value
        return value


class TableTopologyScannerTests(unittest.TestCase):
    def test_is_row_safe_rejects_ambiguous_cell_access_at_cut_boundary(self) -> None:
        table = _Table(
            {
                (3, 1): _Cell(0),
                (3, 2): RuntimeError("ambiguous merged boundary"),
            },
            rows=3,
            cols=2,
        )
        scanner = TableTopologyScanner(table)

        self.assertFalse(scanner._is_row_safe(3))


if __name__ == "__main__":
    unittest.main()
