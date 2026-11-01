from __future__ import annotations

# Direct-script support mutates sys.path before project imports.
# ruff: noqa: E402

import argparse
import json
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

import fitz
import requests
from lxml import etree
from PIL import Image, ImageDraw

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.xml_generator import XMLBuilder


DEFAULT_BASE_URL = 'http://127.0.0.1:8080'
DESCRIPTION_CODE = '100002'
SENTINEL_PREFIX = 'CALIB_PRE'
SENTINEL_SUFFIX = 'CALIB_POST'
# Mirror preview fetch defaults locally instead of importing the GUI preview package.
# Importing that package triggers GUI-side module initialization, which can cascade into
# global logging setup and overwrite the repo-root conversion.log during CLI runs.
PREVIEW_FETCH_RETRY = 3
PREVIEW_FETCH_TIMEOUT_VIEWER = 15
PREVIEW_FETCH_TIMEOUT_PDF = 30
_PDF_MAGIC = b'%PDF-'


def _create_list_xml(
    case_root: Path,
    *,
    generated_files: list[tuple[str, str, int]],
    invention_title: str,
    case_id: str,
    submission_code: str = '',
) -> Path:
    root = etree.Element('data-bus')
    qingqiu = etree.SubElement(root, 'QINGQIUXX')
    etree.SubElement(qingqiu, 'DIANZISQAJID').text = str(case_id)
    etree.SubElement(qingqiu, 'SHENQINGFS').text = '2'
    etree.SubElement(qingqiu, 'YEWULX').text = '0'
    etree.SubElement(qingqiu, 'WENJIANLX').text = '0'
    etree.SubElement(qingqiu, 'TIJIAORDM').text = str(submission_code)
    etree.SubElement(qingqiu, 'FAMINGMC').text = str(invention_title)
    etree.SubElement(qingqiu, 'SHENQINGH')
    etree.SubElement(qingqiu, 'WEINEIBH')
    etree.SubElement(qingqiu, 'GUOJISQH')
    etree.SubElement(qingqiu, 'NEIBUBH').text = ''
    etree.SubElement(qingqiu, 'BAOID')

    wenjianb = etree.SubElement(root, 'WENJIANBYSXX')
    baotou = etree.SubElement(wenjianb, 'BAOTOUXX')
    etree.SubElement(baotou, 'WENJIANBBZ')
    etree.SubElement(baotou, 'WENJIANGS').text = str(len(generated_files))

    for folder, xml_name, pages in generated_files:
        node = etree.SubElement(wenjianb, 'BAONEIWJXX', GUANLIANYWDM='YW110101')
        etree.SubElement(node, 'WENJIANBZ').text = str(xml_name)
        etree.SubElement(node, 'GESHILX').text = '.XML'
        etree.SubElement(node, 'BIAOGEDM').text = str(folder)
        etree.SubElement(node, 'XIANGDUILJ').text = f'{folder}\\{xml_name}'
        etree.SubElement(node, 'DTDVersion').text = '1.0'
        etree.SubElement(node, 'PAGES').text = str(int(pages))
        etree.SubElement(node, 'COUNTS').text = '0'
        etree.SubElement(node, 'SHIFOUBZ').text = '0'
        etree.SubElement(node, 'WENJIANMC').text = str(folder)
        zmyt = etree.SubElement(node, 'ZHENGMINGYT', FILETYPE='')
        zmyt.text = str(folder)

    list_path = case_root / 'list.xml'
    etree.ElementTree(root).write(
        str(list_path),
        encoding='UTF-8',
        xml_declaration=True,
        pretty_print=True,
    )
    return list_path


def find_single_page_hit(page_texts: list[str], before_sentinel: str, after_sentinel: str) -> int | None:
    for page_index, page_text in enumerate(list(page_texts or []), start=1):
        text = str(page_text or '')
        if str(before_sentinel) in text and str(after_sentinel) in text:
            return int(page_index)
    return None


