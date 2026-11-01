from __future__ import annotations

import math
import os
import uuid

import fitz
from PIL import Image, ImageDraw

from core.logging_utils import logger
from core.word_engine_impl.com_compat import add_hidden_document
from .preview_fit_ops import fragment_can_bypass_split
from .process_steps.types import TableCaptureResult, TablePdfFragment


def _row_is_mostly_white(img_local: Image.Image, y: int, *, white_threshold: int = 245) -> bool:
    try:
        w_local, _ = img_local.size
        step = max(1, int(w_local / 800))
        px = img_local.load()
        for x in range(0, w_local, step):
            r, g, b = px[x, y]
            if r < white_threshold or g < white_threshold or b < white_threshold:
                return False
        return True
    except Exception:
        return False


def _find_vertical_bounds(img_local: Image.Image) -> tuple[int, int]:
    try:
        _w_local, h_local = img_local.size
    except Exception:
        return 0, 0
    top_idx = 0
    bottom_idx = h_local - 1
    while top_idx < bottom_idx and _row_is_mostly_white(img_local, top_idx):
        top_idx += 1
    while bottom_idx > top_idx and _row_is_mostly_white(img_local, bottom_idx):
        bottom_idx -= 1
    return int(top_idx), int(bottom_idx)


def _row_is_line(img_local: Image.Image, y: int, *, dark_threshold: int = 200, ratio: float = 0.65) -> bool:
    try:
        w_local, _ = img_local.size
        step = max(1, int(w_local / 800))
        px = img_local.load()
        dark = 0
        total = 0
        for x in range(0, w_local, step):
            r, g, b = px[x, y]
            if r < dark_threshold and g < dark_threshold and b < dark_threshold:
                dark += 1
            total += 1
        if total <= 0:
            return False
        return (float(dark) / float(total)) >= float(ratio)
    except Exception:
        return False


def _count_leading_line_rows(img_local: Image.Image, max_rows: int = 4) -> int:
    try:
        _w_local, h_local = img_local.size
    except Exception:
        return 0
    count = 0
    max_rows = min(int(max_rows), int(h_local))
    for y in range(0, max_rows):
        if _row_is_line(img_local, y):
            count += 1
        else:
            break
    return int(count)


def _count_trailing_line_rows(img_local: Image.Image, max_rows: int = 4) -> int:
    try:
        _w_local, h_local = img_local.size
    except Exception:
        return 0
    count = 0
    max_rows = min(int(max_rows), int(h_local))
    for y in range(h_local - 1, h_local - max_rows - 1, -1):
        if y < 0:
            break
        if _row_is_line(img_local, y):
            count += 1
        else:
            break
    return int(count)


def _count_leading_blank_rows(img_local: Image.Image, max_rows: int = 12) -> int:
    try:
        _w_local, h_local = img_local.size
    except Exception:
        return 0
    count = 0
    max_rows = min(int(max_rows), int(h_local))
    for y in range(0, max_rows):
        if _row_is_mostly_white(img_local, y):
            count += 1
        else:
            break
    return int(count)


def _count_trailing_blank_rows(img_local: Image.Image, max_rows: int = 12) -> int:
    try:
        _w_local, h_local = img_local.size
    except Exception:
        return 0
    count = 0
    max_rows = min(int(max_rows), int(h_local))
    for y in range(h_local - 1, h_local - max_rows - 1, -1):
        if y < 0:
            break
        if _row_is_mostly_white(img_local, y):
            count += 1
        else:
            break
    return int(count)


def _trim_blank_seam_between_pages(curr: Image.Image, nxt: Image.Image, max_rows: int = 12):
    trailing_blank = _count_trailing_blank_rows(curr, max_rows=max_rows)
    leading_blank = _count_leading_blank_rows(nxt, max_rows=max_rows)
    trim_top = min(int(trailing_blank), int(leading_blank))
    diag = {
        'trimmed': False,
        'trim_top': 0,
        'trailing_blank': int(trailing_blank),
        'leading_blank': int(leading_blank),
    }
    if trim_top <= 0:
        return curr, nxt, diag

    try:
        w_local, h_local = nxt.size
    except Exception:
        return curr, nxt, diag
    if (int(h_local) - int(trim_top)) < 8:
        return curr, nxt, diag

    nxt = nxt.crop((0, int(trim_top), int(w_local), int(h_local)))
    diag['trimmed'] = True
    diag['trim_top'] = int(trim_top)
    return curr, nxt, diag


def _calculate_width_variance_ratio(widths: list[int] | tuple[int, ...]) -> float:
    values = sorted(float(w) for w in list(widths or []) if float(w) > 0)
    if not values:
        return 0.0
    mid = len(values) // 2
    if len(values) % 2 == 1:
        median = float(values[mid])
    else:
        median = float(values[mid - 1] + values[mid]) / 2.0
    if median <= 0:
        return 0.0
    return max(abs(float(w) - median) / median for w in values)


