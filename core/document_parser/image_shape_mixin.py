from __future__ import annotations

import io
import math
import os
import re
import zipfile

from core.logging_utils import logger
from lxml import etree
from PIL import Image, ImageDraw, ImageFont

from .image_shape_ops.drawings_extract_ops import _extract_drawings_media_to_temp
from .image_shape_ops.floating_shape_ops import _process_floating_shapes
from .image_shape_ops.handle_shape_ops import handle_shape

wdInlineShapePicture = 3
wdInlineShapeLinkedPicture = 4
wdInlineShapeEmbeddedOLEObject = 1
wdInlineShapeLinkedOLEObject = 2



class ImageShapeMixin:
    def _resolve_active_clean_docx_path(self) -> str:
        try:
            clean_docx = str(getattr(getattr(self, "word", None), "doc", None).FullName or "")
        except Exception:
            clean_docx = ""
        return os.path.abspath(clean_docx) if clean_docx else ""

    def _get_parent_section_key(self, parent_node) -> str:
        tag = str(getattr(parent_node, "tag", "") or "").strip()
        mapping = {
            "cn-drawings": "drawings",
            "cn-description": "description",
            "cn-claims": "claims",
            "cn-abstract": "abstract",
        }
        return mapping.get(tag, "other")

    def _get_drawings_fidelity_config(self) -> dict[str, object]:
        cfg = getattr(self, "config", {}) or {}
        raw = cfg.get("drawings_fidelity") if isinstance(cfg, dict) else {}
        raw = raw if isinstance(raw, dict) else {}
        img_cfg = cfg.get("image_processing") if isinstance(cfg, dict) else {}
        img_cfg = img_cfg if isinstance(img_cfg, dict) else {}

        mode = str(raw.get("mode") or "smart").strip().lower()
        output_format = str(raw.get("output_format") or "jpg").strip().lower()
        if output_format == "jpeg":
            output_format = "jpg"
        low_dpi_policy = str(raw.get("low_dpi_policy") or "warn").strip().lower()

        try:
            target_dpi = int(raw.get("target_dpi") or 300)
        except Exception:
            target_dpi = 300
        if target_dpi <= 0:
            target_dpi = 300

        try:
            jpeg_quality = int(img_cfg.get("jpeg_quality", cfg.get("jpeg_quality", 100)))
        except Exception:
            jpeg_quality = 100
        jpeg_quality = max(1, min(100, jpeg_quality))

        try:
            jpeg_subsampling = int(img_cfg.get("jpeg_subsampling", cfg.get("jpeg_subsampling", 0)))
        except Exception:
            jpeg_subsampling = 0

        return {
            "mode": mode,
            "target_dpi": target_dpi,
            "output_format": output_format,
            "low_dpi_policy": low_dpi_policy,
            "jpeg_quality": jpeg_quality,
            "jpeg_subsampling": jpeg_subsampling,
        }

    def _drawings_smart_jpg_fidelity_enabled(self) -> bool:
        cfg = self._get_drawings_fidelity_config()
        return str(cfg.get("mode") or "") == "smart" and str(cfg.get("output_format") or "") == "jpg"

    def _get_drawings_display_width_mm_for_shape(self, shape_obj) -> float:
        width_point = 0.0
        try:
            width_point = float(getattr(shape_obj, "Width", 0.0) or 0.0)
        except Exception:
            width_point = 0.0
        if width_point <= 0:
            return 0.0

        width_mm = width_point * 0.3528
        cfg = getattr(self, "config", {}) or {}
        if isinstance(cfg, dict):
            xml_rules = cfg.get("xml_rules") or {}
            if isinstance(xml_rules, dict):
                try:
                    max_w = float(xml_rules.get("drawings_img_max_wi_mm") or 0.0)
                    if max_w > 0:
                        width_mm = min(width_mm, max_w)
                except Exception:
                    pass
        return float(width_mm)

    def _get_drawings_target_width_px(self, display_width_mm: float | None) -> int:
        cfg = self._get_drawings_fidelity_config()
        try:
            width_mm = float(display_width_mm or 0.0)
        except Exception:
            width_mm = 0.0
        if width_mm <= 0:
            return 0
        target_dpi = int(cfg.get("target_dpi") or 300)
        return int(math.ceil(width_mm / 25.4 * target_dpi))

    def _get_drawings_target_width_px_for_shape(self, shape_obj) -> int:
        return self._get_drawings_target_width_px(self._get_drawings_display_width_mm_for_shape(shape_obj))

    def _ensure_drawings_quality_state(self) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
        entries = getattr(self, "_drawings_quality_warnings", None)
        if not isinstance(entries, list):
            entries = []
            try:
                self._drawings_quality_warnings = entries
            except Exception:
                pass
        meta = getattr(self, "_drawings_media_quality_meta_by_file", None)
        if not isinstance(meta, dict):
            meta = {}
            try:
                self._drawings_media_quality_meta_by_file = meta
            except Exception:
                pass
        return entries, meta

    def _register_drawings_media_quality_meta(self, filename: str, meta: dict[str, object]) -> None:
        if not filename:
            return
        _, meta_by_file = self._ensure_drawings_quality_state()
        meta_by_file[str(filename)] = dict(meta or {})

    def _append_drawings_quality_entry(self, entry: dict[str, object]) -> None:
        if not isinstance(entry, dict):
            return
        entries, _ = self._ensure_drawings_quality_state()
        kind = str(entry.get("kind") or "").strip()
        temp_file = str(entry.get("temp_file") or "").strip()
        for old in entries:
            if not isinstance(old, dict):
                continue
            if kind and temp_file and old.get("kind") == kind and old.get("temp_file") == temp_file:
                old.update(entry)
                return
        entries.append(dict(entry))

    def _check_drawings_package_media_integrity(self, zip_path: str) -> bool:
        """Reject damaged raster package media before Word renders black or partial content."""
        zip_path = str(zip_path or "").strip()
        if not zip_path:
            return True

        ext = os.path.splitext(zip_path)[1].lower()
        if ext == ".jpeg":
            ext = ".jpg"
        elif ext == ".tiff":
            ext = ".tif"
        if ext not in {".bmp", ".gif", ".jpg", ".png", ".tif", ".webp"}:
            return True

        clean_docx = self._resolve_active_clean_docx_path()
        try:
            source_docx = os.path.abspath(str(getattr(self, "input_file_path", None) or ""))
        except Exception:
            source_docx = ""

        cache_key = (clean_docx, source_docx, zip_path)
        verified = getattr(self, "_drawings_verified_package_media", None)
        if not isinstance(verified, set):
            verified = set()
            self._drawings_verified_package_media = verified
        if cache_key in verified:
            return True

        candidates: list[tuple[str, bytes]] = []
        clean_bytes = self._read_docx_zip_bytes(clean_docx, zip_path) if clean_docx else None
        if clean_bytes:
            candidates.append(("active_docx", clean_bytes))
        if source_docx and source_docx != clean_docx:
            source_bytes = self._read_docx_zip_bytes(source_docx, zip_path)
            if source_bytes and source_bytes != clean_bytes:
                candidates.append(("source_docx", source_bytes))
        if not candidates:
            return True

        failures = []
        for source_kind, media_bytes in candidates:
            try:
                with Image.open(io.BytesIO(media_bytes)) as image:
                    image.load()
                verified.add(cache_key)
                return True
            except Exception as exc:
                failures.append(f"{source_kind}:{type(exc).__name__}")

        entry = {
            "level": "error",
            "kind": "source_media_corrupt",
            "file": os.path.basename(zip_path),
            "source_ext": ext,
            "zip_path": zip_path,
            "reason": ",".join(failures),
        }
        self._append_drawings_quality_entry(entry)
        self._drawings_media_integrity_failure = dict(entry)
        logger.error(
            "[DRAWINGS_SOURCE_MEDIA_CORRUPT] zip_path=%s ext=%s checks=%s",
            zip_path,
            ext,
            entry["reason"],
        )
        return False

    def _render_emf_bytes_to_png(
        self,
        emf_bytes,
        output_path: str,
        *,
        scale: float = 1.0,
        min_width: int = 1000,
        trim_render_margin: bool = False,
    ) -> bool:
        from core.clipboard_utils import render_emf_bytes_to_png

        return bool(
            render_emf_bytes_to_png(
                emf_bytes,
                output_path,
                scale=scale,
                min_width=min_width,
                trim_render_margin=trim_render_margin,
            )
        )

    def _render_drawings_emf_bytes_to_jpg(
        self,
        emf_bytes: bytes,
        output_path: str,
        *,
        target_width_px: int | None,
        target_dpi: int | None = None,
    ) -> bool:
        if not emf_bytes or not output_path:
            return False
        cfg = self._get_drawings_fidelity_config()
        try:
            min_width = int(target_width_px or 0)
        except Exception:
            min_width = 0
        if min_width <= 0:
            return False
        if target_dpi is None:
            target_dpi = int(cfg.get("target_dpi") or 300)

        tmp_png = f"{output_path}.render.png"
        try:
            rendered = bool(
                self._render_emf_bytes_to_png(
                    emf_bytes,
                    tmp_png,
                    scale=1.0,
                    min_width=min_width,
                    trim_render_margin=True,
                )
            )
            if not rendered or not os.path.exists(tmp_png):
                return False
            with Image.open(tmp_png) as im0:
                im = im0.convert("RGB")
                im.save(
                    output_path,
                    format="JPEG",
                    quality=int(cfg.get("jpeg_quality") or 100),
                    subsampling=int(cfg.get("jpeg_subsampling") or 0),
                    dpi=(int(target_dpi), int(target_dpi)),
                )
            try:
                with Image.open(output_path) as check_img:
                    return int(check_img.size[0]) >= min_width
            except Exception:
                return os.path.exists(output_path)
        finally:
            try:
                if os.path.exists(tmp_png):
                    os.remove(tmp_png)
            except Exception:
                pass

    def _maybe_record_drawings_bitmap_dpi_warning(
        self,
        *,
        filename: str,
        display_width_mm: float,
        pixel_width: int,
        pixel_height: int | None = None,
    ) -> None:
        if not filename or not self._drawings_smart_jpg_fidelity_enabled():
            return
        cfg = self._get_drawings_fidelity_config()
        if str(cfg.get("low_dpi_policy") or "") != "warn":
            return
        _, meta_by_file = self._ensure_drawings_quality_state()
        meta = meta_by_file.get(str(filename)) or {}
        source_ext = str(meta.get("source_ext") or "").lower()
        if source_ext == ".jpeg":
            source_ext = ".jpg"
        if source_ext not in (".png", ".jpg"):
            return
        try:
            width_mm = float(display_width_mm)
            width_px = int(pixel_width)
        except Exception:
            return
        if width_mm <= 0 or width_px <= 0:
            return
        effective_dpi = width_px / (width_mm / 25.4)
        target_dpi = int(cfg.get("target_dpi") or 300)
        if effective_dpi >= float(target_dpi):
            return

        entry = {
            "level": "warning",
            "kind": "low_effective_dpi",
            "temp_file": str(filename),
            "source_ext": source_ext,
            "effective_dpi": round(float(effective_dpi), 1),
            "target_dpi": target_dpi,
            "width_px": width_px,
            "height_px": int(pixel_height or 0),
            "display_width_mm": round(width_mm, 2),
        }
        self._append_drawings_quality_entry(entry)
        try:
            logger.warning(
                "[DRAWINGS_QUALITY] kind=low_effective_dpi file=%s source_ext=%s effective_dpi=%.1f target_dpi=%d width_px=%d display_width_mm=%.2f",
                filename,
                source_ext,
                float(effective_dpi),
                target_dpi,
                width_px,
                width_mm,
            )
        except Exception:
            pass

    def _identify_docx_section_key_from_header_text(self, text: str) -> str | None:
        try:
            identify = getattr(self, "identify_section", None)
            if callable(identify):
                key = identify(text)
                if key:
                    return str(key)
        except Exception:
            pass

        norm = re.sub(r"\s+", "", str(text or "").strip())
        mapping = {
            "\u6743\u5229\u8981\u6c42\u4e66": "claims",
            "\u8bf4\u660e\u4e66": "description",
            "\u8bf4\u660e\u4e66\u9644\u56fe": "drawings",
            "\u6458\u8981\u9644\u56fe": "abstract_drawings",
            "\u8bf4\u660e\u4e66\u6458\u8981": "abstract",
            "\u7533\u8bf7\u4fe1\u606f\u786e\u8ba4\u9875": "request_meta",
        }
        return mapping.get(norm)

    def _resolve_docx_section_key_from_sectpr(self, sect_pr, *, zf, rels_map: dict[str, str]) -> str | None:
        ns = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        }
        try:
            header_rids = sect_pr.xpath("./w:headerReference/@r:id", namespaces=ns)
        except Exception:
            header_rids = []

        for rid in header_rids:
            target = rels_map.get(str(rid or ""))
            zip_path = self._normalize_docx_target_to_zip_path(target or "")
            if not zip_path:
                continue
            try:
                header_xml = zf.read(zip_path)
                header_root = etree.fromstring(header_xml)
                header_text = "".join(header_root.xpath(".//w:t/text()", namespaces=ns))
            except Exception:
                header_text = ""
            key = self._identify_docx_section_key_from_header_text(header_text)
            if key:
                return key
        return None

    def _build_drawings_inline_package_queue(self, docx_path: str) -> list[dict[str, object]]:
        if not docx_path or (not os.path.exists(docx_path)):
            return []

        try:
            with zipfile.ZipFile(docx_path, "r") as zf:
                document_xml = zf.read("word/document.xml")
                rels_xml = zf.read("word/_rels/document.xml.rels")
                try:
                    root = etree.fromstring(document_xml)
                    rels_root = etree.fromstring(rels_xml)
                except Exception:
                    return []

                ns = {
                    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
                    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
                    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
                    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
                    "v": "urn:schemas-microsoft-com:vml",
                }
                rels: dict[str, str] = {}
                image_rels: dict[str, str] = {}
                try:
                    for rel in rels_root.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
                        rid = rel.get("Id")
                        target = rel.get("Target")
                        rtype = rel.get("Type")
                        if not rid or not target:
                            continue
                        rels[str(rid)] = str(target)
                        if rtype and rtype.endswith("/image"):
                            image_rels[str(rid)] = str(target)
                except Exception:
                    rels = {}
                    image_rels = {}

                if not image_rels:
                    return []

                items: list[dict[str, object]] = []
                queue_index = 0
                try:
                    paragraphs = root.xpath("./w:body/w:p[not(ancestor::w:tbl)]", namespaces=ns)
                except Exception:
                    paragraphs = []

                paragraph_sections: list[str | None] = [None] * len(paragraphs)
                cursor = 0
                for idx, para in enumerate(paragraphs):
                    try:
                        sect_nodes = para.xpath("./w:pPr/w:sectPr", namespaces=ns)
                    except Exception:
                        sect_nodes = []
                    if not sect_nodes:
                        continue
                    key = self._resolve_docx_section_key_from_sectpr(
                        sect_nodes[0],
                        zf=zf,
                        rels_map=rels,
                    )
                    if key:
                        for fill_idx in range(cursor, idx + 1):
                            paragraph_sections[fill_idx] = key
                    cursor = idx + 1
                try:
                    body_sect_nodes = root.xpath("./w:body/w:sectPr", namespaces=ns)
                except Exception:
                    body_sect_nodes = []
                if body_sect_nodes:
                    key = self._resolve_docx_section_key_from_sectpr(
                        body_sect_nodes[0],
                        zf=zf,
                        rels_map=rels,
                    )
                    if key:
                        for fill_idx in range(cursor, len(paragraphs)):
                            paragraph_sections[fill_idx] = key

                has_drawings_scope = any(section_key == "drawings" for section_key in paragraph_sections)
                try:
                    forced_drawings_scope = str(getattr(self, "forced_section_key", "") or "").strip() == "drawings"
                except Exception:
                    forced_drawings_scope = False
                if not has_drawings_scope and not forced_drawings_scope:
                    logger.info(
                        "[DRAWINGS_QUEUE_UNAVAILABLE] doc=%s reason=package_drawings_scope_unresolved",
                        docx_path,
                    )
                    return []
                for para_idx, para in enumerate(paragraphs):
                    para_section = paragraph_sections[para_idx] if para_idx < len(paragraph_sections) else None
                    if not forced_drawings_scope and para_section != "drawings":
                        continue
                    try:
                        media_nodes = para.xpath(
                            ".//wp:inline[.//a:blip[@r:embed]] | "
                            ".//w:pict[not(ancestor::w:object) and .//v:imagedata[@r:id]] | "
                            ".//w:object[.//v:imagedata[@r:id]]",
                            namespaces=ns,
                        )
                    except Exception:
                        media_nodes = []
                    for media_node in media_nodes:
                        object_kind = "drawingml_inline"
                        media_local_name = etree.QName(media_node).localname
                        if media_local_name in {"pict", "object"}:
                            object_kind = "vml_ole_preview" if media_local_name == "object" else "vml_inline"
                            try:
                                style = str(
                                    media_node.xpath("string(.//v:shape[1]/@style)", namespaces=ns) or ""
                                ).lower()
                            except Exception:
                                style = ""
                            if media_local_name == "pict" and "position:absolute" in style.replace(" ", ""):
                                continue
                            try:
                                rid = media_node.xpath(
                                    "string(.//v:imagedata[1]/@r:id)",
                                    namespaces=ns,
                                ) or None
                            except Exception:
                                rid = None
                        else:
                            try:
                                rid = media_node.xpath(
                                    "string(.//a:blip[1]/@r:embed)",
                                    namespaces=ns,
                                ) or None
                            except Exception:
                                rid = None
                        if not rid:
                            continue
                        target = image_rels.get(str(rid))
                        zip_path = self._normalize_docx_target_to_zip_path(target or "")
                        if not target or not zip_path:
                            continue
                        crop_info = None
                        try:
                            crop_info = self._extract_image_crop_from_openxml(
                                etree.tostring(media_node, encoding="utf-8")
                            )
                        except Exception:
                            crop_info = None
                        queue_index += 1
                        items.append(
                            {
                                "index": queue_index,
                                "rid": str(rid),
                                "target": str(target),
                                "zip_path": str(zip_path),
                                "crop_info": crop_info,
                                "section": "drawings" if forced_drawings_scope else str(para_section or ""),
                                "object_kind": object_kind,
                            }
                        )
                return items
        except Exception:
            return []

    def _rebuild_drawings_inline_package_queue_state(self) -> dict[str, object]:
        docx_path = self._resolve_active_clean_docx_path()
        items = self._build_drawings_inline_package_queue(docx_path)
        self._drawings_inline_package_queue_cache = {docx_path: items} if docx_path else {}
        state = {
            "docx_path": docx_path,
            "items": items,
            "index": 0,
            "disabled": False,
            "disable_reason": None,
        }
        self._drawings_inline_package_queue_state = state
        logger.info(
            "[DRAWINGS_QUEUE_REBUILD] doc=%s items=%d",
            docx_path,
            len(items),
        )
        return state

    def _get_drawings_inline_package_queue_state(self) -> dict[str, object]:
        docx_path = self._resolve_active_clean_docx_path()
        state = getattr(self, "_drawings_inline_package_queue_state", None)
        if isinstance(state, dict) and state.get("docx_path") == docx_path:
            return state

        cache = getattr(self, "_drawings_inline_package_queue_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._drawings_inline_package_queue_cache = cache

        items = cache.get(docx_path)
        if not isinstance(items, list):
            items = self._build_drawings_inline_package_queue(docx_path)
            cache[docx_path] = items

        state = {
            "docx_path": docx_path,
            "items": items,
            "index": 0,
            "disabled": False,
            "disable_reason": None,
        }
        self._drawings_inline_package_queue_state = state
        return state

    def _disable_drawings_inline_package_queue(self, reason: str, *, section_key: str | None = None) -> None:
        state = self._get_drawings_inline_package_queue_state()
        if bool(state.get("disabled")):
            return
        state["disabled"] = True
        state["disable_reason"] = str(reason or "unknown")
        state["disabled_section"] = str(section_key or "other")
        try:
            logger.warning(
                "[INLINE_QUEUE_DISABLE] reason=%s doc=%s index=%s total=%s queue_scope=drawings_inline section=%s",
                state["disable_reason"],
                state.get("docx_path"),
                int(state.get("index") or 0),
                len(state.get("items") or []),
                state.get("disabled_section"),
            )
        except Exception:
            pass

    def _consume_drawings_inline_package_item(
        self,
        *,
        runtime_rid: str | None = None,
        section_key: str | None = None,
    ) -> dict[str, object] | None:
        if section_key != "drawings":
            return None

        state = self._get_drawings_inline_package_queue_state()
        if bool(state.get("disabled")):
            return None

        items = state.get("items") or []
        idx = int(state.get("index") or 0)
        if idx >= len(items):
            self._disable_drawings_inline_package_queue("exhausted", section_key=section_key)
            return None

        item = items[idx]
        state["index"] = idx + 1
        if not isinstance(item, dict):
            self._disable_drawings_inline_package_queue("invalid_item", section_key=section_key)
            return None

        if runtime_rid:
            queue_rid = str(item.get("rid") or "")
            if queue_rid and queue_rid != str(runtime_rid):
                try:
                    mismatch_count = int(state.get("runtime_rid_mismatch_count") or 0) + 1
                    state["runtime_rid_mismatch_count"] = mismatch_count
                    state["last_runtime_rid_mismatch"] = {
                        "runtime": str(runtime_rid),
                        "queue": queue_rid,
                        "index": idx + 1,
                        "section": str(section_key or ""),
                    }
                except Exception:
                    pass
                try:
                    logger.info(
                        "[INLINE_QUEUE_RID_MISMATCH_IGNORED] runtime=%s queue=%s idx=%s doc=%s queue_scope=drawings_inline section=%s",
                        str(runtime_rid),
                        queue_rid,
                        idx + 1,
                        state.get("docx_path"),
                        str(section_key or ""),
                    )
                except Exception:
                    pass
        return item

    def _should_extract_drawings_from_media(
        self,
        *,
        crop_info: dict[str, float] | None,
        package_crop_info: dict[str, float] | None = None,
        explicit_pf_crop: dict[str, float] | None,
    ) -> bool:
        """Return whether drawings media extraction can still match the Word-visible range."""
        if crop_info or package_crop_info:
            return True
        if explicit_pf_crop:
            return False
        return True

    def _get_drawings_media_gate_reason(
        self,
        *,
        crop_info: dict[str, float] | None,
        package_crop_info: dict[str, float] | None = None,
        explicit_pf_crop: dict[str, float] | None,
    ) -> str:
        """Explain why drawings media extraction is allowed or blocked."""
        if crop_info:
            return "runtime_exact"
        if package_crop_info:
            return "package_exact"
        if explicit_pf_crop:
            return "blocked_pf_only"
        return ""

    def _get_drawings_display_frame(
        self,
        shape_obj,
        *,
        processed_img_size: tuple[int, int] | None = None,
    ) -> dict[str, float | str | None]:
        width_point = 0.0
        height_point = 0.0
        try:
            width_point = float(getattr(shape_obj, "Width", 0.0) or 0.0)
        except Exception:
            width_point = 0.0
        try:
            height_point = float(getattr(shape_obj, "Height", 0.0) or 0.0)
        except Exception:
            height_point = 0.0

        if width_point <= 0:
            width_point = 100.0

        if height_point > 0:
            return {
                "width_point": width_point,
                "height_point": height_point,
                "ratio_num": width_point,
                "ratio_den": height_point,
                "ratio_source": "word_display_frame",
            }

        ratio_num = None
        ratio_den = None
        try:
            w_px, h_px = processed_img_size or (0, 0)
            if int(w_px) > 0 and int(h_px) > 0:
                ratio_num = float(w_px)
                ratio_den = float(h_px)
        except Exception:
            ratio_num = None
            ratio_den = None

        return {
            "width_point": width_point,
            "height_point": None,
            "ratio_num": ratio_num,
            "ratio_den": ratio_den,
            "ratio_source": "processed_image_fallback",
        }

    def _log_drawings_size_provenance(
        self,
        *,
        object_kind: str,
        route: str,
        frame: dict[str, float | str | None] | None,
        captured_size: tuple[int, int] | None,
        final_size: tuple[int, int] | None,
        width_mm: float,
        height_mm: float,
    ) -> None:
        frame = frame if isinstance(frame, dict) else {}
        opt_meta = getattr(self.img_proc, "_last_drawings_opt_meta", {}) or {}
        original_size = opt_meta.get("original_size")
        normalized_size = opt_meta.get("final_size")
        edge_cropped = bool(opt_meta.get("edge_cropped"))
        if original_size and normalized_size and tuple(original_size) != tuple(normalized_size):
            normalization = "crop_and_pad" if edge_cropped else "pad_to_frame"
        else:
            normalization = "none"
        logger.info(
            "[DRAWINGS_SIZE] object=%s route=%s frame_pt=%sx%s captured_px=%s final_px=%s "
            "normalization=%s ratio_source=%s xml_wi_he_mm=%.2fx%.2f",
            str(object_kind or "drawing"),
            str(route or "UNKNOWN"),
            frame.get("width_point"),
            frame.get("height_point"),
            captured_size,
            final_size,
            normalization,
            frame.get("ratio_source") or "processed_image_fallback",
            float(width_mm),
            float(height_mm),
        )

    def _extract_image_rid_from_openxml(self, xml_content) -> str | None:
        if not xml_content:
            return None

        xml_bytes = None
        try:
            if isinstance(xml_content, bytes):
                xml_bytes = xml_content
            else:
                xml_text = re.sub(r"^\s*<\?xml[^>]*\?>", "", str(xml_content)).lstrip()
                xml_bytes = xml_text.encode("utf-8")
        except Exception:
            xml_bytes = None

        rid = None
        if xml_bytes:
            try:
                root = etree.fromstring(xml_bytes)
                ns = {
                    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
                    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
                    "v": "urn:schemas-microsoft-com:vml",
                }
                try:
                    rid = root.xpath("string(.//a:blip[1]/@r:embed)", namespaces=ns) or None
                except Exception:
                    rid = None
                if not rid:
                    try:
                        rid = root.xpath("string(.//v:imagedata[1]/@r:id)", namespaces=ns) or None
                    except Exception:
                        rid = None
            except Exception:
                rid = None

        if rid:
            try:
                rid = str(rid).strip()
            except Exception:
                rid = None
        if rid:
            return rid

        try:
            if xml_bytes:
                m = re.search(br"r:(?:embed|id)=\"([^\"]+)\"", xml_bytes)
                if m:
                    return m.group(1).decode("utf-8", errors="ignore")
        except Exception:
            return None

    def _extract_link_rid_from_openxml(self, xml_content) -> str | None:
        if not xml_content:
            return None

        xml_bytes = None
        try:
            if isinstance(xml_content, bytes):
                xml_bytes = xml_content
            else:
                xml_text = re.sub(r"^\s*<\?xml[^>]*\?>", "", str(xml_content)).lstrip()
                xml_bytes = xml_text.encode("utf-8")
        except Exception:
            xml_bytes = None

        rid = None
        if xml_bytes:
            try:
                root = etree.fromstring(xml_bytes)
                ns = {
                    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
                    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
                }
                try:
                    rid = root.xpath("string(.//a:blip[1]/@r:link)", namespaces=ns) or None
                except Exception:
                    rid = None
            except Exception:
                rid = None

        if rid:
            try:
                rid = str(rid).strip()
            except Exception:
                rid = None
        if rid:
            return rid

        try:
            if xml_bytes:
                m = re.search(br"r:link=\"([^\"]+)\"", xml_bytes)
                if m:
                    return m.group(1).decode("utf-8", errors="ignore")
        except Exception:
            return None
        return None

    def _extract_object_prog_id_from_openxml(self, xml_content) -> str | None:
        if not xml_content:
            return None

        xml_bytes = None
        try:
            if isinstance(xml_content, bytes):
                xml_bytes = xml_content
            else:
                xml_text = re.sub(r"^\s*<\?xml[^>]*\?>", "", str(xml_content)).lstrip()
                xml_bytes = xml_text.encode("utf-8")
        except Exception:
            xml_bytes = None

        prog_id = None
        if xml_bytes:
            try:
                root = etree.fromstring(xml_bytes)
                try:
                    prog_id = root.xpath("string(.//*[local-name()='OLEObject'][1]/@ProgID)") or None
                except Exception:
                    prog_id = None
            except Exception:
                prog_id = None

        if prog_id:
            try:
                prog_id = str(prog_id).strip()
            except Exception:
                prog_id = None
        if prog_id:
            return prog_id

        try:
            if xml_bytes:
                m = re.search(br"ProgID=\"([^\"]+)\"", xml_bytes)
                if m:
                    return m.group(1).decode("utf-8", errors="ignore")
        except Exception:
            return None
        return None

    def _classify_external_object(
        self,
        shape_obj,
        *,
        section_key: str | None = None,
        xml_content=None,
    ) -> dict[str, object]:
        if xml_content is None:
            try:
                rng = getattr(shape_obj, "Range", None)
                xml_content = getattr(rng, "WordOpenXML", None) if rng is not None else None
            except Exception:
                xml_content = None

        try:
            type_code = int(getattr(shape_obj, "Type", 0) or 0)
        except Exception:
            type_code = 0

        preview_rid = None
        try:
            preview_rid = self._extract_image_rid_from_openxml(xml_content)
        except Exception:
            preview_rid = None

        link_rid = None
        try:
            link_rid = self._extract_link_rid_from_openxml(xml_content)
        except Exception:
            link_rid = None

        prog_id = None
        try:
            prog_id = self._extract_object_prog_id_from_openxml(xml_content)
        except Exception:
            prog_id = None

        class_type = ""
        try:
            ole_fmt = getattr(shape_obj, "OLEFormat", None)
            class_type = str(getattr(ole_fmt, "ClassType", "") or "").strip()
        except Exception:
            class_type = ""
        if (not prog_id) and class_type:
            prog_id = class_type

        is_equation = False
        try:
            eq_checker = getattr(self, "_is_equation_shape", None)
            if callable(eq_checker):
                is_equation = bool(eq_checker(shape_obj))
        except Exception:
            is_equation = False

        section = str(section_key or "other")
        info: dict[str, object] = {
            "classifier": "unsupported",
            "object_kind": "external_object",
            "reason_code": "unsupported_external_object",
            "source_hint": str(prog_id or class_type or link_rid or preview_rid or "").strip(),
            "preview_rid": str(preview_rid or "").strip(),
            "link_rid": str(link_rid or "").strip(),
            "prog_id": str(prog_id or "").strip(),
            "class_type": str(class_type or "").strip(),
            "type_code": int(type_code),
            "section": section,
            "allow_word_render": False,
            "is_equation": bool(is_equation),
        }

        if type_code == wdInlineShapePicture:
            info["object_kind"] = "inline_picture"
            if preview_rid:
                info["classifier"] = "package_direct"
                info["reason_code"] = "embedded_media_package"
            else:
                info["classifier"] = "word_render_safe"
                info["reason_code"] = "inline_picture_word_render_safe"
                info["allow_word_render"] = True
            return info

        if type_code == wdInlineShapeLinkedPicture:
            info["object_kind"] = "linked_picture"
            if preview_rid:
                info["classifier"] = "preview_embedded"
                info["reason_code"] = "linked_picture_preview_embedded"
            else:
                info["classifier"] = "activation_risky"
                info["reason_code"] = "linked_picture_activation_required"
            return info

        if type_code == wdInlineShapeLinkedOLEObject:
            info["object_kind"] = "linked_ole"
            if preview_rid:
                info["classifier"] = "preview_embedded"
                info["reason_code"] = "linked_ole_preview_embedded"
            else:
                info["classifier"] = "activation_risky"
                info["reason_code"] = "linked_ole_activation_required"
            return info

        if type_code == wdInlineShapeEmbeddedOLEObject:
            info["object_kind"] = "embedded_ole"
            if is_equation:
                info["classifier"] = "word_render_safe"
                info["reason_code"] = "equation_ole_word_render_safe"
                info["allow_word_render"] = True
            elif preview_rid:
                info["classifier"] = "preview_embedded"
                info["reason_code"] = "embedded_ole_preview_embedded"
            elif prog_id or class_type:
                info["classifier"] = "activation_risky"
                info["reason_code"] = "embedded_ole_server_activation_required"
            return info

        if preview_rid and (link_rid or prog_id or class_type):
            info["classifier"] = "preview_embedded"
            info["reason_code"] = "floating_preview_embedded"
            info["object_kind"] = "floating_shape"
            return info

        if link_rid or prog_id or class_type:
            info["classifier"] = "activation_risky"
            info["reason_code"] = "floating_shape_activation_required"
            info["object_kind"] = "floating_shape"
            return info

        if preview_rid:
            info["classifier"] = "preview_embedded"
            info["reason_code"] = "embedded_preview_available"
            info["object_kind"] = "external_object"
            return info

        info["allow_word_render"] = True
        info["classifier"] = "word_render_safe"
        info["reason_code"] = "object_word_render_safe"
        return info

    def _safe_get_shape_range_start(self, shape_obj) -> int | None:
        try:
            rng = getattr(shape_obj, "Range", None)
            if rng is None:
                return None
            return int(getattr(rng, "Start", None))
        except Exception:
            return None

    def _record_object_fallback_failure(
        self,
        *,
        shape_obj=None,
        classification: dict[str, object] | None = None,
        parent_node=None,
        section_key: str | None = None,
        paragraph_index: int | None = None,
        range_start: int | None = None,
        resolution_code: str,
        message: str | None = None,
    ) -> dict[str, object]:
        section = str(section_key or "").strip()
        if not section and isinstance(classification, dict):
            section = str(classification.get("section") or "").strip()
        if not section and parent_node is not None:
            try:
                section = str(self._get_parent_section_key(parent_node) or "").strip()
            except Exception:
                section = ""
        if not section:
            section = "other"

        if paragraph_index is None:
            try:
                paragraph_index = int(getattr(self, "_current_paragraph_index", None))
            except Exception:
                paragraph_index = None

        if range_start is None and shape_obj is not None:
            range_start = self._safe_get_shape_range_start(shape_obj)

        classifier = ""
        object_kind = ""
        source_hint = ""
        reason_code = ""
        if isinstance(classification, dict):
            classifier = str(classification.get("classifier") or "").strip()
            object_kind = str(classification.get("object_kind") or "").strip()
            source_hint = str(classification.get("source_hint") or "").strip()
            reason_code = str(classification.get("reason_code") or "").strip()

        if not message:
            if resolution_code == "preview_extracted":
                message = "该对象已改用静态图片，请核对内容是否完整。"
            elif resolution_code == "placeholder_inserted":
                message = "该对象缺少源程序或源文件，已生成占位图片，请补充原始内容后重新转换。"
            else:
                message = "该对象未能完整转换，请核对转换结果。"

        record = {
            "object_kind": object_kind or "external_object",
            "section": section,
            "paragraph_index": paragraph_index,
            "range_start": range_start,
            "classifier": classifier or "unsupported",
            "source_hint": source_hint,
            "reason_code": reason_code or "external_object_fallback",
            "resolution_code": str(resolution_code or "").strip(),
            "message": str(message or "").strip(),
        }

        items = getattr(self, "object_fallback_failures", None)
        if not isinstance(items, list):
            items = []
            try:
                self.object_fallback_failures = items
            except Exception:
                pass
        items.append(record)
        return record

    def _estimate_external_object_dimensions_mm(
        self,
        shape_obj,
        *,
        section_key: str,
        processed_size: tuple[int, int],
    ) -> tuple[float, float]:
        width_point = 0.0
        height_point = 0.0
        try:
            width_point = float(getattr(shape_obj, "Width", 0.0) or 0.0)
        except Exception:
            width_point = 0.0
        try:
            height_point = float(getattr(shape_obj, "Height", 0.0) or 0.0)
        except Exception:
            height_point = 0.0
        if width_point <= 0:
            width_point = 100.0

        try:
            if str(section_key) == "drawings" and hasattr(self.img_proc, "calculate_drawings_dimensions"):
                width_mm, height_mm = self.img_proc.calculate_drawings_dimensions(
                    width_point,
                    (height_point if height_point > 0 else None),
                    processed_size,
                )
                return float(width_mm), float(height_mm)
        except Exception:
            pass

        try:
            if hasattr(self.img_proc, "calculate_xml_dimensions"):
                width_mm, height_mm = self.img_proc.calculate_xml_dimensions(width_point, processed_size)
                return float(width_mm), float(height_mm)
        except Exception:
            pass

        width_mm = float(width_point) * 0.3528
        if height_point > 0:
            height_mm = float(height_point) * 0.3528
        else:
            try:
                w_px, h_px = processed_size
                height_mm = width_mm * float(h_px) / max(float(w_px), 1.0)
            except Exception:
                height_mm = width_mm * 0.5
        return float(width_mm), float(height_mm)

    def _get_external_object_label(self, classification: dict[str, object] | None) -> str:
        object_kind = ""
        if isinstance(classification, dict):
            object_kind = str(classification.get("object_kind") or "").strip()
            prog_id = str(classification.get("prog_id") or "").strip()
            source_hint = str(classification.get("source_hint") or "").strip()
            source_lower = f"{prog_id} {source_hint}".lower()
            if "visio" in source_lower:
                return "Visio/OLE"
        mapping = {
            "linked_picture": "Linked Picture",
            "linked_ole": "OLE/Linked Object",
            "embedded_ole": "OLE Object",
            "floating_shape": "Floating Object",
            "inline_picture": "Inline Picture",
            "external_object": "外部对象",
        }
        return mapping.get(object_kind, "外部对象")

    def _load_placeholder_font(self, size: int):
        candidates = [
            "msyh.ttc",
            "simhei.ttf",
            "simsun.ttc",
            "arial.ttf",
        ]
        for name in candidates:
            try:
                return ImageFont.truetype(name, size=size)
            except Exception:
                continue
        try:
            return ImageFont.load_default()
        except Exception:
            return None

    def _emit_external_object_placeholder(
        self,
        shape_obj,
        *,
        parent_node=None,
        section_key: str | None = None,
        classification: dict[str, object] | None = None,
        resolution_code: str = "placeholder_inserted",
        message: str | None = None,
    ) -> tuple[str, float, float, None]:
        import uuid

        section = str(section_key or "").strip()
        if not section and parent_node is not None:
            try:
                section = str(self._get_parent_section_key(parent_node) or "").strip()
            except Exception:
                section = ""
        if not section:
            section = "other"

        width_point = 0.0
        height_point = 0.0
        try:
            width_point = float(getattr(shape_obj, "Width", 0.0) or 0.0)
        except Exception:
            width_point = 0.0
        try:
            height_point = float(getattr(shape_obj, "Height", 0.0) or 0.0)
        except Exception:
            height_point = 0.0
        if width_point <= 0:
            width_point = 100.0
        if height_point <= 0:
            height_point = max(width_point * 0.45, 60.0)

        width_mm_est = max(float(width_point) * 0.3528, 40.0)
        height_mm_est = max(float(height_point) * 0.3528, 20.0)
        width_px = max(420, int(round(width_mm_est * 6.0)))
        height_px = max(220, int(round(height_mm_est * 6.0)))

        image = Image.new("RGB", (width_px, height_px), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((12, 12, width_px - 12, height_px - 12), outline=(196, 196, 196), width=3)

        title_font = self._load_placeholder_font(26)
        body_font = self._load_placeholder_font(18)
        meta_font = self._load_placeholder_font(14)

        section_map = {
            "drawings": "说明书附图",
            "description": "说明书",
            "claims": "权利要求书",
            "abstract": "摘要",
            "other": "正文",
        }
        range_start = self._safe_get_shape_range_start(shape_obj)
        position_hint = f"{section_map.get(section, section)} / {range_start or '-'}"
        lines = [
            ("外部对象未导出", title_font, (68, 68, 68)),
            (self._get_external_object_label(classification), body_font, (90, 90, 90)),
            ("该对象未能完整转换，请核对并替换", body_font, (120, 120, 120)),
            (position_hint, meta_font, (150, 150, 150)),
        ]

        current_y = 42
        for text, font, fill in lines:
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                text_h = int(bbox[3] - bbox[1])
            except Exception:
                text_h = 20
            draw.text((32, current_y), text, fill=fill, font=font)
            current_y += text_h + 18

        filename = f"obj_{uuid.uuid4().hex[:8]}.jpg"
        output_path = os.path.join(self.config["paths"]["temp_dir"], filename)
        image.save(
            output_path,
            format="JPEG",
            quality=self.config.get("jpeg_quality", 95),
            subsampling=self.config.get("jpeg_subsampling", 0),
            dpi=(300, 300),
        )
        width_mm, height_mm = self._estimate_external_object_dimensions_mm(
            shape_obj,
            section_key=section,
            processed_size=(width_px, height_px),
        )
        self._record_object_fallback_failure(
            shape_obj=shape_obj,
            classification=classification,
            parent_node=parent_node,
            section_key=section,
            resolution_code=resolution_code,
            message=message,
        )
        return filename, float(width_mm), float(height_mm), None

    def _is_inline_picture_shape(self, shape_obj) -> bool:
        try:
            type_code = int(getattr(shape_obj, "Type", 0) or 0)
        except Exception:
            return False
        return type_code in (wdInlineShapePicture, wdInlineShapeLinkedPicture)

    def _parse_crop_ratio(self, value, *, base: float = 100000.0) -> float:
        if value is None:
            return 0.0
        try:
            text = str(value).strip()
            if not text:
                return 0.0
            if text.endswith("%"):
                ratio = float(text[:-1]) / 100.0
            else:
                ratio = float(text)
                if abs(ratio) > 1:
                    ratio = ratio / float(base)
        except Exception:
            return 0.0
        if ratio < 0:
            return 0.0
        if ratio > 1:
            return 1.0
        return ratio

    def _extract_image_crop_from_openxml(self, xml_content) -> dict[str, float] | None:
        if not xml_content:
            return None

        xml_bytes = None
        try:
            if isinstance(xml_content, bytes):
                xml_bytes = xml_content
            else:
                xml_text = re.sub(r"^\s*<\?xml[^>]*\?>", "", str(xml_content)).lstrip()
                xml_bytes = xml_text.encode("utf-8")
        except Exception:
            xml_bytes = None

        if not xml_bytes:
            return None

        try:
            root = etree.fromstring(xml_bytes)
        except Exception:
            return None

        try:
            src_rect_nodes = root.xpath("//*[local-name()='srcRect']")
        except Exception:
            src_rect_nodes = []
        if src_rect_nodes:
            attrs = src_rect_nodes[0].attrib
            crop = {
                "l": self._parse_crop_ratio(attrs.get("l")),
                "t": self._parse_crop_ratio(attrs.get("t")),
                "r": self._parse_crop_ratio(attrs.get("r")),
                "b": self._parse_crop_ratio(attrs.get("b")),
            }
            if any(value > 0 for value in crop.values()):
                return crop

        try:
            vml_nodes = root.xpath("//*[local-name()='imagedata']")
        except Exception:
            vml_nodes = []
        for node in vml_nodes:
            crop_map = {}
            for key, value in node.attrib.items():
                local_key = key.rsplit("}", 1)[-1].lower()
                if local_key == "cropleft":
                    crop_map["l"] = self._parse_crop_ratio(value)
                elif local_key == "cropright":
                    crop_map["r"] = self._parse_crop_ratio(value)
                elif local_key == "croptop":
                    crop_map["t"] = self._parse_crop_ratio(value)
                elif local_key == "cropbottom":
                    crop_map["b"] = self._parse_crop_ratio(value)
            if crop_map:
                crop = {
                    "l": float(crop_map.get("l", 0.0)),
                    "t": float(crop_map.get("t", 0.0)),
                    "r": float(crop_map.get("r", 0.0)),
                    "b": float(crop_map.get("b", 0.0)),
                }
                if any(value > 0 for value in crop.values()):
                    return crop
        return None

    def _extract_image_crop_from_pictureformat(self, shape_obj) -> dict[str, float] | None:
        """Best-effort: detect non-zero Word PictureFormat crop for InlineShape pictures.

        Notes:
        - Word's PictureFormat.Crop* values are not reliably convertible to srcRect ratios without knowing
          the underlying (pre-crop) image size in Word units.
        - We only need a truthy marker to disable secondary aggressive trimming; return a dict with keys
          l/t/r/b (always 0.0) plus raw values for logging purposes.
        """
        try:
            if not self._is_inline_picture_shape(shape_obj):
                return None
        except Exception:
            return None

        pf = getattr(shape_obj, "PictureFormat", None)
        if not pf:
            return None

        raw = {}
        for key in ("CropLeft", "CropRight", "CropTop", "CropBottom"):
            try:
                raw[key] = float(getattr(pf, key, 0.0) or 0.0)
            except Exception:
                raw[key] = 0.0

        # Non-zero crop indicates the visible representation is already cropped in Word.
        if any(abs(v) > 1e-3 for v in raw.values()):
            return {"l": 0.0, "t": 0.0, "r": 0.0, "b": 0.0, "_source": "PictureFormat", "_raw": raw}
        return None

    def _apply_explicit_crop_to_image(self, image, crop_info: dict[str, float] | None):
        if image is None or not crop_info:
            return image
        try:
            w_px, h_px = image.size
        except Exception:
            return image

        left_ratio = float(crop_info.get("l", 0.0) or 0.0)
        top_ratio = float(crop_info.get("t", 0.0) or 0.0)
        right_ratio = float(crop_info.get("r", 0.0) or 0.0)
        bottom_ratio = float(crop_info.get("b", 0.0) or 0.0)

        left_px = int(round(w_px * left_ratio))
        top_px = int(round(h_px * top_ratio))
        right_px = int(round(w_px * (1.0 - right_ratio)))
        bottom_px = int(round(h_px * (1.0 - bottom_ratio)))

        if right_px <= left_px or bottom_px <= top_px:
            return image
        try:
            logger.debug(
                "[SRCRECT_CROP] size=%s ratios=(%s,%s,%s,%s) box=(%s,%s,%s,%s)",
                (w_px, h_px),
                left_ratio,
                top_ratio,
                right_ratio,
                bottom_ratio,
                left_px,
                top_px,
                right_px,
                bottom_px,
            )
        except Exception:
            pass
        try:
            return image.crop((left_px, top_px, right_px, bottom_px))
        except Exception:
            return image

    def _apply_explicit_crop_to_file(self, image_path: str, crop_info: dict[str, float] | None) -> tuple[int, int] | None:
        if not image_path or not crop_info:
            return None
        try:
            with Image.open(image_path) as _img0:
                img = _img0.copy()
                fmt = str(getattr(_img0, "format", "") or "")
        except Exception:
            return None

        cropped = self._apply_explicit_crop_to_image(img, crop_info)
        if cropped is None:
            return None

        fmt_upper = fmt.upper()
        save_kwargs = {}
        if fmt_upper == "PNG":
            save_kwargs = {"format": "PNG", "dpi": (300, 300)}
        elif fmt_upper in {"TIFF", "TIF"}:
            save_kwargs = {"format": "TIFF", "compression": "tiff_deflate"}
        elif fmt_upper in {"JPEG", "JPG"}:
            save_kwargs = {
                "format": "JPEG",
                "quality": self.config.get("jpeg_quality", 95),
                "subsampling": self.config.get("jpeg_subsampling", 0),
                "dpi": (300, 300),
            }

        try:
            if save_kwargs:
                cropped.save(image_path, **save_kwargs)
            else:
                cropped.save(image_path)
            return cropped.size
        except Exception:
            return None

    def _get_docx_rels_map(self, docx_path: str) -> dict[str, str]:
        try:
            cache = getattr(self, "_docx_rels_cache", None)
            if not isinstance(cache, dict):
                cache = {}
                self._docx_rels_cache = cache
            if docx_path in cache and isinstance(cache.get(docx_path), dict):
                return cache.get(docx_path) or {}
        except Exception:
            cache = None

        mapping: dict[str, str] = {}
        try:
            if not docx_path or (not os.path.exists(docx_path)):
                mapping = {}
            else:
                with zipfile.ZipFile(docx_path, "r") as zf:
                    rels_xml = zf.read("word/_rels/document.xml.rels")
                root = etree.fromstring(rels_xml)
                for rel in root.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
                    rid = rel.get("Id")
                    target = rel.get("Target")
                    rtype = rel.get("Type")
                    if not rid or not target:
                        continue
                    if rtype and rtype.endswith("/image"):
                        mapping[str(rid)] = str(target)
        except Exception:
            mapping = {}

        try:
            if cache is None:
                cache = getattr(self, "_docx_rels_cache", None)
            if isinstance(cache, dict):
                cache[docx_path] = mapping
        except Exception:
            pass
        return mapping

    def _normalize_docx_target_to_zip_path(self, target: str) -> str | None:
        if not target:
            return None
        try:
            t = str(target).replace("\\", "/")
        except Exception:
            return None
        t = t.lstrip("/")
        while t.startswith("../"):
            t = t[3:]
        if t.startswith("word/"):
            return t
        return "word/" + t

    def _read_docx_zip_bytes(self, docx_path: str, zip_path: str) -> bytes | None:
        if not docx_path or not zip_path:
            return None
        try:
            if not os.path.exists(docx_path):
                return None
            with zipfile.ZipFile(docx_path, "r") as zf:
                return zf.read(zip_path)
        except Exception:
            return None

    def _pick_better_media_bytes(self, b1: bytes | None, b2: bytes | None) -> bytes | None:
        if b1 and not b2:
            return b1
        if b2 and not b1:
            return b2
        if not b1 and not b2:
            return None

        try:
            with Image.open(io.BytesIO(b1)) as im1:
                w1, h1 = im1.size
        except Exception:
            w1, h1 = 0, 0
        try:
            with Image.open(io.BytesIO(b2)) as im2:
                w2, h2 = im2.size
        except Exception:
            w2, h2 = 0, 0

        try:
            if w1 > 0 and h1 > 0 and w2 > 0 and h2 > 0:
                if (w1, h1) != (w2, h2):
                    # 尺寸不一致：视为可能误配，优先保留第一份（通常来自 temp_clean）
                    return b1
                area1 = int(w1) * int(h1)
                area2 = int(w2) * int(h2)
                if area2 > area1:
                    return b2
                if area1 > area2:
                    return b1
        except Exception:
            pass

        try:
            if len(b2) > len(b1):
                return b2
        except Exception:
            pass
        return b1

    def _extract_drawings_media_zip_path_to_temp(
        self,
        *,
        zip_path: str,
        filename_prefix: str,
        force_jpg_for_non_tiff: bool = False,
        target_width_px: int | None = None,
    ) -> tuple[str, str] | None:
        if not zip_path:
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




# Attach extracted heavy methods for compatibility.
ImageShapeMixin._extract_drawings_media_to_temp = _extract_drawings_media_to_temp
ImageShapeMixin.handle_shape = handle_shape
ImageShapeMixin._process_floating_shapes = _process_floating_shapes

__all__ = [
    "ImageShapeMixin",
    "wdInlineShapePicture",
    "wdInlineShapeLinkedPicture",
    "wdInlineShapeEmbeddedOLEObject",
    "wdInlineShapeLinkedOLEObject",
]
