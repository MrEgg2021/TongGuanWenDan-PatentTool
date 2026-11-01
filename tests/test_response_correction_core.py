from __future__ import annotations
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from xml.etree import ElementTree as ET
import fitz
import core.response_correction.package_builder as response_package_builder
from core.official_docs.models import NoticeMeta as OfficialNoticeMeta
from core.official_docs.pdf_meta_fallback import PdfFallbackParseResult
from core.response_correction import CorrectionItem, CorrectionPackageRequest, infer_response_correction_notice_kind, NoticeMeta, ResponsePackageRequest, SlotInput, build_correction_package, build_response_package, parse_notice_source

def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path

def _write_notice_zip(path: Path) -> Path:
    list_xml = '<?xml version="1.0" encoding="UTF-8"?>\n<data-bus>\n  <FAWENXLH>2026031900436760</FAWENXLH>\n  <TONGZHISXJ>\n    <SHUXINGXX>\n      <ANJUANH>10000556463209</ANJUANH>\n      <NEIBUBH>wsd2610169</NEIBUBH>\n      <SHENQINGH>2026101841613</SHENQINGH>\n      <SHENQINGR>四川长青松科技有限公司</SHENQINGR>\n      <FAMINGMC>一种高采集效率的离子流采集结构以及质谱仪</FAMINGMC>\n      <TONGZHISBM>210302</TONGZHISBM>\n      <TONGZHISMC>补正通知书</TONGZHISMC>\n      <FAWENR>20260319</FAWENR>\n      <QIXIAN>15</QIXIAN>\n      <FAMINGLX>0</FAMINGLX>\n    </SHUXINGXX>\n  </TONGZHISXJ>\n</data-bus>'
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('inner.zip', _zip_bytes({'list.xml': list_xml, '210302.pdf': b'%PDF-1.4\n%EOF\n'}))
    return path

def _zip_bytes(entries: dict[str, str | bytes]) -> bytes:
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name, value in entries.items():
            zf.writestr(name, value.encode('utf-8') if isinstance(value, str) else value)
    return buf.getvalue()

def _write_pdf(path: Path, lines: list[str]) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), '\n'.join(lines), fontsize=11)
    doc.save(path)
    doc.close()
    return path

def _pdf_bytes(lines: list[str]) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page()
        page.insert_text((72, 72), '\n'.join(lines), fontsize=11)
        return doc.tobytes()
    finally:
        doc.close()

def _write_notice_zip_without_applicant_with_pdf(path: Path) -> Path:
    list_xml = '<?xml version="1.0" encoding="UTF-8"?>\n<data-bus>\n  <FAWENXLH>2026031700247580</FAWENXLH>\n  <TONGZHISXJ>\n    <SHUXINGXX>\n      <ANJUANH>AJ-001</ANJUANH>\n      <NEIBUBH>NB-001</NEIBUBH>\n      <SHENQINGH>2025119605930</SHENQINGH>\n      <FAMINGMC>基于足底压力检测的多维度协同评估方法及系统</FAMINGMC>\n      <TONGZHISBM>210401</TONGZHISBM>\n      <TONGZHISMC>第一次审查意见通知书</TONGZHISMC>\n      <FAWENR>20260127</FAWENR>\n      <FAMINGLX>0</FAMINGLX>\n    </SHUXINGXX>\n  </TONGZHISXJ>\n</data-bus>'
    pdf = _pdf_bytes(['第一次审查意见通知书', '申请号或专利号：2025119605930', '申请人：西安交通大学', '发明名称：基于足底压力检测的多维度协同评估方法及系统'])
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('inner.zip', _zip_bytes({'list.xml': list_xml, '210401.pdf': pdf}))
    return path

def _manifest_entries(inner_zip: Path) -> list[dict[str, str]]:
    source = inner_zip
    if isinstance(source, (bytes, bytearray)):
        zf_ctx = zipfile.ZipFile(io.BytesIO(bytes(source)))
    else:
        zf_ctx = zipfile.ZipFile(source)
    with zf_ctx as zf:
        list_name = next((name for name in zf.namelist() if name.endswith('/list.xml')))
        root = ET.fromstring(zf.read(list_name))
    entries = []
    for node in root.findall('.//BAONEIWJXX'):
        entry = dict(node.attrib)
        entry.update({child.tag: child.text or '' for child in list(node)})
        entries.append(entry)
    return entries

def _read_single_inner_zip_bytes(outer_zip_path: str | Path) -> tuple[str, bytes]:
    with zipfile.ZipFile(outer_zip_path) as outer:
        inner_names = [name for name in outer.namelist() if name.lower().endswith('.zip')]
        if len(inner_names) != 1:
            raise AssertionError(f'expected exactly one inner zip, got: {inner_names}')
        inner_name = inner_names[0]
        return (inner_name, outer.read(inner_name))