def _page_batch_has_invalid_width_variance(widths: list[int] | tuple[int, ...], threshold: float) -> bool:
    try:
        limit = float(threshold)
    except Exception:
        limit = 0.08
    return float(_calculate_width_variance_ratio(widths)) > (float(limit) + 1e-9)


def _pad_pages_to_common_width(images: list[Image.Image]) -> list[Image.Image]:
    if not images:
        return []
    try:
        target_width = max(int(img.size[0]) for img in images)
    except Exception:
        return list(images)

    normalized: list[Image.Image] = []
    for img in list(images):
        try:
            width_local, height_local = img.size
        except Exception:
            normalized.append(img)
            continue
        if int(width_local) >= int(target_width):
            normalized.append(img)
            continue
        canvas = Image.new('RGB', (int(target_width), int(height_local)), (255, 255, 255))
        offset_x = max(0, int((int(target_width) - int(width_local)) / 2))
        canvas.paste(img, (int(offset_x), 0))
        normalized.append(canvas)
    return normalized


def _trim_table_pdf_page(owner, img: Image.Image, *, page_index: int) -> Image.Image | None:
    try:
        w_local, h_local = img.size
    except Exception:
        return None
    top_idx, bottom_idx = _find_vertical_bounds(img)
    if bottom_idx <= top_idx:
        if logger.isEnabledFor(10):
            logger.debug('[TABLE_PDF_PAGE_SKIP] page=%s reason=blank_after_trim', int(page_index))
        return None

    cropped_page = img.crop((0, int(top_idx), int(w_local), int(bottom_idx) + 1))
    if logger.isEnabledFor(10):
        logger.debug(
            '[TABLE_PDF_PAGE_TRIM] page=%s top=%s bottom=%s orig_h=%s new_h=%s',
            int(page_index),
            int(top_idx),
            int(bottom_idx),
            int(h_local),
            int(cropped_page.size[1]),
        )

    if owner is not None:
        try:
            cropped_page = owner.img_proc._crop_white_borders(cropped_page, padding_ratio=0.0, padding_min=4)
        except Exception:
            pass
    return cropped_page


def _prepare_processed_pages(images: list[Image.Image], owner=None) -> list[Image.Image]:
    processed_pages: list[Image.Image] = []
    for idx, img in enumerate(images):
        trimmed = _trim_table_pdf_page(owner, img, page_index=int(idx + 1))
        if trimmed is not None:
            processed_pages.append(trimmed)

    if not processed_pages:
        return []

    for i in range(len(processed_pages) - 1):
        curr = processed_pages[i]
        nxt = processed_pages[i + 1]
        trailing = _count_trailing_line_rows(curr, max_rows=4)
        leading = _count_leading_line_rows(nxt, max_rows=4)
        if trailing > 0 and leading > 0:
            try:
                w_local, h_local = nxt.size
            except Exception:
                w_local, h_local = 0, 0
            trim_top = int(leading)
            if (h_local - trim_top) >= 8:
                nxt = nxt.crop((0, trim_top, int(w_local), int(h_local)))
                processed_pages[i + 1] = nxt
                if logger.isEnabledFor(10):
                    logger.debug('[TABLE_PDF_BORDER_DEDUPE] seam=%s trim_top=%s', int(i + 1), int(trim_top))

        curr2, nxt2, seam_diag = _trim_blank_seam_between_pages(curr, nxt, max_rows=12)
        processed_pages[i] = curr2
        processed_pages[i + 1] = nxt2
        if seam_diag.get('trimmed') and logger.isEnabledFor(10):
            logger.debug(
                '[TABLE_PDF_BLANK_SEAM_TRIM] seam=%s trim_top=%s trailing_blank=%s leading_blank=%s',
                int(i + 1),
                int(seam_diag.get('trim_top', 0)),
                int(seam_diag.get('trailing_blank', 0)),
                int(seam_diag.get('leading_blank', 0)),
            )

    return processed_pages


def _export_selection_pdf(doc, rng, pdf_path: str, *, rng_start, rng_end, table_rows, table_cols) -> bool:
    try:
        if doc is not None:
            try:
                doc.Activate()
            except Exception:
                pass
        rng.Select()
        wdExportFormatPDF = 17
        wdExportSelection = 1
        if doc is None:
            return False
        doc.ExportAsFixedFormat(OutputFileName=pdf_path, ExportFormat=wdExportFormatPDF, Range=wdExportSelection)
        logger.info('[TABLE_PDF_EXPORT] method=selection ok=True')
        return True
    except Exception as exc:
        logger.warning(
            '[TABLE_PDF_EXPORT] method=selection ok=False range_start=%s range_end=%s rows=%s cols=%s error_type=%s error=%s',
            rng_start,
            rng_end,
            table_rows,
            table_cols,
            type(exc).__name__,
            str(exc),
        )
        return False


