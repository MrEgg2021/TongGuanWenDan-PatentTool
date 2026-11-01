from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

from core.paths_utils import get_machine_data_dir, get_resource_path

_MIRROR_ROOT_DIRNAME = "official_docs_resource_mirror"


@dataclass(frozen=True)
class ResourceMirrorPaths:
    resource_name: str
    embedded_path: str
    mirror_path: str


def get_resource_mirror_paths(resource_name: str) -> ResourceMirrorPaths:
    name = str(resource_name or "").strip()
    embedded_path = get_resource_path(name)
    mirror_root = os.path.join(get_machine_data_dir(), _MIRROR_ROOT_DIRNAME)
    mirror_path = os.path.join(mirror_root, name)
    return ResourceMirrorPaths(
        resource_name=name,
        embedded_path=embedded_path,
        mirror_path=mirror_path,
    )


def sync_embedded_resource_to_mirror(paths: ResourceMirrorPaths) -> str:
    if not paths.resource_name:
        return "resource name is empty"
    if not os.path.exists(paths.embedded_path):
        return f"embedded resource missing: {paths.embedded_path}"

    try:
        os.makedirs(os.path.dirname(paths.mirror_path), exist_ok=True)
        tmp_path = paths.mirror_path + ".tmp"
        shutil.copyfile(paths.embedded_path, tmp_path)
        os.replace(tmp_path, paths.mirror_path)
        return ""
    except Exception as exc:
        return f"failed to sync mirror resource '{paths.resource_name}': {exc}"

