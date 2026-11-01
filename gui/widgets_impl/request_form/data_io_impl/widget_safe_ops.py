def _set_checked_safe(widget, checked: bool) -> None:
    try:
        if widget is not None:
            widget.setChecked(bool(checked))
    except Exception:
        pass


def _set_text_safe(widget, text: str) -> None:
    try:
        if widget is not None:
            widget.setText(str(text or ""))
    except Exception:
        pass


def _set_edit_text_safe(widget, text: str) -> None:
    try:
        if widget is not None:
            widget.setEditText(str(text or ""))
    except Exception:
        pass


def _to_text(val) -> str:
    try:
        return str(val or "")
    except Exception:
        return ""