def _export_blank_doc_pdf(app, rng, pdf_path: str, width_point: float, *, rng_start, rng_end, table_rows, table_cols) -> bool:
    new_doc = None
    try:
        new_doc = add_hidden_document(app, logger=logger)
        pasted = False
        try:
            rng.Copy()
            new_doc.Range(0, 0).Paste()
            pasted = True
        except Exception:
            pasted = False
        if not pasted:
            try:
                new_doc.Range(0, 0).FormattedText = rng
                pasted = True
            except Exception:
                pasted = False
        if not pasted:
            try:
                new_doc.Range(0, 0).Text = rng.Text
                pasted = True
            except Exception:
                pasted = False
        if not pasted:
            raise RuntimeError('unable to copy table range into blank document')

        try:
            ps = getattr(new_doc, 'PageSetup', None)
            if ps is not None:
                ps.LeftMargin = 0
                ps.RightMargin = 0
                ps.TopMargin = 0
                ps.BottomMargin = 0
                ps.Gutter = 0
                page_width_point = float(width_point) if width_point else 0.0
                if page_width_point > 0:
                    ps.PageWidth = max(72.0, page_width_point + 12.0)
        except Exception:
            pass

        wdExportFormatPDF = 17
        new_doc.ExportAsFixedFormat(OutputFileName=pdf_path, ExportFormat=wdExportFormatPDF)
        logger.info('[TABLE_PDF_EXPORT] method=copy ok=True')
        return True
    except Exception as exc:
        logger.warning(
            '[TABLE_PDF_EXPORT] method=copy ok=False range_start=%s range_end=%s rows=%s cols=%s error_type=%s error=%s',
            rng_start,
            rng_end,
            table_rows,
            table_cols,
            type(exc).__name__,
            str(exc),
        )
        return False
    finally:
        if new_doc is not None:
            try:
                new_doc.Close(False)
            except Exception:
                pass


def _render_pdf_pages(pdf_path: str, pdf_dpi: int) -> list[Image.Image]:
    doc_pdf = fitz.open(pdf_path)
    try:
        if doc_pdf.page_count == 0:
            return []
        zoom = float(pdf_dpi) / 72.0
        mat = fitz.Matrix(zoom, zoom)
        images: list[Image.Image] = []
        for page in doc_pdf:
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            images.append(img)
        return images
    finally:
        doc_pdf.close()


def _build_fragment_output_path(output_path: str, page_index: int, total_pages: int) -> str:
    if int(total_pages) <= 1:
        return str(output_path)
    base_name, _ = os.path.splitext(os.path.basename(output_path))
    return os.path.join(os.path.dirname(output_path), f'{base_name}_p{int(page_index)}.jpg')


def _cleanup_fragment_file(owner, filename: str | None) -> None:
    if not filename:
        return
    remover = getattr(owner, '_remove_temp_image_if_exists', None)
    if not callable(remover):
        return
    try:
        remover(filename)
    except Exception:
        return


def _cleanup_fragment_files(owner, fragments: list[TablePdfFragment]) -> None:
    for fragment in list(fragments or []):
        _cleanup_fragment_file(owner, fragment.file)


def _resolve_fragment_temp_path(owner, filename: str) -> str:
    temp_dir = os.path.abspath(owner.config['paths']['temp_dir'])
    return os.path.join(temp_dir, str(filename))


def _content_bbox_for_visual_slice(img_local: Image.Image, *, threshold: int = 245) -> tuple[int, int, int, int]:
    gray = img_local.convert('L')
    mask = gray.point(lambda px: 255 if int(px) < int(threshold) else 0)
    bbox = mask.getbbox()
    if bbox:
        return int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
    width_px, height_px = img_local.size
    return 0, 0, int(width_px), int(height_px)


def _gray_row_dark_ratio(gray: Image.Image, y: int, x0: int, x1: int, *, threshold: int = 245) -> float:
    width_px, height_px = gray.size
    y = max(0, min(int(y), int(height_px) - 1))
    x0 = max(0, min(int(x0), int(width_px)))
    x1 = max(x0 + 1, min(int(x1), int(width_px)))
    px = gray.load()
    dark = 0
    total = 0
    for x in range(x0, x1):
        if int(px[x, y]) < int(threshold):
            dark += 1
        total += 1
    if total <= 0:
        return 1.0
    return float(dark) / float(total)