def summarize_synthetic_measurements(measurements: list[dict]) -> dict:
    by_width: dict[str, dict] = {}
    for item in list(measurements or []):
        try:
            width_key = f"{float(item['width_mm']):.2f}"
            height_value = float(item['height_mm'])
            fits_single_page = bool(item['fits_single_page'])
        except Exception:
            continue
        bucket = by_width.setdefault(width_key, {'safe_max_he_mm': None, 'first_overflow_he_mm': None, 'measurements': []})
        bucket['measurements'].append(dict(item))
        if fits_single_page:
            current_safe = bucket.get('safe_max_he_mm')
            if current_safe is None or float(height_value) > float(current_safe):
                bucket['safe_max_he_mm'] = float(height_value)
        else:
            current_fail = bucket.get('first_overflow_he_mm')
            if current_fail is None or float(height_value) < float(current_fail):
                bucket['first_overflow_he_mm'] = float(height_value)

    safe_values = [float(item['safe_max_he_mm']) for item in by_width.values() if item.get('safe_max_he_mm') is not None]
    overall_safe = min(safe_values) if safe_values else None

    overflow_deltas = []
    for item in by_width.values():
        safe_value = item.get('safe_max_he_mm')
        first_fail = item.get('first_overflow_he_mm')
        if safe_value is None or first_fail is None:
            continue
        delta = float(first_fail) - float(safe_value)
        if delta > 0:
            overflow_deltas.append(delta)
    recommended_max_excess = min(overflow_deltas) if overflow_deltas else None

    return {
        'safe_max_he_mm': overall_safe,
        'recommended_max_excess_mm': recommended_max_excess,
        'width_modes': by_width,
    }


