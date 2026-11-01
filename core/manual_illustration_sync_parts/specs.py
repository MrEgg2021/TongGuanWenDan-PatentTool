from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class ManualIllustration:
    shot_id: str
    heading: str
    relative_path: str
    caption: str
    chapter_anchor: str = ""
    variant: str = ""
    purpose: str = ""
    priority: str = ""
    ui_state: str = ""


@dataclass(frozen=True)
class MarkdownSyncSegment:
    kind: str
    content: str = ""
    alt_text: str = ""
    raw_target: str = ""


@dataclass(frozen=True)
class ManualShotSpec:
    shot_id: str
    heading: str
    relative_path: str
    caption: str
    capture: str
    action: str
    target_attr: str = ""
    chapter_anchor: str = ""
    variant: str = ""
    purpose: str = ""
    priority: str = "medium"
    ui_state: str = ""
    scenario_key: str = ""


_DEFAULT_MANUAL_SHOTS_CONFIG_PATH = Path(__file__).resolve().parents[2] / "resources" / "manual_illustration_shots.json"
_KNOWN_SCENARIO_KEYS = {
    "",
    "navigation",
    "single_document",
    "batch",
    "response",
    "preview",
    "data_management",
    "official_docs",
    "formal_review",
    "settings",
    "about",
}


def get_default_manual_shot_config_path() -> Path:
    return _DEFAULT_MANUAL_SHOTS_CONFIG_PATH


def _normalize_posix_fragment(value: str, *, field_name: str) -> str:
    normalized = str(value or "").replace("\\", "/").strip().strip("/")
    if not normalized:
        raise ValueError(f"{field_name} 不能为空")
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{field_name} 非法: {value}")
    return str(path)


def _build_relative_shot_path(output_dir: str, shot_id: str) -> str:
    output_fragment = _normalize_posix_fragment(output_dir, field_name="module.output_dir")
    shot_name = str(shot_id or "").strip()
    if not shot_name or any(token in shot_name for token in ("/", "\\")) or shot_name in {".", ".."}:
        raise ValueError(f"shot_id 非法: {shot_id}")
    return str(PurePosixPath("shots") / output_fragment / f"{shot_name}.png")


def load_manual_shot_specs(config_path: Path | None = None) -> list[ManualShotSpec]:
    config_file = Path(config_path or get_default_manual_shot_config_path()).resolve()
    if not config_file.exists():
        raise FileNotFoundError(f"截图配置文件不存在: {config_file}")

    payload = json.loads(config_file.read_text(encoding="utf-8"))
    modules = payload.get("modules")
    if not isinstance(modules, list) or not modules:
        raise ValueError("截图配置缺少 modules 列表")

    seen_shot_ids: set[str] = set()
    seen_relative_paths: set[str] = set()
    specs: list[ManualShotSpec] = []

    for module in modules:
        if not isinstance(module, dict):
            raise ValueError("modules 中存在非法条目")
        module_id = str(module.get("module_id") or "").strip()
        output_dir = _normalize_posix_fragment(module.get("output_dir") or "", field_name=f"{module_id or 'module'}.output_dir")
        shots = module.get("shots")
        if not module_id:
            raise ValueError("module_id 不能为空")
        if not isinstance(shots, list):
            raise ValueError(f"{module_id}.shots 必须是数组")

        for shot in shots:
            if not isinstance(shot, dict):
                raise ValueError(f"{module_id}.shots 中存在非法条目")
            if shot.get("enabled", True) is False:
                continue

            shot_id = str(shot.get("shot_id") or "").strip()
            heading = str(shot.get("heading") or "").strip()
            caption = str(shot.get("caption") or "").strip()
            capture = str(shot.get("capture") or "").strip()
            action = str(shot.get("action") or "").strip()
            chapter_anchor = str(shot.get("chapter_anchor") or heading).strip()
            scenario_key = str(shot.get("scenario_key") or "").strip()
            if not all((shot_id, heading, caption, capture, action, chapter_anchor)):
                raise ValueError(f"{module_id}.{shot_id or '<missing>'} 缺少必填字段")
            if scenario_key not in _KNOWN_SCENARIO_KEYS:
                raise ValueError(f"未知 scenario_key: {scenario_key}")

            relative_path = _build_relative_shot_path(output_dir, shot_id)
            relative_key = relative_path.casefold()
            shot_key = shot_id.casefold()
            if shot_key in seen_shot_ids:
                raise ValueError(f"存在重复 shot_id: {shot_id}")
            if relative_key in seen_relative_paths:
                raise ValueError(f"存在重复输出路径: {relative_path}")
            seen_shot_ids.add(shot_key)
            seen_relative_paths.add(relative_key)

            specs.append(
                ManualShotSpec(
                    shot_id=shot_id,
                    heading=heading,
                    relative_path=relative_path,
                    caption=caption,
                    capture=capture,
                    action=action,
                    target_attr=str(shot.get("target_attr") or "").strip(),
                    chapter_anchor=chapter_anchor,
                    variant=str(shot.get("variant") or "").strip(),
                    purpose=str(shot.get("purpose") or "").strip(),
                    priority=str(shot.get("priority") or "medium").strip() or "medium",
                    ui_state=str(shot.get("ui_state") or "").strip(),
                    scenario_key=scenario_key,
                )
            )
    return specs


def build_default_manual_shot_specs() -> list[ManualShotSpec]:
    return load_manual_shot_specs()