def _gray_row_longest_dark_run_ratio(gray: Image.Image, y: int, x0: int, x1: int, *, threshold: int = 210) -> float:
    width_px, height_px = gray.size
    y = max(0, min(int(y), int(height_px) - 1))
    x0 = max(0, min(int(x0), int(width_px)))
    x1 = max(x0 + 1, min(int(x1), int(width_px)))
    px = gray.load()
    best_run = 0
    current_run = 0
    for x in range(x0, x1):
        if int(px[x, y]) < int(threshold):
            current_run += 1
            if current_run > best_run:
                best_run = int(current_run)
        else:
            current_run = 0
    return float(best_run) / float(max(1, x1 - x0))


def _gray_row_has_horizontal_rule(gray: Image.Image, y: int, bounds: tuple[int, int, int, int]) -> tuple[bool, float]:
    x0, _top, x1, _bottom = bounds
    dark_ratio = _gray_row_dark_ratio(gray, int(y), int(x0), int(x1), threshold=230)
    run_ratio = _gray_row_longest_dark_run_ratio(gray, int(y), int(x0), int(x1), threshold=210)
    score = max(float(dark_ratio), float(run_ratio))
    return bool(run_ratio >= 0.85 or dark_ratio >= 0.85), float(score)


def _gray_row_has_clear_band(
    gray: Image.Image,
    y: int,
    bounds: tuple[int, int, int, int],
    *,
    radius: int = 3,
    max_dark_ratio: float = 0.025,
    max_long_run_ratio: float = 0.03,
) -> tuple[bool, float]:
    x0, _top, x1, _bottom = bounds
    _width_px, height_px = gray.size
    y = int(y)
    y0 = max(0, y - int(radius))
    y1 = min(int(height_px) - 1, y + int(radius))
    worst_ratio = 0.0
    for row in range(y0, y1 + 1):
        ratio = _gray_row_dark_ratio(gray, int(row), int(x0), int(x1), threshold=245)
        run_ratio = _gray_row_longest_dark_run_ratio(gray, int(row), int(x0), int(x1), threshold=210)
        worst_ratio = max(float(worst_ratio), float(ratio))
        if ratio > float(max_dark_ratio) or run_ratio > float(max_long_run_ratio):
            return False, float(worst_ratio)
    return True, float(worst_ratio)


def _find_safe_visual_slice_cut(
    gray: Image.Image,
    bounds: tuple[int, int, int, int],
    target_y: int,
    min_y: int,
    max_y: int,
) -> tuple[int, str, float] | None:
    target_y = int(target_y)
    min_y = int(min_y)
    max_y = int(max_y)
    if min_y > max_y:
        return None

    candidate_rows = sorted(range(min_y, max_y + 1), key=lambda row: (abs(int(row) - int(target_y)), int(row)))
    for y in candidate_rows:
        has_rule, score = _gray_row_has_horizontal_rule(gray, int(y), bounds)
        if has_rule:
            return int(y), 'horizontal_rule', float(score)

    for y in candidate_rows:
        has_clear_band, score = _gray_row_has_clear_band(gray, int(y), bounds)
        if has_clear_band:
            return int(y), 'blank_band', float(score)

    return None


def _choose_visual_slice_cuts(
    img_local: Image.Image,
    slice_count: int,
    *,
    max_slice_px: int | None = None,
) -> tuple[list[int], list[str], list[float]]:
    _w_local, h_local = img_local.size
    slice_count = int(slice_count)
    if slice_count <= 1:
        return [], [], []

    max_slice_px_value = int(max_slice_px or 0)
    min_slice_px = max(1, min(64, int(h_local / max(slice_count * 10, 1))))
    search_window = max(32, min(900, int(h_local / 8)))
    gray = img_local.convert('L')
    bounds = _content_bbox_for_visual_slice(img_local)
    cuts: list[int] = []
    modes: list[str] = []
    scores: list[float] = []
    prev_cut = 0

    for cut_index in range(1, slice_count):
        target_y = int(round(float(h_local) * float(cut_index) / float(slice_count)))
        remaining_slices = int(slice_count - cut_index)
        lower = max(prev_cut + min_slice_px, target_y - search_window)
        upper = min(int(h_local) - (remaining_slices * min_slice_px), target_y + search_window)
        if max_slice_px_value > 0:
            lower = max(lower, int(h_local) - (remaining_slices * max_slice_px_value))
            upper = min(upper, prev_cut + max_slice_px_value)

        if lower > upper:
            cut_min = prev_cut + min_slice_px
            cut_max = int(h_local) - (remaining_slices * min_slice_px)
            if max_slice_px_value > 0:
                cut_min = max(cut_min, int(h_local) - (remaining_slices * max_slice_px_value))
                cut_max = min(cut_max, prev_cut + max_slice_px_value)
            if cut_min > cut_max:
                return [], [], []
            safe_cut = _find_safe_visual_slice_cut(gray, bounds, min(max(target_y, cut_min), cut_max), cut_min, cut_max)
        else:
            safe_cut = _find_safe_visual_slice_cut(gray, bounds, target_y, lower, upper)

        if safe_cut is None:
            return [], [], []

        cut_y, mode, score = safe_cut
        cut_y = min(max(int(cut_y), lower), upper)
        cuts.append(int(cut_y))
        modes.append(str(mode))
        scores.append(float(score))
        prev_cut = int(cut_y)

    return cuts, modes, scores


