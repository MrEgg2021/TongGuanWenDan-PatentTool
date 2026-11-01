from __future__ import annotations

import unittest

from core.official_docs.models import NoticeMeta, ParsedNotice, PdfSource
from gui.main_window.mixins.official_docs_ops.detail_ops import _refresh_official_docs_detail


class _DummyLabel:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, value: str) -> None:
        self.text = str(value)


class _DummyButton:
    def __init__(self) -> None:
        self.enabled = None

    def setEnabled(self, value: bool) -> None:
        self.enabled = bool(value)


class _DetailWindow:
    def __init__(self, parsed: ParsedNotice) -> None:
        self._parsed = parsed
        self._official_docs_selected_leaf_id = "leaf-1"
        self._official_docs_leaves = {
            "leaf-1": {
                "id": "leaf-1",
                "display_name": "示例通知书",
                "checked": True,
                "last_result": None,
            }
        }
        self.official_docs_current_label = _DummyLabel()
        self.official_docs_meta_label = _DummyLabel()
        self.official_docs_output_preview = _DummyLabel()
        self.official_docs_validation_error = _DummyLabel()
        self.official_docs_pdf_sources_text = _DummyLabel()
        self.official_docs_start_button = _DummyButton()

    def _init_official_docs_state(self) -> None:
        return None

    def _parse_official_docs_leaf_if_needed(self, leaf_id: str) -> ParsedNotice | None:
        if leaf_id != "leaf-1":
            return None
        return self._parsed

    def _build_official_docs_options(self, *, use_saved: bool):
        return {"use_saved": use_saved}

    def _build_preview_paths(self, _parsed: ParsedNotice, _options) -> tuple[str, str, str]:
        return ("示例输出.pdf", "D:/summary/示例输出.pdf", "")

    def _get_official_docs_settings_snapshot(self, *, sync_current_type: bool):
        return {"sync_current_type": sync_current_type}

    def _validate_official_docs_settings(self, _settings) -> list[str]:
        return []

    def _iter_checked_leaf_ids(self):
        yield "leaf-1"


class OfficialDocsDetailPdfSourcesV265Tests(unittest.TestCase):
    def test_refresh_detail_shows_pdf_sources_for_pdf_fallback_leaf(self) -> None:
        parsed = ParsedNotice(
            source_zip_path="demo.zip",
            notice_kind="exam_opinion",
            meta=NoticeMeta(app_no="2025113838195", notice_name="第一次审查意见通知书", issue_date="2025-11-06"),
            meta_source="pdf_fallback",
            pdf_entries=[
                PdfSource(raw_name="main.pdf", display_name="main.pdf", kind="main"),
                PdfSource(raw_name="annex.jpg", display_name="annex.jpg", kind="attachment", source_type="image"),
            ],
        )
        window = _DetailWindow(parsed)

        _refresh_official_docs_detail(window)

        self.assertIn("1. 主文 | main.pdf", window.official_docs_pdf_sources_text.text)
        self.assertIn("2. 附件 | annex.jpg | 图片来源", window.official_docs_pdf_sources_text.text)
        self.assertTrue(window.official_docs_start_button.enabled)

    def test_refresh_detail_shows_pdf_sources_for_list_xml_leaf(self) -> None:
        parsed = ParsedNotice(
            source_zip_path="list-based.zip",
            notice_kind="rectification",
            meta=NoticeMeta(app_no="2023102005899", notice_name="补正通知书", issue_date="2024-03-01"),
            meta_source="list_xml",
            pdf_entries=[
                PdfSource(raw_name="210301.pdf", display_name="210301.pdf", kind="main"),
                PdfSource(raw_name="attachment.pdf", display_name="attachment.pdf", kind="extra"),
            ],
        )
        window = _DetailWindow(parsed)

        _refresh_official_docs_detail(window)

        self.assertIn("1. 主文 | 210301.pdf", window.official_docs_pdf_sources_text.text)
        self.assertIn("2. 其他 | attachment.pdf", window.official_docs_pdf_sources_text.text)
        self.assertIn("2023102005899", window.official_docs_meta_label.text)


if __name__ == "__main__":
    unittest.main()
