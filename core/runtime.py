from __future__ import annotations

import os
import sys
import shutil

from core.logging_utils import logger

_OWNED_OUTPUT_WORKSPACES: set[str] = set()


def register_output_workspace(path: str) -> None:
    _OWNED_OUTPUT_WORKSPACES.add(os.path.realpath(path))


def cleanup_runtime_artifacts(result: dict | None = None) -> None:
    """仅清理本次转换拥有的工作目录，不删除配置指向的目录。"""
    if not getattr(sys, "frozen", False):
        return
    case_root = (result or {}).get("case_root")
    if not case_root:
        return
    workspace = os.path.realpath(os.path.dirname(case_root))
    if workspace not in _OWNED_OUTPUT_WORKSPACES:
        return
    try:
        shutil.rmtree(workspace)
        _OWNED_OUTPUT_WORKSPACES.discard(workspace)
        logger.info("🧹 已清理本次转换工作目录（exe 模式）")
    except OSError as exc:
        logger.warning("清理本次转换工作目录失败: %s", exc)
