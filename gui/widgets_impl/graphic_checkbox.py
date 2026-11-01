from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox


class GraphicCheckBox(QCheckBox):
    """
    Standard QCheckBox that can be styled via QSS.
    Previously a custom-painted widget, now refactored to use native styling.
    """

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        # Preserve the 'emphasis' property logic for compatibility
        # If 'emphasis' is set in QSS/properties, we can react to it,
        # but primarily we rely on QSS styling now.