def _build_visual_slice_output_path(fragment_path: str, slice_index: int) -> str:
    base_name, _ = os.path.splitext(os.path.basename(fragment_path))
    return os.path.join(os.path.dirname(fragment_path), f'{base_name}_s{int(slice_index)}.jpg')


def _process_visual_slice_fragment(
    owner,
    slice_img: Image.Image,
    output_path: str,
    *,
    original_fragment: TablePdfFragment,
    width_point: float,
) -> TablePdfFragment | None:
    processed_size = owner.img_proc.process_image(
        slice_img,
        output_path,
        is_equation=False,
        crop=False,
        apply_enhancement=True,
        safe_crop_guard=True,
    )
    if not processed_size:
        return None
    w_px, h_px = int(processed_size[0]), int(processed_size[1])
    width_mm, height_mm = owner.img_proc.calculate_xml_dimensions(float(width_point), (int(w_px), int(h_px)))
    return TablePdfFragment(
        file=os.path.basename(output_path),
        page_index=int(original_fragment.page_index),
        width_px=int(w_px),
        height_px=int(h_px),
        width_mm=float(width_mm),
        height_mm=float(height_mm),
        source_method=str(original_fragment.source_method),
    )


def _load_visual_slice_fragment_images(owner, fragments: list[TablePdfFragment]) -> tuple[list[Image.Image], list[str]] | None:
    images: list[Image.Image] = []
    paths: list[str] = []
    for fragment in list(fragments or []):
        fragment_path = _resolve_fragment_temp_path(owner, fragment.file)
        if not os.path.isfile(fragment_path):
            return None
        try:
            with Image.open(fragment_path) as opened:
                images.append(opened.convert('RGB').copy())
            paths.append(str(fragment_path))
        except OSError:
            return None
    if not images:
        return None
    return images, paths


def _stack_visual_slice_images(images: list[Image.Image]) -> Image.Image | None:
    normalized = _pad_pages_to_common_width(list(images or []))
    if not normalized:
        return None
    width_px = max(int(img.size[0]) for img in normalized)
    height_px = sum(int(img.size[1]) for img in normalized)
    if width_px <= 0 or height_px <= 0:
        return None
    stacked = Image.new('RGB', (int(width_px), int(height_px)), (255, 255, 255))
    offset_y = 0
    for img in normalized:
        stacked.paste(img, (0, int(offset_y)))
        offset_y += int(img.size[1])
    return stacked


def _draw_visual_slice_closure(slice_img: Image.Image, x_bounds: tuple[int, int], *, close_top: bool, close_bottom: bool) -> Image.Image:
    if not close_top and not close_bottom:
        return slice_img
    width_px, height_px = slice_img.size
    if width_px <= 0 or height_px <= 0:
        return slice_img
    x0, x1 = x_bounds
    x0 = max(0, min(int(x0), int(width_px) - 1))
    x1 = max(int(x0), min(int(x1), int(width_px) - 1))
    draw = ImageDraw.Draw(slice_img)
    line_width = max(2, min(4, int(round(float(width_px) / 1200.0)) + 1))
    if close_top:
        draw.line((x0, 0, x1, 0), fill=(0, 0, 0), width=int(line_width))
    if close_bottom:
        draw.line((x0, int(height_px) - 1, x1, int(height_px) - 1), fill=(0, 0, 0), width=int(line_width))
    return slice_img


