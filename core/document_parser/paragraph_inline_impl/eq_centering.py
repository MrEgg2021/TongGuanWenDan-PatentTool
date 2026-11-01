import os
import re

from core.logging_utils import swallow_exception


def apply_eq_centering(self, para, segments, *, raw_text_full: str, has_inline: bool, is_claim: bool, parent_tag: str, eq_center_cfg: dict):
    precise_cfg = (eq_center_cfg.get("precise") or {}) if isinstance(eq_center_cfg, dict) else {}
    eq_display_ratio = 1.0
    try:
        cfg = getattr(self, "config", {}) or {}
        eq_display_ratio = float(cfg.get("equation_display_scale_ratio", 1.0))
    except Exception:
        swallow_exception("eq_display_ratio")
        eq_display_ratio = 1.0
    if not eq_display_ratio or eq_display_ratio <= 0:
        eq_display_ratio = 1.0
    eq_display_ratio = max(0.4, min(1.0, float(eq_display_ratio)))

    px_per_mm_override = None
    try:
        mm_per_px = float(cfg.get("omath_mm_per_px", 0.1))
        if mm_per_px > 0:
            px_per_mm_override = 1.0 / float(mm_per_px)
    except Exception:
        swallow_exception("px_per_mm_override")
        px_per_mm_override = None

    eq_meta_by_file = getattr(self, "_eq_centering_desc_equation_images", None)
    if not isinstance(eq_meta_by_file, dict):
        eq_meta_by_file = {}
        try:
            setattr(self, "_eq_centering_desc_equation_images", eq_meta_by_file)
        except Exception:
            swallow_exception("setattr_eq_meta")
            pass

    try:
        line_width_mm = float(precise_cfg.get("line_width_mm", 165.0))
    except (TypeError, ValueError):
        swallow_exception("line_width_mm")
        line_width_mm = 165.0
    try:
        desc_reserved_mm = float(precise_cfg.get("desc_reserved_mm", 22.0))
    except (TypeError, ValueError):
        swallow_exception("desc_reserved_mm")
        desc_reserved_mm = 22.0
    # 权利要求：保持历史行为（使用整行宽度居中），不额外预留“(n)”编号宽度。
    claim_body_target_width_mm = line_width_mm
    claim_line_target_width_mm = line_width_mm
    desc_line_target_width_mm = line_width_mm - desc_reserved_mm
    if desc_line_target_width_mm <= 0:
        desc_line_target_width_mm = line_width_mm

    try:
        raw_text_full_for_eq = raw_text_full if has_inline else (para.Range.Text or "")
        try:
            raw_text_full_for_eq = (raw_text_full_for_eq or "").replace("\x0b", "\n")
        except Exception:
            swallow_exception("replace_vertical_tab")
            pass
        try:
            clean_text_full_for_eq = self._sanitize_text((raw_text_full_for_eq or "").replace("\r", "")).strip()
        except Exception:
            swallow_exception("_sanitize_text")
            clean_text_full_for_eq = ""
        eq_lines = self._detect_visual_eq_lines_in_raw(raw_text_full_for_eq)
    except Exception:
        swallow_exception("detect_eq_lines")
        eq_lines = []
        clean_text_full_for_eq = ""

    if (not eq_lines) and clean_text_full_for_eq and re.fullmatch(r"[（(]?\s*\d+\s*[)）]?", clean_text_full_for_eq):
        eq_lines = [(0, len(raw_text_full_for_eq or ""))]

    should_detect_eq_with_num = False
    if is_claim:
        should_detect_eq_with_num = True
    else:
        should_detect_eq_with_num = (parent_tag == "description") or bool(eq_lines and len(eq_lines) == 1)

    if should_detect_eq_with_num:
        num_pattern = re.compile(r"[（(]\d+[)）]")
        eq_indices = []
        for i, seg in enumerate(segments):
            if seg.get("kind") == "img" and seg.get("is_equation"):
                eq_indices.append(i)

        if len(eq_indices) == 1:
            eq_idx = eq_indices[0]
            for j in range(eq_idx + 1, len(segments)):
                seg = segments[j]
                if seg.get("kind") != "text":
                    continue
                txt = seg.get("text_plain") or seg.get("text") or ""
                m = num_pattern.search(txt)
                if not m:
                    continue
                if (parent_tag == "description") and (not is_claim):
                    if not re.fullmatch(r"[（(]\s*\d+\s*[)）]", txt.strip()):
                        continue
                prefix = txt[: m.start()]
                if prefix.strip() != "":
                    continue

                between_ok = True
                for k in range(eq_idx + 1, j):
                    mid = segments[k]
                    if mid.get("kind") != "text":
                        continue
                    mid_txt = mid.get("text_plain") or mid.get("text") or ""
                    if mid_txt.strip() != "":
                        between_ok = False
                        break
                if not between_ok:
                    continue

                kind = "claim_eq_with_num" if is_claim else "desc_eq_with_num"
                segments[eq_idx]["eq_line_kind"] = kind
                seg["is_eq_number"] = True

                if (not is_claim) and parent_tag == "description":
                    try:
                        fn = segments[eq_idx].get("filename")
                        if isinstance(fn, str) and fn:
                            eq_meta_by_file[fn] = {"with_num": True}
                    except Exception:
                        swallow_exception("eq_meta_with_num")
                        pass
                break

    try:
        temp_dir = os.path.abspath(self.config["paths"]["temp_dir"])
    except Exception:
        temp_dir = None

    if temp_dir and parent_tag == "description":
        for seg in segments:
            if seg.get("kind") == "img" and seg.get("is_equation") and seg.get("eq_line_kind") == "desc_eq_with_num":
                try:
                    if seg.get("_eq_center_padded"):
                        continue
                    image_path = os.path.join(temp_dir, seg["filename"])
                    new_w, new_h = self.img_proc.pad_equation_for_centering(
                        image_path,
                        seg["width_mm"],
                        seg["height_mm"],
                        target_width_mm=desc_line_target_width_mm,
                        scale_ratio=eq_display_ratio,
                        px_per_mm_override=seg.get("px_per_mm_for_ole") or px_per_mm_override,
                    )
                    seg["width_mm"] = new_w
                    seg["height_mm"] = new_h
                    seg["_eq_center_padded"] = True

                    try:
                        fn = seg.get("filename")
                        if isinstance(fn, str) and fn:
                            meta = eq_meta_by_file.get(fn) or {}
                            if not isinstance(meta, dict):
                                meta = {}
                            meta["with_num"] = True
                            meta["padded"] = True
                            eq_meta_by_file[fn] = meta
                    except Exception:
                        pass
                except Exception:
                    pass

    if temp_dir and parent_tag in ("description", "cn-abstract") and len(segments) > 1:
        for seg in segments:
            if seg.get("kind") == "img" and seg.get("is_equation") and seg.get("is_big") and not seg.get("eq_line_kind"):
                try:
                    if seg.get("_eq_center_padded"):
                        continue
                    image_path = os.path.join(temp_dir, seg["filename"])
                    target_w = desc_line_target_width_mm if parent_tag == "description" else line_width_mm
                    new_w, new_h = self.img_proc.pad_equation_for_centering(
                        image_path,
                        seg["width_mm"],
                        seg["height_mm"],
                        target_width_mm=target_w,
                        scale_ratio=eq_display_ratio,
                        px_per_mm_override=seg.get("px_per_mm_for_ole") or px_per_mm_override,
                    )
                    seg["width_mm"] = new_w
                    seg["height_mm"] = new_h
                    seg["_eq_center_padded"] = True

                    if parent_tag == "description":
                        try:
                            fn = seg.get("filename")
                            if isinstance(fn, str) and fn:
                                meta = eq_meta_by_file.get(fn) or {}
                                if not isinstance(meta, dict):
                                    meta = {}
                                meta.setdefault("with_num", False)
                                meta["padded"] = True
                                eq_meta_by_file[fn] = meta
                        except Exception:
                            pass
                except Exception:
                    pass

    if temp_dir and parent_tag == "cn-abstract":
        for seg in segments:
            if seg.get("kind") == "img" and seg.get("is_equation") and seg.get("eq_line_kind") == "desc_eq_with_num":
                try:
                    if seg.get("_eq_center_padded"):
                        continue
                    image_path = os.path.join(temp_dir, seg["filename"])
                    new_w, new_h = self.img_proc.pad_equation_for_centering(
                        image_path,
                        seg["width_mm"],
                        seg["height_mm"],
                        target_width_mm=line_width_mm,
                        scale_ratio=eq_display_ratio,
                        px_per_mm_override=seg.get("px_per_mm_for_ole") or px_per_mm_override,
                    )
                    seg["width_mm"] = new_w
                    seg["height_mm"] = new_h
                    seg["_eq_center_padded"] = True
                except Exception:
                    pass

    if temp_dir and is_claim:
        for seg in segments:
            if seg.get("kind") == "img" and seg.get("is_equation") and seg.get("eq_line_kind") == "claim_eq_with_num":
                try:
                    if seg.get("_eq_center_padded"):
                        continue
                    image_path = os.path.join(temp_dir, seg["filename"])
                    new_w, new_h = self.img_proc.pad_equation_for_centering(
                        image_path,
                        seg["width_mm"],
                        seg["height_mm"],
                        target_width_mm=claim_body_target_width_mm,
                        scale_ratio=eq_display_ratio,
                        px_per_mm_override=seg.get("px_per_mm_for_ole") or px_per_mm_override,
                    )
                    seg["width_mm"] = new_w
                    seg["height_mm"] = new_h
                    seg["_eq_center_padded"] = True
                except Exception:
                    pass

        for seg in segments:
            if (
                seg.get("kind") == "img"
                and seg.get("is_equation")
                and seg.get("is_big")
                and not seg.get("eq_line_kind")
            ):
                try:
                    if seg.get("_eq_center_padded"):
                        continue
                    image_path = os.path.join(temp_dir, seg["filename"])
                    new_w, new_h = self.img_proc.pad_equation_for_centering(
                        image_path,
                        seg["width_mm"],
                        seg["height_mm"],
                        target_width_mm=claim_line_target_width_mm,
                        scale_ratio=eq_display_ratio,
                        px_per_mm_override=seg.get("px_per_mm_for_ole") or px_per_mm_override,
                    )
                    seg["width_mm"] = new_w
                    seg["height_mm"] = new_h
                    seg["_eq_center_padded"] = True
                except Exception:
                    pass

    if temp_dir and (is_claim or parent_tag == "description" or parent_tag == "cn-abstract") and len(segments) == 1:
        seg0 = segments[0]
        if (
            seg0.get("kind") == "img"
            and seg0.get("is_equation")
            and not seg0.get("eq_line_kind")
        ):
            try:
                if seg0.get("_eq_center_padded"):
                    return segments
                image_path = os.path.join(temp_dir, seg0["filename"])

                if is_claim:
                    target_w = claim_line_target_width_mm
                    seg0["is_big"] = True
                elif parent_tag == "description":
                    target_w = desc_line_target_width_mm
                else:
                    target_w = line_width_mm

                new_w, new_h = self.img_proc.pad_equation_for_centering(
                    image_path,
                    seg0["width_mm"],
                    seg0["height_mm"],
                    target_width_mm=target_w,
                    scale_ratio=eq_display_ratio,
                    px_per_mm_override=seg0.get("px_per_mm_for_ole") or px_per_mm_override,
                )
                seg0["width_mm"] = new_w
                seg0["height_mm"] = new_h
                seg0["_eq_center_padded"] = True

                if (not is_claim) and parent_tag == "description":
                    try:
                        fn = seg0.get("filename")
                        if isinstance(fn, str) and fn:
                            meta = eq_meta_by_file.get(fn) or {}
                            if not isinstance(meta, dict):
                                meta = {}
                            meta.setdefault("with_num", False)
                            meta["padded"] = True
                            eq_meta_by_file[fn] = meta
                    except Exception:
                        pass
            except Exception:
                pass

    return segments


__all__ = ["apply_eq_centering"]
