from __future__ import annotations

import unittest
from pathlib import Path


class PatentTypeDialogsStyleWiringTests(unittest.TestCase):
    def test_single_dialog_uses_graphic_checkbox_not_qradiobutton(self) -> None:
        text = Path("gui/patent_type_dialogs.py").read_text(encoding="utf-8")
        required = [
            "from gui.widgets import GraphicCheckBox",
            'radios: dict[str, GraphicCheckBox] = {}',
            "radio = GraphicCheckBox(label, option_box)",
            "group = QButtonGroup(dlg)",
        ]
        missing = [snippet for snippet in required if snippet not in text]
        self.assertFalse(missing, "Missing patent type dialog style wiring:\n" + "\n".join(missing))
        self.assertNotIn("QRadioButton", text)


if __name__ == "__main__":
    unittest.main()