def _visual_slice_pdf_fragments(
    owner,
    fragments: list[TablePdfFragment],
    *,
    width_point: float,
    max_height_mm: float,
) -> list[TablePdfFragment] | None:
    if float(max_height_mm) <= 0:
        return None
    fragments = list(fragments or [])
    loaded = _load_visual_slice_fragment_images(owner, fragments)
    if loaded is None:
        return None
    images, fragment_paths = loaded
    stacked_img = _stack_visual_slice_images(images)
    if stacked_img is None:
        return None

    width_px, height_px = stacked_img.size
    total_height_mm = sum(float(fragment.height_mm) for fragment in fragments)
    if int(width_px) <= 0:
        return None

    if total_height_mm <= 0:
        return None
    min_slice_count = max(2, int(math.ceil(float(total_height_mm) / float(max_height_mm))))
    if int(height_px) < int(min_slice_count):
        return None

    max_slice_px = int(math.floor(float(max_height_mm) * float(height_px) / float(total_height_mm)))
    max_slice_count = int(min_slice_count)
    cuts: list[int] = []
    modes: list[str] = []
    scores: list[float] = []
    slice_count = int(min_slice_count)
    for candidate_slice_count in range(int(min_slice_count), int(max_slice_count) + 1):
        candidate_cuts, candidate_modes, candidate_scores = _choose_visual_slice_cuts(
            stacked_img,
            int(candidate_slice_count),
            max_slice_px=max(1, int(max_slice_px)),
        )
        if len(candidate_cuts) == int(candidate_slice_count) - 1:
            cuts = list(candidate_cuts)
            modes = list(candidate_modes)
            scores = list(candidate_scores)
            slice_count = int(candidate_slice_count)
            break
    if len(cuts) != int(slice_count) - 1:
        logger.warning(
            '[TABLE_PDF_FRAGMENT_VISUAL_SLICE_FAIL] file=%s total_height_mm=%.2f max_height_mm=%.2f min_slices=%s reason=no_safe_cut',
            str(fragments[0].file) if fragments else '',
            float(total_height_mm),
            float(max_height_mm),
            int(min_slice_count),
        )
        return None
    boundaries = [0] + list(cuts) + [int(height_px)]
    generated: list[TablePdfFragment] = []
    content_bounds = _content_bbox_for_visual_slice(stacked_img)
    x_bounds = (int(content_bounds[0]), int(content_bounds[2]) - 1)
    first_fragment_path = fragment_paths[0]
    first_fragment = fragments[0]

    for idx, (top_y, bottom_y) in enumerate(zip(boundaries, boundaries[1:]), start=1):
        if int(bottom_y) <= int(top_y):
            _cleanup_fragment_files(owner, generated)
            return None
        slice_img = stacked_img.crop((0, int(top_y), int(width_px), int(bottom_y)))
        slice_img = _draw_visual_slice_closure(
            slice_img,
            x_bounds,
            close_top=int(idx) > 1,
            close_bottom=int(idx) < int(slice_count),
        )
        output_path = _build_visual_slice_output_path(first_fragment_path, int(idx))
        sliced_fragment = _process_visual_slice_fragment(
            owner,
            slice_img,
            output_path,
            original_fragment=first_fragment,
            width_point=float(width_point),
        )
        if sliced_fragment is None:
            _cleanup_fragment_file(owner, os.path.basename(output_path))
            _cleanup_fragment_files(owner, generated)
            return None
        generated.append(sliced_fragment)

    if any(float(item.height_mm) > float(max_height_mm) + 1e-6 for item in generated):
        _cleanup_fragment_files(owner, generated)
        return None

    _cleanup_fragment_files(owner, fragments)
    logger.info(
        '[TABLE_PDF_FRAGMENT_VISUAL_SLICE] page=%s file=%s original_height_mm=%.2f max_height_mm=%.2f slices=%s slice_heights_mm=%s cut_modes=%s mode=group total_height_mm=%.2f cuts_px=%s cut_scores=%s boundary_closed=True',
        int(first_fragment.page_index),
        str(first_fragment.file),
        float(total_height_mm),
        float(max_height_mm),
        int(len(generated)),
        '|'.join(f'{float(item.height_mm):.2f}' for item in generated),
        '|'.join(modes) if modes else 'safe',
        float(total_height_mm),
        '|'.join(str(int(cut)) for cut in cuts),
        '|'.join(f'{float(score):.3f}' for score in scores),
    )
    return generated


def _expand_overlimit_pdf_fragments(
    owner,
    fragments: list[TablePdfFragment],
    *,
    width_point: float,
    max_height_mm: float,
) -> list[TablePdfFragment] | None:
    fragments = list(fragments or [])
    needs_visual_slicing = False
    for fragment in list(fragments or []):
        if fragment_can_bypass_split(owner, float(fragment.height_mm), hard_limit_mm=float(max_height_mm)):
            continue
        needs_visual_slicing = True
        break

    if not needs_visual_slicing:
        return fragments

    return _visual_slice_pdf_fragments(
        owner,
        fragments,
        width_point=float(width_point),
        max_height_mm=float(max_height_mm),
    )


