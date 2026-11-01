from __future__ import annotations

import io
import os

from PIL import Image


wdInlineShapePicture = 3
wdInlineShapeLinkedPicture = 4
wdInlineShapeEmbeddedOLEObject = 1
wdInlineShapeLinkedOLEObject = 2


def _extract_drawings_media_to_temp(
    self,
    *,
    rid: str,
    filename_prefix: str,
    force_jpg_for_non_tiff: bool = False,
    target_width_px: int | None = None,
) -> tuple[str, str] | None:
    if not rid:
        return None

    try:
        clean_docx = str(getattr(getattr(self, "word", None), "doc", None).FullName or "")
    except Exception:
        clean_docx = ""
    try:
        source_docx = str(getattr(self, "input_file_path", None) or "")
    except Exception:
        source_docx = ""

    clean_docx = os.path.abspath(clean_docx) if clean_docx else ""
    source_docx = os.path.abspath(source_docx) if source_docx else ""

    rels = self._get_docx_rels_map(clean_docx) if clean_docx else {}
    target = rels.get(str(rid))
    if not target:
        return None
    zip_path = self._normalize_docx_target_to_zip_path(target)
    if not zip_path:
        return None

    b_clean = self._read_docx_zip_bytes(clean_docx, zip_path) if clean_docx else None
    if not b_clean:
        return None

    b_source = None
    if source_docx and source_docx != clean_docx:
        b_source = self._read_docx_zip_bytes(source_docx, zip_path)

    best_bytes = self._pick_better_media_bytes(b_clean, b_source)
    if not best_bytes:
        return None

    ext = ""
    try:
        ext = os.path.splitext(zip_path)[1].lower()
    except Exception:
        ext = ""
    if ext == ".jpeg":
        ext = ".jpg"
    elif ext == ".tiff":
        ext = ".tif"

    allowed = {".jpg", ".tif"}
    if force_jpg_for_non_tiff:
        output_ext = ".tif" if ext == ".tif" else ".jpg"
    else:
        output_ext = ext if ext in allowed else ".tif"

    import uuid

    filename = f"{filename_prefix}{uuid.uuid4().hex[:8]}{output_ext}"
    out_dir = self.config["paths"]["temp_dir"]
    output_path = os.path.join(out_dir, filename)
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        return None
    fidelity_cfg = {}
    try:
        fidelity_cfg = self._get_drawings_fidelity_config()
    except Exception:
        fidelity_cfg = {}

    def register_meta(**meta) -> None:
        try:
            self._register_drawings_media_quality_meta(filename, meta)
        except Exception:
            pass

    if output_ext == ".tif":
        if ext != ".tif":
            try:
                with Image.open(io.BytesIO(best_bytes)) as im0:
                    im = im0.convert("RGB")
                    im.save(output_path, format="TIFF", compression="tiff_deflate")
                return filename, output_path
            except Exception:
                return None
        try:
            with open(output_path, "wb") as f:
                f.write(best_bytes)
            register_meta(source_ext=ext, output_ext=output_ext, kind="media_direct")
            return filename, output_path
        except Exception:
            return None

    if output_ext == ".jpg":
        if ext in (".emf", ".wmf"):
            try:
                smart_enabled = bool(self._drawings_smart_jpg_fidelity_enabled())
            except Exception:
                smart_enabled = False
            try:
                has_target_width = int(target_width_px or 0) > 0
            except Exception:
                has_target_width = False
            if smart_enabled and has_target_width:
                target_dpi = int(fidelity_cfg.get("target_dpi") or 300)
                if self._render_drawings_emf_bytes_to_jpg(
                    best_bytes,
                    output_path,
                    target_width_px=target_width_px,
                    target_dpi=target_dpi,
                ):
                    rendered_w, rendered_h = 0, 0
                    try:
                        with Image.open(output_path) as rendered_img:
                            rendered_w, rendered_h = rendered_img.size
                    except Exception:
                        pass
                    register_meta(
                        source_ext=ext,
                        output_ext=output_ext,
                        kind="emf_high_fidelity_rendered",
                        target_width_px=int(target_width_px or 0),
                        rendered_width_px=int(rendered_w or 0),
                        rendered_height_px=int(rendered_h or 0),
                        target_dpi=target_dpi,
                    )
                    try:
                        self._append_drawings_quality_entry(
                            {
                                "level": "info",
                                "kind": "emf_high_fidelity_rendered",
                                "temp_file": filename,
                                "source_ext": ext,
                                "target_width_px": int(target_width_px or 0),
                                "rendered_width_px": int(rendered_w or 0),
                                "rendered_height_px": int(rendered_h or 0),
                                "target_dpi": target_dpi,
                            }
                        )
                    except Exception:
                        pass
                    return filename, output_path
                try:
                    self._append_drawings_quality_entry(
                        {
                            "level": "warning",
                            "kind": "emf_high_fidelity_failed",
                            "temp_file": filename,
                            "source_ext": ext,
                            "target_width_px": int(target_width_px or 0),
                            "target_dpi": target_dpi,
                        }
                    )
                except Exception:
                    pass
                return None

        if ext != ".jpg":
            try:
                with Image.open(io.BytesIO(best_bytes)) as im0:
                    im = im0.convert("RGB")
                    im.save(
                        output_path,
                        format="JPEG",
                        quality=int(fidelity_cfg.get("jpeg_quality") or self.config.get("jpeg_quality", 95)),
                        subsampling=int(fidelity_cfg.get("jpeg_subsampling") or self.config.get("jpeg_subsampling", 0)),
                        dpi=(300, 300),
                    )
                register_meta(source_ext=ext, output_ext=output_ext, kind="bitmap_converted")
                return filename, output_path
            except Exception:
                return None
        try:
            with open(output_path, "wb") as f:
                f.write(best_bytes)
            register_meta(source_ext=ext, output_ext=output_ext, kind="bitmap_direct")
            return filename, output_path
        except Exception:
            return None
    return None

