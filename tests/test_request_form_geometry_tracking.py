from __future__ import annotations

import unittest
from pathlib import Path


class RequestFormGeometryTrackingTests(unittest.TestCase):
    def test_geometry_ops_uses_owner_local_rect_instead_of_global_mapping(self) -> None:
        source = Path(
            "gui/widgets_impl/request_form/dialog_impl/main_dialog_impl/geometry_ops.py"
        ).read_text(encoding="utf-8")
        self.assertIn("self.setGeometry(QRect(target.rect()))", source)
        self.assertNotIn("mapToGlobal", source)

    def test_event_filter_watches_layout_and_screen_related_events(self) -> None:
        source = Path(
            "gui/widgets_impl/request_form/dialog_impl/main_dialog_impl/event_filter_ops.py"
        ).read_text(encoding="utf-8")
        self.assertIn("QEvent.Show", source)
        self.assertIn("QEvent.LayoutRequest", source)
        self.assertIn("QEvent.ScreenChangeInternal", source)


if __name__ == "__main__":
    unittest.main()