def _build_pdf_fragments(owner, normalized_pages: list[Image.Image], output_path: str, width_point: float, *, source_method: str) -> list[TablePdfFragment]:
    fragments: list[TablePdfFragment] = []
    total_pages = len(normalized_pages)
    logical_width_point = float(width_point) if width_point else 400.0
    if logical_width_point <= 0:
        logical_width_point = 400.0

    for page_index, page_img in enumerate(list(normalized_pages), start=1):
        fragment_path = _build_fragment_output_path(output_path, int(page_index), int(total_pages))
        processed_size = owner.img_proc.process_image(
            page_img,
            fragment_path,
            is_equation=False,
            crop=False,
            apply_enhancement=True,
            safe_crop_guard=True,
        )
        if not processed_size:
            _cleanup_fragment_files(owner, fragments)
            return []
        w_px, h_px = int(processed_size[0]), int(processed_size[1])
        width_mm, height_mm = owner.img_proc.calculate_xml_dimensions(float(logical_width_point), (int(w_px), int(h_px)))
        fragments.append(
            TablePdfFragment(
                file=os.path.basename(fragment_path),
                page_index=int(page_index),
                width_px=int(w_px),
                height_px=int(h_px),
                width_mm=float(width_mm),
                height_mm=float(height_mm),
                source_method=str(source_method),
            )
        )
    return fragments


def _range_has_vertical_merge(rng) -> bool:
    try:
        xml_content = getattr(rng, 'WordOpenXML', None)
        if xml_content:
            xml_text = str(xml_content)
            return ('<w:vMerge' in xml_text) or ('vMerge' in xml_text)
    except Exception:
        return False
    return False


def _detect_hard_table(owner, rng, table_ref) -> bool:
    reasons: list[str] = []
    cfg = getattr(owner, 'config', {}) or {}
    table_cfg = (cfg.get('table_capture') or {}) if isinstance(cfg, dict) else {}
    try:
        row_threshold = int((table_cfg or {}).get('hard_table_row_threshold', 20) or 20)
    except Exception:
        row_threshold = 20

    try:
        row_count = int(table_ref.Rows.Count)
    except Exception:
        row_count = 0
    if row_count >= int(row_threshold):
        reasons.append('row_count')

    if _range_has_vertical_merge(rng):
        reasons.append('vmerge')

    for reason, detector_name in (
        ('ole', '_table_range_has_ole'),
        ('drawings', '_table_range_has_drawings'),
        ('explicit_crop', '_table_range_has_explicit_crop'),
    ):
        detector = getattr(owner, detector_name, None)
        if callable(detector):
            try:
                if detector(rng):
                    reasons.append(reason)
            except Exception:
                pass

    try:
        from .process_steps.split_flow import _build_row_top_map, _collect_row_heights

        row_top_map = _build_row_top_map(table_ref)
        row_heights = _collect_row_heights(table_ref)
        estimated_total_pt = sum(float(v) for v in list(row_heights or []))
        max_height_cm = float(getattr(owner, '_get_table_splitting_max_height_cm')())
        target_slice_pt = float(max_height_cm) * 72.0 / 2.54
        if estimated_total_pt > float(target_slice_pt):
            reasons.append('estimated_overflow')
        try:
            doc = table_ref.Range.Document
            page_height_pt = float(doc.PageSetup.PageHeight)
        except Exception:
            page_height_pt = 29.7 * 72.0 / 2.54
        if any(float(top_pt) >= float(page_height_pt) for top_pt in row_top_map.values()):
            reasons.append('cross_page')
    except Exception:
        pass

    if reasons:
        logger.info('[TABLE_PDF_FIRST] hard_table=True reasons=%s', ','.join(dict.fromkeys(reasons)))
    return bool(reasons)


