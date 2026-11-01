from __future__ import annotations

from pathlib import Path
import unittest


class TableTopologyCoeffSamplingIsolatedTests(unittest.TestCase):
    def test_table_topology_impl_has_no_bare_except(self) -> None:
        text = Path("core/document_parser/table_topology_impl.py").read_text(encoding="utf-8")

        self.assertNotIn("except:", text)

    def test_table_topology_has_no_legacy_bitmap_sampling(self) -> None:
        text = Path("core/document_parser/table_topology_impl.py").read_text(encoding="utf-8")

        self.assertNotIn("export_range_as_picture", text)
        self.assertNotIn("_sample_region_coefficient", text)


if __name__ == "__main__":
    unittest.main()