def _build_synthetic_image(path: Path, *, width_mm: float, height_mm: float, dpi: int = 300) -> None:
    width_px = max(32, int(round(float(width_mm) * float(dpi) / 25.4)))
    height_px = max(32, int(round(float(height_mm) * float(dpi) / 25.4)))
    image = Image.new('RGB', (width_px, height_px), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((2, 2, width_px - 3, height_px - 3), outline=(0, 0, 0), width=3)
    draw.text((12, 12), f'{width_mm:.2f} x {height_mm:.2f} mm', fill=(0, 0, 0))
    image.save(path, quality=95, subsampling=0, dpi=(dpi, dpi))


def _create_description_case(case_root: Path, *, image_path: Path, width_mm: float, height_mm: float, before_sentinel: str, after_sentinel: str) -> Path:
    desc_dir = case_root / DESCRIPTION_CODE
    desc_dir.mkdir(parents=True, exist_ok=True)
    image_target = desc_dir / image_path.name
    shutil.copyfile(image_path, image_target)

    xml = XMLBuilder({'drawings_img_max_wi_mm': 164.0, 'drawings_img_max_he_mm': 230.0})
    root = xml.init_xml()
    desc = xml.create_section(root, 'description')
    xml.create_paragraph(desc, before_sentinel, num='0001', is_claim=False)
    img_para = xml.create_paragraph(desc, text=None, num='XXXX', is_claim=False)
    xml.create_image_node(img_para, image_target.name, width_mm, height_mm, img_type='desc', inline=False)
    xml.create_paragraph(desc, after_sentinel, num='0002', is_claim=False)
    xml_path = desc_dir / f'{DESCRIPTION_CODE}.xml'
    xml.save(str(xml_path))

    _create_list_xml(
        case_root,
        generated_files=[(DESCRIPTION_CODE, f'{DESCRIPTION_CODE}.xml', 1)],
        invention_title='Table Preview Calibration',
        case_id='99999999',
        submission_code='',
    )
    return xml_path


def _zip_case_root(case_root: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in case_root.rglob('*'):
            if file_path.is_file():
                zf.write(file_path, arcname=str(file_path.relative_to(case_root)).replace('\\', '/'))
    return zip_path


def _ping_preview_service(base_url: str) -> bool:
    try:
        resp = requests.get(base_url.rstrip('/') + '/', timeout=2, proxies={'http': None, 'https': None})
        return resp.status_code < 400
    except Exception:
        return False


def _upload_preview_zip(base_url: str, zip_path: Path) -> str:
    url = base_url.rstrip('/') + '/api/upload-zip/sync'
    with open(zip_path, 'rb') as fh:
        files = {'file': (zip_path.name, fh, 'application/zip')}
        resp = requests.post(url, files=files, timeout=120, proxies={'http': None, 'https': None})
    resp.raise_for_status()
    preview_url = str(resp.text or '').strip()
    if not preview_url:
        raise RuntimeError('preview upload returned an empty URL')
    return preview_url


def _download_preview_pdf(preview_url: str, *, code: str = DESCRIPTION_CODE) -> bytes:
    match = re.match(r'^(https?://[^/]+)/view/([^/?#]+)', preview_url.strip())
    if not match:
        raise RuntimeError('preview URL is invalid')
    origin, token = match.group(1), match.group(2)
    viewer_url = origin.rstrip('/') + f'/pdf/web/viewer.html?file=/view-pdf/{token}/{code}.pdf'
    pdf_url = origin.rstrip('/') + f'/view-pdf/{token}/{code}.pdf'
    session = requests.Session()
    session.proxies = {'http': None, 'https': None}
    user_agent = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    )
    last_error = 'preview PDF is empty'
    last_content = b''
    for attempt in range(1, PREVIEW_FETCH_RETRY + 1):
        try:
            session.get(
                viewer_url,
                timeout=PREVIEW_FETCH_TIMEOUT_VIEWER,
                headers={'Referer': preview_url, 'User-Agent': user_agent},
            )
            resp = session.get(
                pdf_url,
                timeout=PREVIEW_FETCH_TIMEOUT_PDF,
                headers={'Referer': viewer_url, 'User-Agent': user_agent},
            )
            resp.raise_for_status()
            content = resp.content or b''
            last_content = content
            if not content:
                raise RuntimeError('preview PDF is empty')
            head = content[:1024].lstrip()
            if not head.startswith(_PDF_MAGIC):
                content_type = str(resp.headers.get('Content-Type') or '').strip()
                snippet = head[:160].decode('utf-8', errors='replace').strip()
                detail = f'content_type={content_type or "unknown"}'
                if snippet:
                    detail += f' body={snippet}'
                raise RuntimeError(f'preview PDF is not ready ({detail})')
            doc = fitz.open(stream=content, filetype='pdf')
            try:
                if doc.page_count <= 0:
                    raise RuntimeError('preview PDF has no pages')
            finally:
                doc.close()
            return content
        except Exception as exc:
            last_error = str(exc)
            if attempt >= PREVIEW_FETCH_RETRY:
                break
            time.sleep(float(attempt))
    if last_content:
        raise RuntimeError(f'preview PDF not ready or invalid after {PREVIEW_FETCH_RETRY} attempts: {last_error}')
    raise RuntimeError(f'preview PDF unavailable after {PREVIEW_FETCH_RETRY} attempts: {last_error}')


def _extract_page_texts(pdf_bytes: bytes) -> list[str]:
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        return [page.get_text('text') for page in doc]
    finally:
        doc.close()


def _parse_replay_entry(entry: str) -> tuple[str, float, float]:
    parts = [part.strip() for part in str(entry or '').split(',')]
    if len(parts) != 3:
        raise ValueError(f'invalid replay entry: {entry!r}')
    return parts[0], float(parts[1]), float(parts[2])


def _sanitize_label_piece(value: object) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    text = re.sub(r'[^0-9A-Za-z._-]+', '_', text)
    return text.strip('_')


def load_replay_manifest_entries(manifest_path: str) -> list[dict]:
    path = Path(str(manifest_path or '').strip()).resolve()
    if not path.is_file():
        raise FileNotFoundError(f'replay manifest not found: {path}')

    payload = json.loads(path.read_text(encoding='utf-8'))
    entries = payload.get('entries') if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        raise ValueError('replay manifest must contain an entries list')

    output: list[dict] = []
    for idx, item in enumerate(entries, start=1):
        if not isinstance(item, dict):
            raise ValueError(f'invalid replay manifest entry at index {idx}')
        image_path = Path(str(item.get('image_path') or '').strip()).resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f'replay image not found: {image_path}')
        width_mm = float(item.get('width_mm'))
        height_mm = float(item.get('height_mm'))
        table_id = _sanitize_label_piece(item.get('table_id') or f'table_{idx:03d}') or f'table_{idx:03d}'
        fragment_index = int(item.get('fragment_index') or idx)
        label = _sanitize_label_piece(item.get('label') or f'{table_id}_f{fragment_index:03d}') or f'replay_{idx:03d}'
        output.append(
            {
                'label': label,
                'table_id': str(item.get('table_id') or table_id),
                'fragment_index': int(fragment_index),
                'image_path': str(image_path),
                'width_mm': float(width_mm),
                'height_mm': float(height_mm),
            }
        )
    return output


