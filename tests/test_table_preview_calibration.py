from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz

from tools.table_preview_calibration import (
    _download_preview_pdf,
    _run_single_case,
    find_single_page_hit,
    load_replay_manifest_entries,
    main,
    summarize_synthetic_measurements,
)


class TablePreviewCalibrationTests(unittest.TestCase):
    def test_import_does_not_pull_gui_preview_package_or_logging_utils(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        code = (
            "import sys; "
            "import tools.table_preview_calibration; "
            "print('core.logging_utils' in sys.modules); "
            "print('gui.tools_ui_impl.preview_impl.run' in sys.modules)"
        )
        proc = subprocess.run(
            [sys.executable, '-c', code],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual(lines[-2:], ['False', 'False'])

    def test_find_single_page_hit_requires_both_sentinels_on_same_page(self) -> None:
        self.assertEqual(find_single_page_hit(['prefix PRE sentinel suffix POST sentinel', 'other page'], 'PRE sentinel', 'POST sentinel'), 1)
        self.assertIsNone(find_single_page_hit(['PRE sentinel only', 'POST sentinel only'], 'PRE sentinel', 'POST sentinel'))

    def test_summarize_synthetic_measurements_reports_global_safe_height(self) -> None:
        summary = summarize_synthetic_measurements(
            [
                {'width_mm': 145.0, 'height_mm': 239.0, 'fits_single_page': True},
                {'width_mm': 145.0, 'height_mm': 240.0, 'fits_single_page': False},
                {'width_mm': 165.0, 'height_mm': 237.0, 'fits_single_page': True},
                {'width_mm': 165.0, 'height_mm': 238.0, 'fits_single_page': False},
            ]
        )

        self.assertEqual(summary['safe_max_he_mm'], 237.0)
        self.assertEqual(summary['width_modes']['145.00']['safe_max_he_mm'], 239.0)
        self.assertEqual(summary['width_modes']['165.00']['safe_max_he_mm'], 237.0)

    def test_load_replay_manifest_entries_reads_audit_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / 'sms_11.jpg'
            image_path.write_bytes(b'fake-image')
            manifest_path = root / 'replay_manifest.json'
            manifest_path.write_text(
                json.dumps(
                    {
                        'entries': [
                            {
                                'table_id': 'table_184_10377',
                                'fragment_index': 1,
                                'image_path': str(image_path),
                                'width_mm': 165.0,
                                'height_mm': 234.19,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding='utf-8',
            )

            entries = load_replay_manifest_entries(str(manifest_path))

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['table_id'], 'table_184_10377')
        self.assertEqual(entries[0]['fragment_index'], 1)
        self.assertEqual(entries[0]['width_mm'], 165.0)
        self.assertTrue(entries[0]['label'].startswith('table_184_10377'))

    def test_main_replay_manifest_generates_manual_required_report_when_service_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / 'sms_11.jpg'
            image_path.write_bytes(b'fake-image')
            manifest_path = root / 'replay_manifest.json'
            manifest_path.write_text(
                json.dumps(
                    {
                        'entries': [
                            {
                                'table_id': 'table_184_10377',
                                'fragment_index': 1,
                                'image_path': str(image_path),
                                'width_mm': 165.0,
                                'height_mm': 234.19,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding='utf-8',
            )
            output_dir = root / 'calibration'

            with patch('tools.table_preview_calibration._ping_preview_service', return_value=False):
                code = main(
                    [
                        '--mode',
                        'replay',
                        '--replay-manifest',
                        str(manifest_path),
                        '--output-dir',
                        str(output_dir),
                    ]
                )

            report = json.loads((output_dir / 'preview_calibration_report.json').read_text(encoding='utf-8'))

        self.assertEqual(code, 0)
        self.assertFalse(report['service_ready'])
        self.assertEqual(report['replay_results'][0]['status'], 'manual_required')
        self.assertIn('manual_instructions', report)

    def test_download_preview_pdf_retries_until_valid_pdf(self) -> None:
        pdf_doc = fitz.open()
        pdf_doc.new_page()
        valid_pdf = pdf_doc.tobytes()
        pdf_doc.close()

        class FakeResponse:
            def __init__(self, content: bytes, *, headers: dict[str, str] | None = None) -> None:
                self.content = content
                self.headers = headers or {}

            def raise_for_status(self) -> None:
                return None

        class FakeSession:
            def __init__(self) -> None:
                self.proxies = {}
                self.calls = 0

            def get(self, url, timeout=None, headers=None):
                self.calls += 1
                if 'viewer.html' in str(url):
                    return FakeResponse(b'<html>viewer</html>', headers={'Content-Type': 'text/html'})
                if self.calls < 4:
                    return FakeResponse(b'<html>not-ready</html>', headers={'Content-Type': 'text/html'})
                return FakeResponse(valid_pdf, headers={'Content-Type': 'application/pdf'})

        with patch('tools.table_preview_calibration.requests.Session', return_value=FakeSession()), patch(
            'tools.table_preview_calibration.time.sleep', return_value=None
        ):
            content = _download_preview_pdf('http://127.0.0.1:8080/view/token123')

        self.assertTrue(content.startswith(b'%PDF-'))

    def test_run_single_case_downgrades_invalid_preview_pdf_to_manual_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / 'sms_11.jpg'
            image_path.write_bytes(b'fake-image')

            with patch('tools.table_preview_calibration._upload_preview_zip', return_value='http://127.0.0.1:8080/view/token123'), patch(
                'tools.table_preview_calibration._download_preview_pdf',
                side_effect=RuntimeError('preview PDF not ready or invalid after 3 attempts: preview PDF is not ready'),
            ):
                result = _run_single_case(
                    root,
                    label='replay_001',
                    image_path=image_path,
                    width_mm=165.0,
                    height_mm=234.19,
                    base_url='http://127.0.0.1:8080',
                    service_ready=True,
                )

        self.assertEqual(result['status'], 'manual_required')
        self.assertEqual(result['preview_url'], 'http://127.0.0.1:8080/view/token123')
        self.assertIn('preview PDF not ready', result['error'])


if __name__ == '__main__':
    unittest.main()
