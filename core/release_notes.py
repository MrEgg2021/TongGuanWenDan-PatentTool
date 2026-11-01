from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

INTERNAL_ONLY_SUBJECT_PREFIXES = (
    "test(",
    "docs(openspec):",
    "docs(release):",
    "docs(project):",
    "chore(openspec):",
)


def _run_git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return str(completed.stdout or "")


def resolve_ref(repo_root: Path, ref: str) -> str:
    return _run_git(repo_root, "rev-parse", ref).strip()


def collect_release_commits(repo_root: Path, previous_ref: str, release_ref: str) -> list[dict]:
    raw = _run_git(repo_root, "log", "--reverse", "--format=%H%x1f%s", f"{previous_ref}..{release_ref}")
    commits: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        commit_hash, subject = line.split("\x1f", 1)
        files_raw = _run_git(repo_root, "show", "--pretty=", "--name-only", commit_hash)
        changed_files = [item.strip().replace("\\", "/") for item in files_raw.splitlines() if item.strip()]
        commits.append(
            {
                "hash": commit_hash[:7],
                "full_hash": commit_hash,
                "subject": subject.strip(),
                "changed_files": changed_files,
            }
        )
    return commits


def infer_version_from_ref(ref: str) -> str:
    text = str(ref or "").strip()
    if text.lower().startswith("v"):
        text = text[1:]
    return text


def is_internal_only_commit(subject: str) -> bool:
    value = str(subject or "").strip()
    return any(value.startswith(prefix) for prefix in INTERNAL_ONLY_SUBJECT_PREFIXES)


def _default_change_id(subject: str) -> str:
    lowered = str(subject or "").lower()
    head = lowered.split(":", 1)[0]
    head = re.sub(r"[^a-z0-9]+", "-", head).strip("-")
    return head or "misc-change"


def classify_user_visible_change(commit: dict) -> dict | None:
    subject = str(commit.get("subject") or "").strip()
    changed_files = [str(item) for item in commit.get("changed_files") or []]

    if is_internal_only_commit(subject):
        return None

    if subject.startswith("fix(response-correction):"):
        return {
            "change_id": "response-correction-slot-mapping",
            "section": "问题修复",
            "text": "修复了答复/补正材料在导入和打包时可能放错位置的问题，后续整理和提交会更省心。",
        }
    if subject.startswith("fix(conversion):"):
        return {
            "change_id": "legacy-doc-compat-conversion",
            "section": "重点更新",
            "text": "直接处理旧版 Word 文档时更稳定了，附图更不容易出现图号对不上、白边过大或预览异常的问题。",
        }
    if subject.startswith("fix(word):"):
        return {
            "change_id": "office-process-guard",
            "section": "兼容性与稳定性",
            "entries": [
                "之前有不少用户反馈：明明已经关闭了 Word/WPS 窗口，程序还是提示需要先关闭进程，但任务管理器里又不容易分辨到底该关哪个，使用上比较困惑。",
                "这次更新后，程序会更准确地区分“还在使用中的文档窗口”和“关闭窗口后遗留的后台进程”，减少把这类后台残留误判成必须先手动处理的问题。",
                "也就是说，遇到只剩后台残留、但没有真正打开文档窗口的情况时，程序通常不会再像以前那样直接把转换卡住；只有在这些后台进程确实影响 Word 启动时，才会再给出后续处理提示。",
            ],
        }
    if subject.startswith("docs(manual):"):
        return {
            "change_id": "manual-refresh",
            "section": "文档与使用说明",
            "text": "更新了用户手册和配套截图，和当前界面保持一致，按图操作会更直接。",
        }

    if subject.startswith("fix("):
        return {
            "change_id": _default_change_id(subject),
            "section": "问题修复",
            "text": subject.split(":", 1)[1].strip() if ":" in subject else subject,
        }
    if subject.startswith("feat("):
        return {
            "change_id": _default_change_id(subject),
            "section": "重点更新",
            "text": subject.split(":", 1)[1].strip() if ":" in subject else subject,
        }
    if subject.startswith("docs(") and any(path.startswith("docs/") or "用户使用手册+更新日志/" in path for path in changed_files):
        return {
            "change_id": _default_change_id(subject),
            "section": "文档与使用说明",
            "text": subject.split(":", 1)[1].strip() if ":" in subject else subject,
        }
    return {
        "change_id": _default_change_id(subject),
        "section": "重点更新",
        "text": subject.split(":", 1)[1].strip() if ":" in subject else subject,
    }