def _run_single_case(base_dir: Path, *, label: str, image_path: Path, width_mm: float, height_mm: float, base_url: str, service_ready: bool) -> dict:
    case_root = base_dir / label
    case_root.mkdir(parents=True, exist_ok=True)
    before_sentinel = f'{SENTINEL_PREFIX}_{label}'
    after_sentinel = f'{SENTINEL_SUFFIX}_{label}'
    _create_description_case(
        case_root,
        image_path=image_path,
        width_mm=float(width_mm),
        height_mm=float(height_mm),
        before_sentinel=before_sentinel,
        after_sentinel=after_sentinel,
    )
    zip_path = _zip_case_root(case_root, case_root.with_suffix('.zip'))

    result = {
        'label': label,
        'zip_path': str(zip_path),
        'image_path': str(image_path),
        'width_mm': float(width_mm),
        'height_mm': float(height_mm),
        'service_ready': bool(service_ready),
        'fits_single_page': None,
        'matched_page': None,
        'preview_url': None,
        'status': 'manual_required' if not service_ready else 'pending',
    }
    if not service_ready:
        return result

    preview_url = None
    try:
        preview_url = _upload_preview_zip(base_url, zip_path)
        pdf_bytes = _download_preview_pdf(preview_url, code=DESCRIPTION_CODE)
        page_texts = _extract_page_texts(pdf_bytes)
        matched_page = find_single_page_hit(page_texts, before_sentinel, after_sentinel)
        result.update(
            {
                'preview_url': preview_url,
                'pdf_path': str(case_root / f'{DESCRIPTION_CODE}.pdf'),
                'fits_single_page': matched_page is not None,
                'matched_page': matched_page,
                'status': 'ok',
            }
        )
        with open(result['pdf_path'], 'wb') as fh:
            fh.write(pdf_bytes)
    except Exception as exc:
        result.update(
            {
                'preview_url': preview_url,
                'status': 'manual_required',
                'error': str(exc),
            }
        )
    return result


