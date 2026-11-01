from __future__ import annotations

from . import structure_mixin_impl as _impl

for _name, _value in vars(_impl).items():
    if _name.startswith("__"):
        continue
    globals()[_name] = _value

if hasattr(_impl, "__all__"):
    __all__ = list(getattr(_impl, "__all__") or [])
else:
    __all__ = [name for name in vars(_impl) if not name.startswith("_")]
