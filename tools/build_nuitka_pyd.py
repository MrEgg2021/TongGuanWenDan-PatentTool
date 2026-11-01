from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProfileConfig:
    name: str
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    description: str


def _load_profile(config_path: Path, profile_name: str) -> ProfileConfig:
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"nuitka config not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"nuitka config json parse error: {exc}") from exc

    if not isinstance(raw, dict):
        raise SystemExit("nuitka config must be a json object")
    node = raw.get(profile_name)
    if not isinstance(node, dict):
        available = ", ".join(sorted(str(k) for k in raw.keys()))
        raise SystemExit(f"profile not found: {profile_name}; available: {available}")

    include = tuple(str(x).strip() for x in node.get("include", []) if str(x).strip())
    exclude = tuple(str(x).strip() for x in node.get("exclude", []) if str(x).strip())
    description = str(node.get("description", "")).strip()
    if not include:
        raise SystemExit(f"profile '{profile_name}' has empty include list")
    return ProfileConfig(name=profile_name, include=include, exclude=exclude, description=description)


def _is_excluded(rel_posix: str, exclude_patterns: tuple[str, ...]) -> bool:
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(rel_posix, pattern):
            return True
    return False


def _collect_modules(repo_root: Path, profile: ProfileConfig) -> tuple[list[Path], dict[str, int]]:
    selected: dict[str, Path] = {}
    hit_count: dict[str, int] = {}

    for pattern in profile.include:
        hits_for_pattern = 0
        for path in repo_root.glob(pattern):
            if not path.is_file() or path.suffix.lower() != ".py":
                continue
            rel = path.relative_to(repo_root).as_posix()
            if _is_excluded(rel, profile.exclude):
                continue
            selected[rel] = path
            hits_for_pattern += 1
        hit_count[pattern] = hits_for_pattern

    modules = sorted(selected.values(), key=lambda p: p.relative_to(repo_root).as_posix())
    return modules, hit_count


def _resolve_jobs(raw_jobs: str) -> int:
    text = str(raw_jobs or "").strip().lower()
    if text in {"", "auto"}:
        return max(1, int(os.cpu_count() or 1))
    try:
        jobs = int(text)
    except ValueError as exc:
        raise SystemExit(f"invalid --jobs value: {raw_jobs!r}") from exc
    if jobs <= 0:
        raise SystemExit("--jobs must be > 0")
    return jobs


def _find_compiled_module(output_dir: Path, stem: str) -> Path | None:
    candidates = sorted(output_dir.glob(f"{stem}*.pyd"))
    if not candidates:
        return None
    return candidates[-1]


def _run_nuitka_for_module(
    *,
    repo_root: Path,
    source_file: Path,
    output_root: Path,
    jobs: int,
    verbose: bool,
) -> dict[str, Any]:
    rel = source_file.relative_to(repo_root)
    rel_posix = rel.as_posix()
    out_dir = output_root / rel.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "nuitka.__main__",
        "--module",
        rel_posix,
        f"--output-dir={out_dir}",
        "--remove-output",
        "--no-pyi-file",
        f"--jobs={jobs}",
    ]
    if os.name == "nt":
        cmd.append("--msvc=latest")

    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    elapsed = round(time.perf_counter() - started, 3)

    compiled = _find_compiled_module(out_dir, source_file.stem)
    ok = proc.returncode == 0 and compiled is not None

    result = {
        "source": rel_posix,
        "output": compiled.relative_to(repo_root).as_posix() if compiled else "",
        "ok": ok,
        "returncode": int(proc.returncode),
        "seconds": elapsed,
        "command": cmd,
        "stdout": proc.stdout[-20000:] if proc.stdout else "",
        "stderr": proc.stderr[-20000:] if proc.stderr else "",
    }

    status = "OK" if ok else "FAIL"
    print(f"[{status}] {rel_posix} ({elapsed}s)")
    if verbose and proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)

    return result


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _prepare_output(repo_root: Path, output_root: Path, *, clean: bool) -> None:
    build_root = repo_root / "build"
    if output_root == build_root or not output_root.is_relative_to(build_root):
        raise SystemExit("--output-root must be a dedicated subdirectory of the repository build directory")
    marker = output_root / ".nuitka-output-owner"
    owner = str(repo_root)
    if output_root.exists():
        owned = marker.is_file() and marker.read_text(encoding="utf-8") == owner
        # 兼容旧构建器已经生成且绑定到该路径的清单。
        if not owned and (output_root / "manifest.json").is_file():
            try:
                manifest = json.loads((output_root / "manifest.json").read_text(encoding="utf-8"))
                owned = manifest.get("repo_root") == owner and manifest.get("output_root") == str(output_root)
            except (OSError, ValueError, AttributeError):
                owned = False
        if not owned and any(output_root.iterdir()):
            raise SystemExit("output directory is not owned by this build tool; refusing to overwrite or clean it")
        if clean:
            shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    marker.write_text(owner, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile selected python modules into .pyd via Nuitka.")
    parser.add_argument("--profile", default="full_core", help="Profile name in tools/nuitka_module_sets.json")
    parser.add_argument(
        "--config",
        default="tools/nuitka_module_sets.json",
        help="Path to module-set config json.",
    )
    parser.add_argument(
        "--output-root",
        default="build/nuitka_pyd",
        help="Dedicated owned subdirectory under repository build/ for compiled .pyd files.",
    )
    parser.add_argument("--jobs", default="auto", help="Nuitka compile jobs. Use integer or 'auto'.")
    parser.add_argument("--clean", action="store_true", help="Clean output root before compile.")
    parser.add_argument("--verbose", action="store_true", help="Print full stdout from Nuitka subprocesses.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    config_path = (repo_root / args.config).resolve()
    output_root = (repo_root / args.output_root).resolve()
    manifest_path = output_root / "manifest.json"

    profile = _load_profile(config_path, args.profile)
    jobs = _resolve_jobs(args.jobs)

    modules, pattern_hits = _collect_modules(repo_root, profile)
    if not modules:
        raise SystemExit(f"no modules selected for profile={profile.name}")
    if any(source.resolve().is_relative_to(output_root) for source in modules):
        raise SystemExit("output directory contains selected source modules; refusing to clean or overwrite it")
    _prepare_output(repo_root, output_root, clean=args.clean)

    print(
        f"Profile={profile.name}, selected modules={len(modules)}, jobs={jobs}, output={output_root.relative_to(repo_root).as_posix()}"
    )

    results: list[dict[str, Any]] = []
    for source_file in modules:
        result = _run_nuitka_for_module(
            repo_root=repo_root,
            source_file=source_file,
            output_root=output_root,
            jobs=jobs,
            verbose=bool(args.verbose),
        )
        results.append(result)

    failed = [x for x in results if not bool(x.get("ok"))]
    compiled = [x for x in results if bool(x.get("ok"))]

    manifest = {
        "profile": profile.name,
        "description": profile.description,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "config_path": str(config_path),
        "output_root": str(output_root),
        "jobs": jobs,
        "patterns": {
            "include": list(profile.include),
            "exclude": list(profile.exclude),
            "match_counts": pattern_hits,
        },
        "summary": {
            "selected": len(modules),
            "compiled": len(compiled),
            "failed": len(failed),
        },
        "modules": results,
    }
    _write_manifest(manifest_path, manifest)

    print(
        f"Manifest written: {manifest_path.relative_to(repo_root).as_posix()} | compiled={len(compiled)} failed={len(failed)}"
    )
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
