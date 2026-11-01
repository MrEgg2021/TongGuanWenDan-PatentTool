from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.cnipa_preview.runtime import REQUIRED_RUNTIME_SOURCE_PATHS  # noqa: E402


_INCLUDED_PATHS = REQUIRED_RUNTIME_SOURCE_PATHS


def _iter_files(source_root: Path, relative_path: str):
    source = source_root / relative_path
    if source.is_file():
        yield source, Path(relative_path)
        return
    if not source.is_dir():
        raise FileNotFoundError(f"required runtime path is missing: {source}")
    for path in sorted(source.rglob("*")):
        if path.is_file():
            yield path, Path(relative_path) / path.relative_to(source)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_runtime_archive(*, client_root: Path, output_path: Path, version: str, overwrite: bool = False) -> Path:
    if not client_root.is_dir():
        raise FileNotFoundError(f"CNIPA client root does not exist: {client_root}")
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output already exists (pass --overwrite to replace it): {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stage_dir = Path(tempfile.mkdtemp(prefix="cnipa_runtime_archive_", dir=str(output_path.parent)))
    stage_path = stage_dir / output_path.name
    try:
        with zipfile.ZipFile(stage_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            manifest = {
                "version": version,
                "source_layout": "CNIPAClient",
                "included_paths": list(_INCLUDED_PATHS),
            }
            archive.writestr("runtime-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            for source, relative in (
                pair for include in _INCLUDED_PATHS for pair in _iter_files(client_root, include)
            ):
                archive.write(source, Path("CNIPAClient") / relative)
        if output_path.exists():
            output_path.unlink()
        os.replace(stage_path, output_path)
        digest = _sha256(output_path)
        sidecar_manifest = output_path.with_suffix(".manifest.json")
        sidecar_manifest.write_text(
            json.dumps(
                {
                    "version": version,
                    "archive_name": output_path.name,
                    "archive_bytes": output_path.stat().st_size,
                    "sha256": digest,
                    "source_layout": "CNIPAClient",
                    "included_paths": list(_INCLUDED_PATHS),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        output_path.with_suffix(output_path.suffix + ".sha256").write_text(
            f"{digest}  {output_path.name}\n",
            encoding="utf-8",
        )
        return output_path
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a separately distributed CNIPA XML-to-PDF support archive.")
    parser.add_argument("--client-root", required=True, help="Official CNIPAClient installation root, for example D:\\Program Files (x86)\\CNIPAClient")
    parser.add_argument(
        "--output",
        default="artifacts/cnipa_preview_runtime/cnipa_xml2pdf_runtime.zip",
        help="Output ZIP path relative to the repository root (defaults to ignored artifacts/)",
    )
    parser.add_argument("--version", required=True, help="Renderer version recorded in the support archive manifest")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output archive")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    output = Path(args.output)
    if not output.is_absolute():
        output = repo_root / output
    result = build_runtime_archive(
        client_root=Path(args.client_root),
        output_path=output,
        version=str(args.version).strip(),
        overwrite=bool(args.overwrite),
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
