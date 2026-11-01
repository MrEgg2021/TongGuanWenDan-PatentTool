import os

from core.paths_utils import get_app_dir


def _ensure_output_dir() -> str:
    base = os.path.join(get_app_dir(), "output")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return base