def build_release_manifest_from_commits(
    commits: list[dict],
    *,
    previous_ref: str,
    release_ref: str,
    release_user_version: str,
    git_tag: str,
    previous_user_version: str | None = None,
    product_visible_version: str | None = None,
    previous_commit: str | None = None,
    release_commit: str | None = None,
    quality_gates: list[dict] | None = None,
    packaging_evidence: list[dict] | None = None,
) -> dict:
    visible_version = str(product_visible_version or release_user_version)
    previous_version = str(previous_user_version or infer_version_from_ref(previous_ref))
    included_commits: list[dict] = []
    included_changes: list[str] = []
    excluded_internal_only_items: list[str] = []

    for commit in commits:
        subject = str(commit.get("subject") or "").strip()
        if is_internal_only_commit(subject):
            excluded_internal_only_items.append(subject)
            continue
        included_commits.append(commit)
        change = classify_user_visible_change(commit)
        if change is not None:
            change_id = str(change["change_id"])
            if change_id not in included_changes:
                included_changes.append(change_id)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "previous_user_version": previous_version,
        "previous_ref": previous_ref,
        "previous_commit": previous_commit or "",
        "release_user_version": release_user_version,
        "release_ref": release_ref,
        "release_commit": release_commit or "",
        "product_visible_version": visible_version,
        "git_tag": git_tag,
        "quality_gates": list(quality_gates or []),
        "packaging_evidence": list(packaging_evidence or []),
        "included_commits": included_commits,
        "included_changes": included_changes,
        "excluded_internal_only_items": excluded_internal_only_items,
    }


def write_manifest(path: Path, manifest: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evidence_status(item: dict) -> str:
    if item.get("not_executed"):
        return "not_executed"
    if item.get("not_applicable"):
        return "not_applicable"
    if "status" in item:
        status = item["status"]
        if status not in {"passed", "failed", "not_executed", "not_applicable"}:
            raise ValueError(f"invalid evidence status: {status!r}")
        return status
    if item.get("ok") is True:
        return "passed"
    if item.get("ok") is False:
        return "failed"
    return "not_executed"


def render_internal_evidence(manifest: dict) -> str:
    lines = [
        f"# {manifest['git_tag']} Internal Evidence",
        "",
        f"- previous ref: `{manifest['previous_ref']}`",
        f"- release ref: `{manifest['release_ref']}`",
        f"- previous user version: `V{manifest['previous_user_version']}`",
        f"- release user version: `V{manifest['release_user_version']}`",
        f"- product visible version: `V{manifest['product_visible_version']}`",
        f"- git tag: `{manifest['git_tag']}`",
        "",
        "## Included Commits",
    ]
    for commit in manifest.get("included_commits", []):
        lines.append(f"- `{commit['hash']}` {commit['subject']}")

    lines.extend(["", "## Excluded Internal-only Items"])
    excluded = manifest.get("excluded_internal_only_items", [])
    if excluded:
        lines.extend(f"- {subject}" for subject in excluded)
    else:
        lines.append("- none")

    lines.extend(["", "## Quality Gates"])
    gates = manifest.get("quality_gates", [])
    if gates:
        for item in gates:
            status = evidence_status(item)
            note = str(item.get("note") or "").strip()
            lines.append(f"- `{item.get('command', '')}`: {status}")
            if note:
                lines.append(f"  - {note}")
    else:
        lines.append("- not recorded in this manifest yet")

    lines.extend(["", "## Packaging Evidence"])
    packaging = manifest.get("packaging_evidence", [])
    if packaging:
        for item in packaging:
            status = evidence_status(item)
            note = str(item.get("note") or "").strip()
            lines.append(f"- `{item.get('command', '')}`: {status}")
            if note:
                lines.append(f"  - {note}")
    else:
        lines.append("- not recorded in this manifest yet")
    lines.append("")
    return "\n".join(lines)


def write_internal_evidence_output(manifest: dict, *, output_root: Path) -> Path:
    output_root = Path(output_root).resolve()
    git_tag = str(manifest["git_tag"])

    internal_path = output_root / "docs" / "release_notes" / "internal_evidence" / f"{git_tag}.internal.md"

    internal_path.parent.mkdir(parents=True, exist_ok=True)

    internal_path.write_text(render_internal_evidence(manifest), encoding="utf-8")
    return internal_path
