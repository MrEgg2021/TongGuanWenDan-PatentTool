from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QFont


_PANEL_ITEM_PRIMITIVE = getattr(QStyle, "PE_PanelItemViewItem", None)
if _PANEL_ITEM_PRIMITIVE is None:
    _primitive_enum = getattr(QStyle, "PrimitiveElement", None)
    if _primitive_enum is not None:
        _PANEL_ITEM_PRIMITIVE = getattr(_primitive_enum, "PE_PanelItemViewItem", None)

_STATE_SELECTED = getattr(QStyle, "State_Selected", None)
if _STATE_SELECTED is None:
    _state_enum = getattr(QStyle, "StateFlag", None) or getattr(QStyle, "State", None)
    if _state_enum is not None:
        _STATE_SELECTED = getattr(_state_enum, "State_Selected", 0)


class FactCandidateDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        if not index.isValid():
            return

        # Prepare option
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        painter.save()
        try:
            # 1. Draw Background (Selection, Hover, etc.)
            widget = opt.widget
            style = widget.style() if widget else None
            if style and _PANEL_ITEM_PRIMITIVE is not None:
                style.drawPrimitive(_PANEL_ITEM_PRIMITIVE, opt, painter, widget)

            # 2. Determine Style/Colors
            is_selected = bool(opt.state & _STATE_SELECTED) if _STATE_SELECTED else False

            main_text_color = opt.palette.text().color()
            if is_selected:
                main_text_color = opt.palette.highlightedText().color()

            # Light blue for sub text (CornflowerBlue approx), or lighter if selected
            sub_text_color = QColor("#6495ED")
            if is_selected:
                # If background is dark (default selection), we need light text.
                # If background is light (some styles), we need dark text.
                # Usually highlightedText is white/light.
                # Let's use a very light blue/white for selection state.
                sub_text_color = QColor("#E6E6FA")

            # 3. Parse Text
            # Main text is DisplayRole
            main_text = index.data(Qt.DisplayRole) or ""
            # Sub text is UserRole + 1
            assoc_info = index.data(Qt.UserRole + 1)
            sub_text = ""
            if assoc_info:
                sub_text = "\u5173\u8054\uff1a" + str(assoc_info)

            # 4. Layout & Draw
            rect = QRectF(opt.rect)
            rect.adjust(5, 0, -5, 0)  # Padding

            # Main Text
            font = opt.font
            painter.setFont(font)
            painter.setPen(main_text_color)

            # Measure main text height/alignment
            # We align left and vertical center
            # Using boundingRect to get width of main text
            flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            main_rect = painter.boundingRect(rect.toRect(), flags, main_text)

            # Draw Main
            painter.drawText(rect.toRect(), flags, main_text)

            # Sub Text
            if sub_text:
                sub_font = QFont(font)
                # Size -2
                pt = sub_font.pointSize()
                if pt > 0:
                    sub_font.setPointSize(max(1, pt - 2))
                else:
                    px = sub_font.pixelSize()
                    if px > 0:
                        sub_font.setPixelSize(max(1, px - 2))

                sub_font.setItalic(True)
                painter.setFont(sub_font)
                painter.setPen(sub_text_color)

                # Position: Right of main text + 10px padding
                # But we must respect the original rect's vertical centering
                sub_x = main_rect.width() + 10 + rect.x()

                if sub_x < rect.right():
                    sub_rect = QRectF(sub_x, rect.y(), rect.right() - sub_x, rect.height())
                    painter.drawText(sub_rect.toRect(), flags, sub_text)
        finally:
            painter.restore()
