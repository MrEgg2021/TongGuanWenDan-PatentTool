from __future__ import annotations

import unittest
from pathlib import Path


class OfficialDocsNavigationHealthWiringTests(unittest.TestCase):
    def test_navigation_checks_catalog_health_before_entering_page(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = (repo_root / "gui/main_window/mixins/navigation_mixin_impl.py").read_text(encoding="utf-8")

        self.assertIn("def _nav_to_official_docs(self):", text)
        self.assertIn("get_supported_type_catalog_health()", text)
        self.assertIn('QMessageBox.critical(self, "官文资源不可用"', text)
        self.assertIn('self._set_nav_checked("official_docs")', text)


if __name__ == "__main__":
    unittest.main()