def _write_report(output_dir: Path, *, synthetic_results: list[dict], replay_results: list[dict], service_ready: bool, base_url: str) -> tuple[Path, Path]:
    synthetic_summary = summarize_synthetic_measurements(synthetic_results)
    report = {
        'service_ready': bool(service_ready),
        'base_url': str(base_url),
        'safe_max_he_mm': synthetic_summary.get('safe_max_he_mm'),
        'recommended_max_excess_mm': synthetic_summary.get('recommended_max_excess_mm'),
        'max_excess_mm': synthetic_summary.get('recommended_max_excess_mm'),
        'width_modes': synthetic_summary.get('width_modes', {}),
        'synthetic_results': synthetic_results,
        'replay_results': replay_results,
    }
    if not service_ready:
        report['manual_instructions'] = [
            'Start the official preview service locally.',
            'Re-run this script with the same output directory or inspect the generated ZIP files manually.',
            'Do not enable table_capture.preview_fit until safe_max_he_mm and max_excess_mm are confirmed.',
        ]

    json_path = output_dir / 'preview_calibration_report.json'
    md_path = output_dir / 'preview_calibration_report.md'
    with open(json_path, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    lines = [
        '# Table Preview Calibration Report',
        '',
        f'- Service ready: {service_ready}',
        f'- Base URL: `{base_url}`',
        f"- safe_max_he_mm: `{report.get('safe_max_he_mm')}`",
        f"- recommended_max_excess_mm: `{report.get('recommended_max_excess_mm')}`",
        '',
        '## Width Modes',
    ]
    width_modes = report.get('width_modes', {}) or {}
    if width_modes:
        for width_key, payload in sorted(width_modes.items()):
            lines.append(
                f"- {width_key} mm: safe_max_he_mm={payload.get('safe_max_he_mm')} first_overflow_he_mm={payload.get('first_overflow_he_mm')}"
            )
    else:
        lines.append('- No synthetic calibration results were available.')

    lines.extend(['', '## Replay Results'])
    if replay_results:
        for item in replay_results:
            lines.append(
                f"- {item.get('label')}: status={item.get('status')} fits_single_page={item.get('fits_single_page')} matched_page={item.get('matched_page')} zip={item.get('zip_path')}"
            )
            if item.get('error'):
                lines.append(f"  error: {item.get('error')}")
    else:
        lines.append('- No replay fragments were provided.')

    if not service_ready:
        lines.extend(['', '## Manual Instructions'])
        for item in report.get('manual_instructions', []):
            lines.append(f'- {item}')

    with open(md_path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Calibrate official preview single-page table image height.')
    parser.add_argument('--mode', choices=['synthetic', 'replay', 'all'], default='all')
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL)
    parser.add_argument('--output-dir', default=str(Path('temp_processing') / 'table_preview_calibration'))
    parser.add_argument('--widths-mm', default='145,165')
    parser.add_argument('--height-start-mm', type=float, default=232.0)
    parser.add_argument('--height-end-mm', type=float, default=245.0)
    parser.add_argument('--height-step-mm', type=float, default=1.0)
    parser.add_argument('--replay-fragment', action='append', default=[], help='Format: image_path,width_mm,height_mm')
    parser.add_argument('--replay-manifest', default='', help='Path to replay_manifest.json generated by table_conversion_audit')
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    service_ready = _ping_preview_service(str(args.base_url))

    synthetic_results: list[dict] = []
    replay_results: list[dict] = []

    if args.mode in ('synthetic', 'all'):
        widths = [float(item.strip()) for item in str(args.widths_mm).split(',') if item.strip()]
        height_value = float(args.height_start_mm)
        synthetic_dir = output_dir / 'synthetic'
        synthetic_dir.mkdir(parents=True, exist_ok=True)
        while height_value <= float(args.height_end_mm) + 1e-9:
            for width_value in widths:
                label = f'synth_{width_value:.2f}_{height_value:.2f}'.replace('.', '_')
                image_path = synthetic_dir / f'{label}.jpg'
                _build_synthetic_image(image_path, width_mm=float(width_value), height_mm=float(height_value))
                result = _run_single_case(
                    synthetic_dir,
                    label=label,
                    image_path=image_path,
                    width_mm=float(width_value),
                    height_mm=float(height_value),
                    base_url=str(args.base_url),
                    service_ready=service_ready,
                )
                synthetic_results.append(result)
            height_value += float(args.height_step_mm)

    if args.mode in ('replay', 'all'):
        replay_dir = output_dir / 'replay'
        replay_dir.mkdir(parents=True, exist_ok=True)
        replay_entries: list[dict] = []
        for idx, replay_entry in enumerate(list(args.replay_fragment or []), start=1):
            image_path_raw, width_mm, height_mm = _parse_replay_entry(replay_entry)
            replay_entries.append(
                {
                    'label': f'replay_{idx:03d}',
                    'table_id': '',
                    'fragment_index': int(idx),
                    'image_path': str(Path(image_path_raw).resolve()),
                    'width_mm': float(width_mm),
                    'height_mm': float(height_mm),
                }
            )
        if args.replay_manifest:
            replay_entries.extend(load_replay_manifest_entries(str(args.replay_manifest)))

        for idx, replay_item in enumerate(replay_entries, start=1):
            image_path = Path(str(replay_item.get('image_path') or '')).resolve()
            label = str(replay_item.get('label') or f'replay_{idx:03d}')
            result = _run_single_case(
                replay_dir,
                label=label,
                image_path=image_path,
                width_mm=float(replay_item.get('width_mm') or 0.0),
                height_mm=float(replay_item.get('height_mm') or 0.0),
                base_url=str(args.base_url),
                service_ready=service_ready,
            )
            result['table_id'] = str(replay_item.get('table_id') or '')
            result['fragment_index'] = int(replay_item.get('fragment_index') or idx)
            replay_results.append(result)

    json_path, md_path = _write_report(
        output_dir,
        synthetic_results=synthetic_results,
        replay_results=replay_results,
        service_ready=service_ready,
        base_url=str(args.base_url),
    )
    print(json.dumps({'json_report': str(json_path), 'markdown_report': str(md_path), 'service_ready': service_ready}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
