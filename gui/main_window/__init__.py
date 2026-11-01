try:
    from .main_window import MainWindow
except Exception:
    MainWindow = None

__all__ = ["MainWindow"]