def _capture_table_pdf_first_result(self, rng, *, current_section_key: str, width_point: float | None = None) -> TableCaptureResult:
    rng_start = None
    rng_end = None
    table_rows = None
    table_cols = None
    try:
        rng_start = int(getattr(rng, 'Start', 0) or 0)
    except Exception:
        rng_start = None
    try:
        rng_end = int(getattr(rng, 'End', 0) or 0)
    except Exception:
        rng_end = None
    try:
        table_ref = rng.Tables(1)
    except Exception:
        table_ref = None
    if table_ref is not None:
        try:
            table_rows = int(table_ref.Rows.Count)
        except Exception:
            table_rows = None
        try:
            table_cols = int(table_ref.Columns.Count)
        except Exception:
            table_cols = None
    logger.info(
        '[TABLE_CAPTURE_PATH] method=pdf_first section=%s range_start=%s range_end=%s rows=%s cols=%s',
        str(current_section_key),
        rng_start,
        rng_end,
        table_rows,
        table_cols,
    )

    app = getattr(self.word, 'app', None)
    if app is None:
        return TableCaptureResult(failure_code='render_export_failed')

    cfg = getattr(self, 'config', {}) or {}
    table_cfg = cfg.get('table_capture', {}) or {}
    try:
        pdf_dpi = int(table_cfg.get('pdf_dpi', 600) or 600)
    except Exception:
        pdf_dpi = 600
    try:
        variance_threshold = float(table_cfg.get('hard_table_page_width_variance_ratio', 0.08) or 0.08)
    except Exception:
        variance_threshold = 0.08

    try:
        temp_dir = os.path.abspath(self.config['paths']['temp_dir'])
    except Exception:
        temp_dir = None
    if not temp_dir:
        return TableCaptureResult(failure_code='render_export_failed')

    output_path = os.path.join(temp_dir, f'tbl_{uuid.uuid4().hex[:8]}.jpg')
    base_name, _ = os.path.splitext(os.path.basename(output_path))
    pdf_path = os.path.join(temp_dir, f'{base_name}_tbl.pdf')

    hard_table = _detect_hard_table(self, rng, table_ref) if table_ref is not None else _range_has_vertical_merge(rng)

    try:
        doc = getattr(rng, 'Document', None)
    except Exception:
        doc = None

    used_blank_doc_fallback = False
    processed_pages: list[Image.Image] = []
    source_method = 'selection'
    diagnostic_code = None

    selection_ok = _export_selection_pdf(
        doc,
        rng,
        pdf_path,
        rng_start=rng_start,
        rng_end=rng_end,
        table_rows=table_rows,
        table_cols=table_cols,
    )
    if selection_ok:
        images = _render_pdf_pages(pdf_path, pdf_dpi)
        logger.info('[TABLE_PDF_RENDER] pages=%d', int(len(images)))
        processed_pages = _prepare_processed_pages(images, owner=self)
        if _page_batch_has_invalid_width_variance([img.size[0] for img in processed_pages], variance_threshold):
            diagnostic_code = 'pdf_page_invalid'
            processed_pages = []
    else:
        diagnostic_code = 'selection_export_failed'

    if not selection_ok or (not processed_pages):
        used_blank_doc_fallback = True
        source_method = 'blank_doc'
        if not _export_blank_doc_pdf(
            app,
            rng,
            pdf_path,
            float(width_point) if width_point else 0.0,
            rng_start=rng_start,
            rng_end=rng_end,
            table_rows=table_rows,
            table_cols=table_cols,
        ):
            return TableCaptureResult(
                fragments=[],
                used_blank_doc_fallback=True,
                hard_table=bool(hard_table),
                failure_code='blank_doc_export_failed',
                diagnostic_code=diagnostic_code,
            )
        images = _render_pdf_pages(pdf_path, pdf_dpi)
        logger.info('[TABLE_PDF_RENDER] pages=%d', int(len(images)))
        processed_pages = _prepare_processed_pages(images, owner=self)
        if (not processed_pages) or _page_batch_has_invalid_width_variance([img.size[0] for img in processed_pages], variance_threshold):
            return TableCaptureResult(
                fragments=[],
                used_blank_doc_fallback=True,
                hard_table=bool(hard_table),
                failure_code='pdf_page_invalid',
                diagnostic_code=diagnostic_code,
            )

    normalized_pages = _pad_pages_to_common_width(processed_pages)
    fragments = _build_pdf_fragments(
        self,
        normalized_pages,
        output_path,
        float(width_point) if width_point else 400.0,
        source_method=str(source_method),
    )
    if not fragments:
        return TableCaptureResult(
            fragments=[],
            used_blank_doc_fallback=bool(used_blank_doc_fallback),
            hard_table=bool(hard_table),
            failure_code='pdf_page_invalid',
            diagnostic_code=diagnostic_code,
        )

    max_height_mm = 240.0
    try:
        max_height_mm = float(getattr(self, '_get_table_splitting_max_height_cm')()) * 10.0
    except Exception:
        max_height_mm = 240.0
    expanded_fragments = _expand_overlimit_pdf_fragments(
        self,
        fragments,
        width_point=float(width_point) if width_point else 400.0,
        max_height_mm=float(max_height_mm),
    )
    if expanded_fragments is None:
        _cleanup_fragment_files(self, fragments)
        return TableCaptureResult(
            fragments=[],
            used_blank_doc_fallback=bool(used_blank_doc_fallback),
            hard_table=bool(hard_table),
            failure_code='fragment_still_over_limit',
            diagnostic_code=diagnostic_code,
        )
    fragments = list(expanded_fragments)

    if len(fragments) > 1:
        logger.info('[TABLE_PDF_FRAGMENT_EMIT] pages=%s source_method=%s hard_table=%s', int(len(fragments)), str(source_method), bool(hard_table))
    return TableCaptureResult(
        fragments=fragments,
        used_blank_doc_fallback=bool(used_blank_doc_fallback),
        hard_table=bool(hard_table),
        failure_code=None,
        diagnostic_code=diagnostic_code,
    )
