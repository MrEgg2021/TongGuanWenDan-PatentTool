from pathlib import Path
import logging
import sys


_LOGGER = logging.getLogger(__name__)


def _warn_missing_theme_assets(theme_path: Path) -> None:
    """Warn (without breaking UI) when theme-dependent assets are missing."""
    try:
        required = (
            theme_path.parent / "assets" / "check_dark.svg",
            theme_path.parent / "assets" / "chevron_down.svg",
            theme_path.parent / "assets" / "chevron_right.svg",
        )
        missing = [str(p) for p in required if not p.exists()]
        if missing:
            _LOGGER.warning("Theme assets missing: %s", ", ".join(missing))
    except Exception:
        # Non-blocking by design: style loading must never fail because of this check.
        pass


def load_theme_stylesheet() -> str:
    """加载现代主题 QSS。若读取失败则返回空字符串。"""
    candidates = []
    try:
        candidates.append(Path(__file__).with_name("theme.qss"))
    except Exception:
        candidates = []

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            try:
                candidates.append(Path(str(meipass)) / "gui" / "ui_layout_impl" / "theme.qss")
            except Exception:
                pass

    for theme_path in candidates:
        try:
            if theme_path.exists():
                raw = theme_path.read_text(encoding="utf-8")
                _warn_missing_theme_assets(theme_path)
                try:
                    theme_dir = str(theme_path.parent.as_posix())
                    raw = raw.replace("__THEME_DIR__", theme_dir)
                except Exception:
                    pass
                return raw
        except Exception:
            continue
    return ""


# 默认样式已迁移至 theme.qss，此处保留极简 fallback
APP_STYLESHEET = """
QWidget {
    background-color: #F8FAFC;
    color: #0F172A;
    font-size: 14px;
}
QPushButton {
    min-height: 32px;
    padding: 0 16px;
    border-radius: 6px;
    background-color: #E2E8F0;
}
QPushButton:hover {
    background-color: #CBD5E1;
}
"""
