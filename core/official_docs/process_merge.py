from __future__ import annotations

import os
from typing import Callable

from .models import CollisionPolicy, CollisionResolver


def ensure_dir(path: str) -> None:
    if path:
        os.makedirs(path, exist_ok=True)


def _next_available_name(*, base_name: str, exists_fn: Callable[[str], bool]) -> str:
    name = str(base_name or "").strip()
    stem, ext = os.path.splitext(name)
    if not ext:
        ext = ".pdf"
    if not exists_fn(name):
        return name
    for index in range(2, 10_000):
        candidate = f"{stem} ({index}){ext}"
        if not exists_fn(candidate):
            return candidate
    raise RuntimeError("无法自动改名：冲突次数过大")


def resolve_collision(
    *,
    output_pdf_name: str,
    summary_path: str,
    archive_path: str,
    collision_resolver: CollisionResolver | None,
) -> tuple[CollisionPolicy, str]:
    if collision_resolver is None:
        return "rename", output_pdf_name

    policy = collision_resolver(summary_path, archive_path)
    if policy not in ("overwrite", "skip", "rename"):
        return "rename", output_pdf_name
    if policy != "rename":
        return policy, output_pdf_name

    def _exists_for_name(name: str) -> bool:
        summary_candidate = os.path.join(os.path.dirname(summary_path), name) if summary_path else ""
        archive_candidate = os.path.join(os.path.dirname(archive_path), name) if archive_path else ""
        return (bool(summary_candidate) and os.path.exists(summary_candidate)) or (
            bool(archive_candidate) and os.path.exists(archive_candidate)
        )

    new_name = _next_available_name(base_name=output_pdf_name, exists_fn=_exists_for_name)
    return "rename", new_name


__all__ = ["ensure_dir", "resolve_collision"]
