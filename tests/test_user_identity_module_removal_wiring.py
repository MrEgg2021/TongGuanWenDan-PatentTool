from __future__ import annotations

import unittest
from pathlib import Path


class UserIdentityModuleRemovalWiringTests(unittest.TestCase):
    def test_sidebar_and_layout_no_longer_reference_user_identity_module(self) -> None:
        modern_shell = Path("gui/ui_layout_impl/modern_shell_impl.py").read_text(encoding="utf-8")
        ui_layout = Path("gui/ui_layout.py").read_text(encoding="utf-8")

        self.assertNotIn("用户身份信息", modern_shell)
        self.assertNotIn("nav_agent_applicant", modern_shell)
        self.assertNotIn("build_agent_applicant_page", ui_layout)
        self.assertNotIn("_agent_applicant_page", ui_layout)

    def test_navigation_mixin_no_longer_exposes_user_identity_target(self) -> None:
        source = Path("gui/main_window/mixins/navigation_mixin_impl.py").read_text(encoding="utf-8")

        self.assertNotIn("_nav_to_agent_applicant", source)
        self.assertNotIn("_show_agent_applicant_page", source)
        self.assertNotIn("agent_applicant", source)


if __name__ == "__main__":
    unittest.main()