class ResponseCorrectionCoreTests(unittest.TestCase):

    def test_package_builder_uses_full_canonical_abstract_display_name(self) -> None:
        self.assertEqual(response_package_builder._SLOT_DISPLAY_NAMES['100004'], '说明书摘要')

    def test_infer_notice_kind_prefers_notice_name(self) -> None:
        self.assertEqual(infer_response_correction_notice_kind(NoticeMeta(notice_name='第一次审查意见通知书')), 'exam_opinion')
        self.assertEqual(infer_response_correction_notice_kind(NoticeMeta(notice_name='补正通知书')), 'rectification')

    def test_infer_notice_kind_falls_back_to_notice_code(self) -> None:
        self.assertEqual(infer_response_correction_notice_kind(NoticeMeta(notice_name='其他通知书', notice_code='220301')), 'exam_opinion')
        self.assertEqual(infer_response_correction_notice_kind(NoticeMeta(notice_name='其他通知书', notice_code='230302')), 'exam_opinion')
        self.assertEqual(infer_response_correction_notice_kind(NoticeMeta(notice_name='其他通知书', notice_code='210302')), 'rectification')
        self.assertEqual(infer_response_correction_notice_kind(NoticeMeta(notice_name='其他通知书', notice_code='230301')), 'rectification')
        self.assertEqual(infer_response_correction_notice_kind(NoticeMeta(notice_name='其他通知书', notice_code='999999')), 'unknown')

    def test_parse_notice_zip_prefers_list_xml_and_maps_patent_type(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            notice = _write_notice_zip(Path(td) / 'notice.zip')
            parsed = parse_notice_source(str(notice))
            self.assertEqual(parsed.meta_source, 'list_xml')
            self.assertEqual(parsed.meta.application_no, '2026101841613')
            self.assertEqual(parsed.meta.invention_title, '一种高采集效率的离子流采集结构以及质谱仪')
            self.assertEqual(parsed.meta.notice_name, '补正通知书')
            self.assertEqual(parsed.meta.notice_code, '210302')
            self.assertEqual(parsed.meta.issue_date, '20260319')
            self.assertEqual(parsed.meta.doc_serial, '2026031900436760')
            self.assertEqual(parsed.meta.patent_type, 'invention')

    def test_parse_notice_pdf_fallback_marks_low_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pdf = _write_pdf(Path(td) / 'notice.pdf', ['Office Action Notice', 'Application No: 2025119605930', 'Invention: pressure evaluation system', 'Issue Date: 2026-01-27'])
            parsed = parse_notice_source(str(pdf))
            self.assertEqual(parsed.meta_source, 'pdf_fallback')
            self.assertEqual(parsed.meta.application_no, '2025119605930')
            self.assertEqual(parsed.meta.notice_name, 'Office Action Notice')
            self.assertEqual(parsed.meta.issue_date, '20260127')

    def test_parse_notice_pdf_fallback_reuses_official_docs_support_for_acceptance_notice(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pdf = _write_pdf(Path(td) / 'acceptance.pdf', ['Acceptance Notice', 'Application No: 2025119605930', 'Issue Date: 2026-01-27'])
            with patch('core.response_correction.notice_parse.parse_pdf_fallback_bytes', return_value=PdfFallbackParseResult(ok=True, meta=OfficialNoticeMeta(notice_code='200101', notice_name='专利申请受理通知书', app_no='2025119605930', issue_date_raw='2026-01-27', issue_date='2026-01-27', issue_date8='20260127'), matched_type_key='200101|专利申请受理通知书', flat_fields={'SHENQINGH': '2025119605930', 'TONGZHISBM': '200101', 'TONGZHISMC': '专利申请受理通知书', 'FAWENR': '2026-01-27'}, main_pdf_raw_name='acceptance.pdf')), patch('core.response_correction.notice_parse.extract_pdf_entity_fields', return_value=SimpleNamespace(applicant='')):
                parsed = parse_notice_source(str(pdf))
            self.assertEqual(parsed.meta_source, 'pdf_fallback')
            self.assertEqual(parsed.meta.application_no, '2025119605930')
            self.assertEqual(parsed.meta.notice_name, '专利申请受理通知书')
            self.assertEqual(parsed.meta.notice_code, '200101')
            self.assertEqual(parsed.meta.issue_date, '20260127')

    def test_parse_notice_pdf_fallback_extracts_issue_date_from_next_line(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pdf = Path(td) / 'notice.pdf'
            pdf.write_bytes(b'%PDF-1.4\n%EOF\n')
            with patch('core.response_correction.notice_parse._read_pdf_lines', return_value=['第一次审查意见通知书', '申请号或专利号：2025119605930', '发明名称：基于足底压力检测的多维度协同评估方法及系统', '发文日：', '2026年01月27日']), patch('core.response_correction.notice_parse.extract_pdf_entity_fields', return_value=SimpleNamespace(applicant='')):
                parsed = parse_notice_source(str(pdf))
            self.assertEqual(parsed.meta_source, 'pdf_fallback')
            self.assertEqual(parsed.meta.application_no, '2025119605930')
            self.assertEqual(parsed.meta.issue_date, '20260127')

    def test_parse_notice_pdf_fallback_extracts_doc_serial_from_label_alias_and_next_line(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pdf = Path(td) / 'notice.pdf'
            pdf.write_bytes(b'%PDF-1.4\n%EOF\n')
            with patch('core.response_correction.notice_parse._read_pdf_lines', return_value=['第一次审查意见通知书', '申请号或专利号：2025119605930', '发文编号：', '2026012700247580']), patch('core.response_correction.notice_parse.extract_pdf_entity_fields', return_value=SimpleNamespace(applicant='')):
                parsed = parse_notice_source(str(pdf))
            self.assertEqual(parsed.meta_source, 'pdf_fallback')
            self.assertEqual(parsed.meta.application_no, '2025119605930')
            self.assertEqual(parsed.meta.doc_serial, '2026012700247580')

    def test_parse_notice_pdf_fallback_extracts_doc_serial_with_label_side_noise(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pdf = Path(td) / 'notice.pdf'
            pdf.write_bytes(b'%PDF-1.4\n%EOF\n')
            with patch('core.response_correction.notice_parse._read_pdf_lines', return_value=['第二次审查意见通知书', '申请号或专利号：202011435491.4', '发文序号：{2025061702233200']), patch('core.response_correction.notice_parse.extract_pdf_entity_fields', return_value=SimpleNamespace(applicant='')):
                parsed = parse_notice_source(str(pdf))
            self.assertEqual(parsed.meta.doc_serial, '2025061702233200')
            self.assertEqual(parsed.meta.application_no, '2020114354914')

    def test_parse_notice_pdf_fallback_local_real_pdfs_if_present(self) -> None:
        sample_paths = [Path('D:/工作文件夹/盛德/逆变器/2020114354914-第一次审查意见通知书.pdf'), Path('D:/工作文件夹/盛德/逆变器/2020114354914-第二次审查意见通知书.pdf'), Path('D:/工作文件夹/盛德/逆变器/2020114354914-第三次审查意见通知书.pdf')]
        if not all((path.exists() for path in sample_paths)):
            self.skipTest('local real-world response-correction PDFs are not available')
        expected_serials = {sample_paths[0]: '2024113000000520', sample_paths[1]: '2025061702233200', sample_paths[2]: '2025082001550670'}
        expected_dates = {sample_paths[0]: '20241130', sample_paths[1]: '20250617', sample_paths[2]: '20250820'}
        for path in sample_paths:
            with self.subTest(path=str(path)):
                parsed = parse_notice_source(str(path))
                self.assertEqual(parsed.meta_source, 'pdf_fallback')
                self.assertEqual(parsed.meta.issue_date, expected_dates[path])
                self.assertEqual(parsed.meta.doc_serial, expected_serials[path])

    def test_parse_notice_zip_fills_missing_applicant_from_main_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            notice = _write_notice_zip_without_applicant_with_pdf(Path(td) / 'notice.zip')
            with patch('core.response_correction.notice_parse.extract_pdf_entity_fields', return_value=SimpleNamespace(applicant='西安交通大学')) as mocked:
                parsed = parse_notice_source(str(notice))
            self.assertEqual(parsed.meta_source, 'list_xml')
            self.assertEqual(parsed.meta.application_no, '2025119605930')
            self.assertEqual(parsed.meta.notice_code, '210401')
            self.assertEqual(parsed.meta.applicant, '西安交通大学')
            mocked.assert_called_once()

    def test_parse_notice_pdf_fallback_fills_applicant_with_official_docs_extractor(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pdf = _write_pdf(Path(td) / 'notice.pdf', ['第一次审查意见通知书', '申请号或专利号：2025119605930', '申请人：西安交通大学', '发明名称：基于足底压力检测的多维度协同评估方法及系统', '发文日：2026年01月27日'])
            with patch('core.response_correction.notice_parse.extract_pdf_entity_fields', return_value=SimpleNamespace(applicant='西安交通大学')) as mocked:
                parsed = parse_notice_source(str(pdf))
            self.assertEqual(parsed.meta_source, 'pdf_fallback')
            self.assertEqual(parsed.meta.application_no, '2025119605930')
            self.assertEqual(parsed.meta.applicant, '西安交通大学')
            mocked.assert_called_once()

    def test_build_response_package_manifest_omits_section_body_and_registers_slots_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            claims_xml = _write_text(root / 'claims.xml', '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><cn-claims><claim id="c1_cl001" num="1"><claim-text>权    利    要    求    书</claim-text></claim><claim id="c1_cl002" num="2"><claim-text>一种装置。</claim-text></claim></cn-claims></cn-application-body>')
            body_xml = _write_text(root / 'section_1.xml', '<?xml version="1.0" encoding="UTF-8"?><cn-other-file lang="zh" country="CN"><p id="p0001" num="0001" Italic="0">答复内容。</p></cn-other-file>')
            request = ResponsePackageRequest(notice=NoticeMeta(application_no='2022101518506', invention_title='一种二进制执行装置', applicant='上海交通大学', notice_name='第N次审查意见通知书', notice_code='210403', issue_date='20260317', doc_serial='2026031700247580', patent_type='invention'), output_dir=str(root / 'out'), opinion_body=SlotInput(path=str(body_xml), preconverted=True), slots={'100001': SlotInput(path=str(claims_xml), preconverted=True)})
            with patch('core.response_correction.package_builder.generate_case_id', return_value='10000009'):
                result = build_response_package(request)
            outer_zip = Path(result.outer_zip_path)
            self.assertEqual(outer_zip.name, '答复审查意见+一种二进制执行装置+2022101518506+第N次审查意见通知书.zip')
            self.assertEqual(sorted((path.name for path in (root / 'out').iterdir())), [outer_zip.name])
            self.assertEqual(result.inner_zip_path, '')
            self.assertEqual(result.case_root, '')
            inner_name, inner_bytes = _read_single_inner_zip_bytes(outer_zip)
            self.assertEqual(inner_name, '10000009.zip')
            with zipfile.ZipFile(io.BytesIO(inner_bytes)) as zf:
                names = set(zf.namelist())
                manifest = ET.fromstring(zf.read('10000009/list.xml'))
                form = ET.fromstring(zf.read('10000009/100012/100012.xml'))
                body_text = zf.read('10000009/100012/section_1.xml').decode('utf-8')
                body = ET.fromstring(body_text.split('>', 1)[1] if body_text.startswith('<?xml') else body_text)
                claims = ET.fromstring(zf.read('10000009/100001/100001.xml'))
            self.assertIn('10000009/100012/100012.xml', names)
            self.assertIn('10000009/100012/section_1.xml', names)
            self.assertIn('10000009/100001/100001.xml', names)
            self.assertNotIn('10000009/100042/100042.pdf', names)
            self.assertEqual(manifest.findtext('.//DIANZISQAJID'), '10000009')
            entries = _manifest_entries(inner_bytes)
            codes = [entry['BIAOGEDM'] for entry in entries]
            paths = [entry['XIANGDUILJ'] for entry in entries]
            self.assertEqual(codes, ['100012', '100001'])
            self.assertNotIn('100012\\section_1.xml', paths)
            self.assertEqual(entries[0]['GUANLIANYWDM'], 'YW10001201')
            self.assertEqual(entries[1]['COUNTS'], '1')
            self.assertEqual(form.findtext('专利申请或专利/发明创造名称'), '一种二进制执行装置')
            self.assertEqual(form.findtext('专利申请或专利/申请人或专利权人姓名或名称'), '上海交通大学')
            self.assertIsNone(form.find('发明创造名称'))
            self.assertEqual(form.findtext('.//针对通知书陈述/专利局就上述专利申请或专利发出通知的日期/年'), '2026')
            self.assertIsNotNone(form.find('关于补交实验数据的情况/补交了实验数据/附加'))
            self.assertIsNotNone(form.find('专利局处理意见/意见内容'))
            self.assertEqual([node.text for node in form.findall('.//附件清单/分类附件/附件类型')], ['权利要求书'])
            self.assertNotIn('意见陈述书正文', [node.text for node in form.findall('.//附件清单/分类附件/附件名称')])
            self.assertIn('<!DOCTYPE cn-other-file SYSTEM "/dtdandxsl/cn-other-file-20080416.dtd">', body_text)
            self.assertEqual(body.find('.//p').attrib['num'], '1')
            claim_nodes = claims.findall('.//claim')
            self.assertEqual(len(claim_nodes), 1)
            self.assertEqual(claim_nodes[0].attrib['num'], '1')
            self.assertEqual(claim_nodes[0].attrib['id'], 'c1_cl001')

    def test_build_response_package_reports_real_progress_steps(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            claims_xml = _write_text(root / 'claims.xml', '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><cn-claims><claim id="c1_cl001" num="1"><claim-text>权 利 要 求 书</claim-text></claim></cn-claims></cn-application-body>')
            body_xml = _write_text(root / 'section_1.xml', '<?xml version="1.0" encoding="UTF-8"?><cn-other-file lang="zh" country="CN"><p id="p0001" num="0001" Italic="0">答复内容。</p></cn-other-file>')
            request = ResponsePackageRequest(notice=NoticeMeta(application_no='2022101518506', invention_title='一种二进制执行装置', applicant='上海交通大学', notice_name='第N次审查意见通知书', notice_code='210403', issue_date='20260317', doc_serial='2026031700247580', patent_type='invention'), output_dir=str(root / 'out'), opinion_body=SlotInput(path=str(body_xml), preconverted=True), slots={'100001': SlotInput(path=str(claims_xml), preconverted=True)})
            progress_events: list[tuple[int, str, str]] = []
            with patch('core.response_correction.package_builder.generate_case_id', return_value='10000019'):
                result = build_response_package(request, progress_callback=lambda percent, primary, detail: progress_events.append((percent, primary, detail)))
            self.assertTrue(result.outer_zip_path.endswith('.zip'))
            self.assertGreaterEqual(len(progress_events), 6)
            self.assertEqual(progress_events[0][0], 5)
            self.assertEqual(progress_events[-1][0], 100)
            self.assertTrue(any(('准备工作目录' in event[2] for event in progress_events)))
            self.assertTrue(any(('意见陈述书正文' in event[2] for event in progress_events)))
            self.assertTrue(any(('四书槽位' in event[2] for event in progress_events)))
            self.assertTrue(any(('生成 list.xml' in event[2] for event in progress_events)))
            self.assertTrue(any(('打 outer zip' in event[2] for event in progress_events)))

    def test_build_response_package_normalizes_dotted_application_no_everywhere(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            claims_xml = _write_text(root / 'claims.xml', '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><cn-claims><claim id="c1_cl001" num="1"><claim-text>claim</claim-text></claim></cn-claims></cn-application-body>')
            body_xml = _write_text(root / 'section_1.xml', '<?xml version="1.0" encoding="UTF-8"?><cn-other-file lang="zh" country="CN"><p id="p0001" num="0001" Italic="0">body</p></cn-other-file>')
            request = ResponsePackageRequest(notice=NoticeMeta(application_no='202011435491.4', invention_title='Example invention', applicant='Example applicant', notice_name='第一次审查意见通知书', notice_code='210401', issue_date='20241130', doc_serial='2024113000000520', patent_type='invention'), output_dir=str(root / 'out'), opinion_body=SlotInput(path=str(body_xml), preconverted=True), slots={'100001': SlotInput(path=str(claims_xml), preconverted=True)})
            with patch('core.response_correction.package_builder.generate_case_id', return_value='10000009'):
                result = build_response_package(request)
            outer_zip = Path(result.outer_zip_path)
            self.assertIn('2020114354914', outer_zip.name)
            self.assertNotIn('202011435491.4', outer_zip.name)
            inner_name, inner_bytes = _read_single_inner_zip_bytes(outer_zip)
            self.assertEqual(inner_name, '10000009.zip')
            with zipfile.ZipFile(io.BytesIO(inner_bytes)) as zf:
                manifest = ET.fromstring(zf.read('10000009/list.xml'))
                form = ET.fromstring(zf.read('10000009/100012/100012.xml'))
            self.assertEqual(manifest.findtext('.//SHENQINGH'), '2020114354914')
            patent = list(form)[0]
            self.assertEqual(patent[0].text, '2020114354914')

    def test_build_correction_package_allows_empty_correction_items(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            request = CorrectionPackageRequest(notice=NoticeMeta(application_no='2026101841613', invention_title='一种高采集效率的离子流采集结构以及质谱仪', applicant='四川长青松科技有限公司', notice_name='补正通知书', notice_code='210302', issue_date='20260319', doc_serial='2026031900436760', patent_type='invention'), output_dir=str(root / 'out'), correction_items=())
            with patch('core.response_correction.package_builder.generate_case_id', return_value='10000006'):
                result = build_correction_package(request)
            outer_zip = Path(result.outer_zip_path)
            self.assertEqual(outer_zip.name, '答复补正+一种高采集效率的离子流采集结构以及质谱仪+2026101841613+补正通知书.zip')
            self.assertEqual(sorted((path.name for path in (root / 'out').iterdir())), [outer_zip.name])
            self.assertEqual(result.inner_zip_path, '')
            self.assertEqual(result.case_root, '')
            _inner_name, inner_bytes = _read_single_inner_zip_bytes(outer_zip)
            with zipfile.ZipFile(io.BytesIO(inner_bytes)) as zf:
                form = ET.fromstring(zf.read('10000006/100006/100006.xml'))
                manifest = ET.fromstring(zf.read('10000006/list.xml'))
            self.assertEqual(manifest.findtext('.//DIANZISQAJID'), '10000006')
            self.assertEqual(form.findtext('专利申请/发明创造名称'), '一种高采集效率的离子流采集结构以及质谱仪')
            self.assertEqual(form.findtext('专利申请/申请人或专利权人姓名或名称'), '四川长青松科技有限公司')
            self.assertIsNone(form.find('发明创造名称'))
            self.assertEqual(form.findtext('.//根据专利法实施细则第50条的规定针对通知书/日期/年'), '2026')
            self.assertEqual(form.findtext('.//通知书序号'), '补正通知书')
            self.assertEqual(len(form.findall('.//补正内容/补正项')), 0)
            self.assertIsNotNone(form.find('附件清单/备案证明文件/备案证明文件编号'))
            self.assertIsNotNone(form.find('专利局处理意见/意见内容'))
            entries = _manifest_entries(inner_bytes)
            self.assertEqual(entries[0]['BIAOGEDM'], '100006')
            self.assertEqual(entries[0]['GUANLIANYWDM'], 'YW10000601')

    def test_build_correction_package_reports_real_progress_steps(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            claims_xml = _write_text(root / 'claims.xml', '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><cn-claims><claim id="c1_cl001" num="1"><claim-text>权 利 要 求 书</claim-text></claim></cn-claims></cn-application-body>')
            request = CorrectionPackageRequest(notice=NoticeMeta(application_no='2026101841613', invention_title='一种高采集效率的离子流采集结构以及质谱仪', applicant='四川长青松科技有限公司', notice_name='补正通知书', notice_code='210302', issue_date='20260319', doc_serial='2026031900436760', patent_type='invention'), output_dir=str(root / 'out'), correction_items=(CorrectionItem(file_name='权利要求书', location='第1页', before='A', after='B'),), slots={'100001': SlotInput(path=str(claims_xml), preconverted=True)})
            progress_events: list[tuple[int, str, str]] = []
            with patch('core.response_correction.package_builder.generate_case_id', return_value='10000020'):
                result = build_correction_package(request, progress_callback=lambda percent, primary, detail: progress_events.append((percent, primary, detail)))
            self.assertTrue(result.outer_zip_path.endswith('.zip'))
            self.assertGreaterEqual(len(progress_events), 5)
            self.assertEqual(progress_events[0][0], 5)
            self.assertEqual(progress_events[-1][0], 100)
            self.assertTrue(any(('准备工作目录' in event[2] for event in progress_events)))
            self.assertTrue(any(('四书槽位' in event[2] for event in progress_events)))
            self.assertTrue(any(('生成主 XML' in event[2] for event in progress_events)))
            self.assertTrue(any(('打 outer zip' in event[2] for event in progress_events)))

    def test_build_response_package_surfaces_file_and_paragraph_progress_from_word_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            opinion_docx = _write_text(root / 'opinion.docx', 'word placeholder')
            claims_xml = _write_text(root / 'claims.xml', '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><cn-claims><claim id="c1_cl001" num="1"><claim-text>权 利 要 求 书</claim-text></claim></cn-claims></cn-application-body>')
            request = ResponsePackageRequest(notice=NoticeMeta(application_no='2022101518506', invention_title='一种二进制执行装置', applicant='上海交通大学', notice_name='第N次审查意见通知书', notice_code='210403', issue_date='20260317', doc_serial='2026031700247580', patent_type='invention'), output_dir=str(root / 'out'), opinion_body=SlotInput(path=str(opinion_docx), preconverted=False), slots={'100001': SlotInput(path=str(claims_xml), preconverted=True)})
            progress_events: list[tuple[int, str, str]] = []

            def _fake_convert_document_slot(input_path, slot_code, output_dir, **kwargs):
                progress = kwargs.get('progress_callback')
                target_dir = Path(output_dir)
                target_dir.mkdir(parents=True, exist_ok=True)
                if callable(progress):
                    progress('scan_ready', {'message': '文档预扫描完成，开始逐段处理...', 'total_paragraphs': 5})
                    progress('paragraph', {'index': 2, 'total': 5, 'section': 'abstract'})
                    progress('paragraph', {'index': 5, 'total': 5, 'section': 'abstract'})
                    progress('before_generate', {'message': '正在生成 XML'})
                xml_path = target_dir / 'section_1.xml'
                xml_path.write_text('<?xml version="1.0" encoding="UTF-8"?><cn-other-file lang="zh" country="CN"><p id="p0001" num="0001" Italic="0">答复内容。</p></cn-other-file>', encoding='utf-8')
                return SimpleNamespace(xml_path=str(xml_path), pages=1, counts=0)
            with patch('core.response_correction.package_builder.generate_case_id', return_value='10000021'), patch('core.response_correction.package_builder.convert_document_slot', side_effect=_fake_convert_document_slot):
                result = build_response_package(request, progress_callback=lambda percent, primary, detail: progress_events.append((percent, primary, detail)))
            self.assertTrue(result.outer_zip_path.endswith('.zip'))
            self.assertTrue(any(('共 2 个文件' in event[2] for event in progress_events)))
            self.assertTrue(any(('第 1/2 个文件' in event[2] for event in progress_events)))
            self.assertTrue(any(('opinion.docx' in event[2] for event in progress_events)))
            self.assertTrue(any(('第 2/5 段' in event[2] for event in progress_events)))
            self.assertTrue(any(('第 5/5 段' in event[2] for event in progress_events)))

    def test_build_correction_package_surfaces_current_file_name_during_slot_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            claims_docx = _write_text(root / 'claims.docx', 'word placeholder')
            request = CorrectionPackageRequest(notice=NoticeMeta(application_no='2026101841613', invention_title='一种高采集效率的离子流采集结构以及质谱仪', applicant='四川长青松科技有限公司', notice_name='补正通知书', notice_code='210302', issue_date='20260319', doc_serial='2026031900436760', patent_type='invention'), output_dir=str(root / 'out'), correction_items=(CorrectionItem(file_name='权利要求书', location='第1页', before='A', after='B'),), slots={'100001': SlotInput(path=str(claims_docx), preconverted=False)})
            progress_events: list[tuple[int, str, str]] = []

            def _fake_convert_document_slot(input_path, slot_code, output_dir, **kwargs):
                progress = kwargs.get('progress_callback')
                target_dir = Path(output_dir)
                target_dir.mkdir(parents=True, exist_ok=True)
                if callable(progress):
                    progress('scan_ready', {'message': '文档预扫描完成，开始逐段处理...', 'total_paragraphs': 3})
                    progress('paragraph', {'index': 1, 'total': 3, 'section': 'claims'})
                xml_path = target_dir / '100001.xml'
                xml_path.write_text('<?xml version="1.0" encoding="UTF-8"?><cn-application-body><cn-claims><claim id="c1_cl001" num="1"><claim-text>权 利 要 求 书</claim-text></claim></cn-claims></cn-application-body>', encoding='utf-8')
                return SimpleNamespace(xml_path=str(xml_path), pages=1, counts=1)
            with patch('core.response_correction.package_builder.generate_case_id', return_value='10000022'), patch('core.response_correction.package_builder.convert_document_slot', side_effect=_fake_convert_document_slot):
                result = build_correction_package(request, progress_callback=lambda percent, primary, detail: progress_events.append((percent, primary, detail)))
            self.assertTrue(result.outer_zip_path.endswith('.zip'))
            self.assertTrue(any(('共 1 个文件' in event[2] for event in progress_events)))
            self.assertTrue(any(('第 1/1 个文件' in event[2] for event in progress_events)))
            self.assertTrue(any(('claims.docx' in event[2] for event in progress_events)))
            self.assertTrue(any(('第 1/3 段' in event[2] for event in progress_events)))

    def test_build_response_package_reports_file_stage_details_for_preconverted_and_copy_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            claims_xml = _write_text(root / 'claims.xml', '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><cn-claims><claim id="c1_cl001" num="1"><claim-text>测试</claim-text></claim></cn-claims></cn-application-body>')
            body_xml = _write_text(root / 'section_1.xml', '<?xml version="1.0" encoding="UTF-8"?><cn-other-file lang="zh" country="CN"><p id="p0001" num="0001" Italic="0">意见陈述</p></cn-other-file>')
            request = ResponsePackageRequest(notice=NoticeMeta(application_no='2022101518506', invention_title='示例发明', applicant='示例申请人', notice_name='第一次审查意见通知书', notice_code='210403', issue_date='20260317', doc_serial='2026031700247580', patent_type='invention'), output_dir=str(root / 'out'), opinion_body=SlotInput(path=str(body_xml), preconverted=True), slots={'100001': SlotInput(path=str(claims_xml), preconverted=True)})
            progress_events: list[tuple[int, str, str]] = []
            with patch('core.response_correction.package_builder.generate_case_id', return_value='10000026'):
                result = build_response_package(request, progress_callback=lambda percent, primary, detail: progress_events.append((percent, primary, detail)))
            self.assertTrue(result.outer_zip_path.endswith('.zip'))
            self.assertTrue(any(('共 2 个文件' in event[2] for event in progress_events)))
            self.assertTrue(any(('section_1.xml' in event[2] and '分析文件内容' in event[2] for event in progress_events)))
            self.assertTrue(any(('claims.xml' in event[2] and '复制预转换 XML' in event[2] for event in progress_events)))

    def test_build_active_response_package_uses_active_scene_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            claims_xml = _write_text(root / 'claims.xml', '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><cn-claims><claim id="c1_cl001" num="1"><claim-text>一种装置。</claim-text></claim></cn-claims></cn-application-body>')
            body_xml = _write_text(root / 'section_1.xml', '<?xml version="1.0" encoding="UTF-8"?><cn-other-file lang="zh" country="CN"><p id="p0001" num="0001" Italic="0">主动答复内容。</p></cn-other-file>')
            request = ResponsePackageRequest(notice=NoticeMeta(application_no='2025105145819', invention_title='一种低蒸发焓水凝胶的制备方法', applicant='聊城大学', patent_type='invention'), output_dir=str(root / 'out'), opinion_body=SlotInput(path=str(body_xml), preconverted=True), slots={'100001': SlotInput(path=str(claims_xml), preconverted=True)}, submission_scene='active_response')
            with patch('core.response_correction.package_builder.generate_case_id', return_value='10000010'):
                result = build_response_package(request)
            outer_zip = Path(result.outer_zip_path)
            self.assertEqual(outer_zip.name, '主动答复+一种低蒸发焓水凝胶的制备方法+2025105145819.zip')
            _inner_name, inner_bytes = _read_single_inner_zip_bytes(outer_zip)
            with zipfile.ZipFile(io.BytesIO(inner_bytes)) as zf:
                form = ET.fromstring(zf.read('10000010/100012/100012.xml'))
            entries = _manifest_entries(inner_bytes)
            self.assertEqual(form.findtext('陈述事项/针对通知书陈述/附加'), '0')
            self.assertEqual(form.findtext('陈述事项/根据专利法实施细则第57条第1款第2款的规定主动提出修改/附加'), '1')
            self.assertEqual(form.findtext('陈述事项/针对通知书陈述/专利局就上述专利申请或专利发出通知的名称'), '')
            self.assertEqual(form.findtext('陈述事项/针对通知书陈述/发文序号'), '')
            self.assertEqual(entries[0]['GUANLIANYWDM'], 'YW10001203')

    def test_build_active_correction_package_uses_active_scene_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            request = CorrectionPackageRequest(notice=NoticeMeta(application_no='2024108155998', invention_title='一种铁掺杂生物炭催化剂及阴极的制备方法与应用', applicant='太原理工大学', patent_type='invention'), output_dir=str(root / 'out'), correction_items=(CorrectionItem(file_name='权利要求书', location='权利要求1', before='补正前文本', after='补正后文本'),), submission_scene='active_correction')
            with patch('core.response_correction.package_builder.generate_case_id', return_value='10000011'):
                result = build_correction_package(request)
            outer_zip = Path(result.outer_zip_path)
            self.assertEqual(outer_zip.name, '主动补正+一种铁掺杂生物炭催化剂及阴极的制备方法与应用+2024108155998.zip')
            _inner_name, inner_bytes = _read_single_inner_zip_bytes(outer_zip)
            with zipfile.ZipFile(io.BytesIO(inner_bytes)) as zf:
                form = ET.fromstring(zf.read('10000011/100006/100006.xml'))
            entries = _manifest_entries(inner_bytes)
            self.assertEqual(form.findtext('补正原因/根据专利法实施细则第57条的规定/附加'), '1')
            self.assertEqual(form.findtext('补正原因/根据专利法实施细则第50条的规定针对通知书/附加'), '0')
            self.assertEqual(form.findtext('补正原因/根据专利法实施细则第50条的规定针对通知书/通知书序号'), '')
            self.assertEqual(form.findtext('补正原因/根据专利法实施细则第50条的规定针对通知书/发文序号'), '')
            self.assertEqual(entries[0]['GUANLIANYWDM'], 'YW10000602')

    def test_build_response_package_avoids_overwriting_existing_named_zip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out_dir = root / 'out'
            out_dir.mkdir(parents=True, exist_ok=True)
            existing = out_dir / '答复审查意见+一种二进制执行装置+2022101518506+第N次审查意见通知书.zip'
            existing.write_bytes(b'existing')
            claims_xml = _write_text(root / 'claims.xml', '<?xml version="1.0" encoding="UTF-8"?><cn-application-body><cn-claims><claim id="c1_cl001" num="1"><claim-text>一种装置。</claim-text></claim></cn-claims></cn-application-body>')
            body_xml = _write_text(root / 'section_1.xml', '<?xml version="1.0" encoding="UTF-8"?><cn-other-file lang="zh" country="CN"><p id="p0001" num="0001" Italic="0">答复内容。</p></cn-other-file>')
            request = ResponsePackageRequest(notice=NoticeMeta(application_no='2022101518506', invention_title='一种二进制执行装置', applicant='上海交通大学', notice_name='第N次审查意见通知书', notice_code='210403', issue_date='20260317', doc_serial='2026031700247580', patent_type='invention'), output_dir=str(out_dir), opinion_body=SlotInput(path=str(body_xml), preconverted=True), slots={'100001': SlotInput(path=str(claims_xml), preconverted=True)})
            with patch('core.response_correction.package_builder.generate_case_id', return_value='10000025'):
                result = build_response_package(request)
            self.assertEqual(Path(result.outer_zip_path).name, '答复审查意见+一种二进制执行装置+2022101518506+第N次审查意见通知书 (2).zip')
            self.assertEqual(sorted((path.name for path in out_dir.iterdir())), ['答复审查意见+一种二进制执行装置+2022101518506+第N次审查意见通知书 (2).zip', '答复审查意见+一种二进制执行装置+2022101518506+第N次审查意见通知书.zip'])
if __name__ == '__main__':
    unittest.main()
