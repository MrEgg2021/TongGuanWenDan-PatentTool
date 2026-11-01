import unittest
from pathlib import Path


class DropCardProxyWiringTests(unittest.TestCase):
    def test_drop_card_proxy_is_exposed_and_installed_on_all_target_pages(self) -> None:
        drag_drop = Path("gui/widgets_impl/drag_drop.py").read_text(encoding="utf-8")
        widgets_impl_init = Path("gui/widgets_impl/__init__.py").read_text(encoding="utf-8")
        widgets_api = Path("gui/widgets.py").read_text(encoding="utf-8")
        single_panel = Path("gui/ui_layout_impl/single_panel.py").read_text(encoding="utf-8")
        batch_panel = Path("gui/ui_layout_impl/batch_panel.py").read_text(encoding="utf-8")
        task_panel = Path("gui/ui_layout_impl/official_docs_page_parts/task_panel.py").read_text(encoding="utf-8")
        preview_page = Path("gui/ui_layout_impl/preview_page.py").read_text(encoding="utf-8")

        self.assertIn("class DropCardProxy(QObject):", drag_drop)
        self.assertIn("def install_drop_card_proxy(card: QWidget, drop_widget: QWidget) -> DropCardProxy:", drag_drop)
        self.assertIn("DropCardProxy", widgets_impl_init)
        self.assertIn("install_drop_card_proxy", widgets_impl_init)
        self.assertIn("DropCardProxy", widgets_api)
        self.assertIn("install_drop_card_proxy", widgets_api)

        self.assertIn("install_drop_card_proxy(top_card, window.single_drop_zone)", single_panel)
        self.assertIn("install_drop_card_proxy(drop_card, window.batch_drop_zone)", batch_panel)
        self.assertIn("install_drop_card_proxy(drop_card, drop_zone)", task_panel)
        self.assertIn("install_drop_card_proxy(drop_card, dz)", preview_page)


if __name__ == "__main__":
    unittest.main()
