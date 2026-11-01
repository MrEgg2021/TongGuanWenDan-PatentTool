from __future__ import annotations

import unittest
from pathlib import Path

from official_docs_source_loader import read_official_docs_mixin_source, read_official_docs_page_source


class OfficialDocsPdfParseTabWiringTests(unittest.TestCase):
    def test_pdf_parse_tab_main_toggle_and_children_exist(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn('chk_exam_pdf_parse = QCheckBox("解析PDF文件内容")', text)
        self.assertIn('tabs.addTab(pdf_parse_tab, "PDF解析")', text)
        self.assertIn('"applicant": chk_pdf_applicant', text)
        self.assertIn('"inventor": chk_pdf_inventor', text)
        self.assertIn('"agent": chk_pdf_agent', text)
        self.assertIn('"agency_raw": chk_pdf_agency_raw', text)
        self.assertIn('"department": chk_pdf_department', text)
        self.assertIn('"center": chk_pdf_center', text)
        self.assertIn('"examiner": chk_pdf_examiner', text)
        self.assertIn('"panel": chk_pdf_panel', text)
        self.assertIn('"reject_reason": chk_pdf_reject_reason', text)
        self.assertIn('"prior_art": chk_pdf_prior_art', text)
        self.assertIn('"dossier_no": chk_pdf_dossier_no', text)
        self.assertIn('"authorization_pub_no": chk_pdf_authorization_pub_no', text)
        self.assertIn('"authorization_pub_date": chk_pdf_authorization_pub_date', text)
        self.assertIn('"certificate_no": chk_pdf_certificate_no', text)
        self.assertIn('"qrcode_link": chk_pdf_qrcode_link', text)
        self.assertIn('"qrcode_image": chk_pdf_qrcode_image', text)

    def test_pdf_parse_field_enablement_is_linked_in_mixin(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn("def _set_pdf_parse_field_checks_enabled(self, enabled: bool)", text)
        self.assertIn('wrap = getattr(self, "official_docs_pdf_parse_fields_wrap", None)', text)
        self.assertIn("self._set_pdf_parse_field_checks_enabled(parse_enabled)", text)

    def test_pdf_parse_enable_warning_wiring_exists(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn("show_official_docs_pdf_parse_enable_notice_dialog", text)
        self.assertIn("def _persist_pdf_parse_notice_preference", text)
        self.assertIn("next_parse_enabled and (not prev_parse_enabled)", text)


if __name__ == "__main__":
    unittest.main()
