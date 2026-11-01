from __future__ import annotations

from core.config import load_config
from core.logging_utils import logger
from core.patent_type_resolution import detect_direct_patent_type_heading
from core.word_engine import WordEngine


def probe_description_patent_type_heading(input_file, config_path=None) -> dict[str, str | None]:
    if config_path is None:
        config = load_config()
    else:
        config = load_config(config_path)

    word_engine = WordEngine(config["word_engine"])
    try:
        word_engine.start_app()
        word_engine.open_doc(input_file)
        doc = word_engine.doc

        from core.document_parser.document_parser import DocumentParser

        parser = DocumentParser(word_engine, None, None, config)
        section_plan = parser._build_section_plan_from_headers(doc)
        paragraphs = getattr(doc, "Paragraphs", None)
        if paragraphs is None:
            return {"patent_type": None, "matched_heading": None}

        for para in paragraphs:
            try:
                section_key = parser._get_section_key_for_paragraph(para, section_plan)
            except Exception:
                section_key = None
            if section_key != "description":
                continue

            try:
                raw_text = (para.Range.Text or "").replace("\x0b", "\n")
            except Exception:
                raw_text = ""
            try:
                text = parser._sanitize_text(raw_text).strip()
            except Exception:
                text = str(raw_text or "").strip()
            if not text:
                continue

            patent_type, heading = detect_direct_patent_type_heading(text)
            if patent_type in ("invention", "utility_model"):
                logger.info(
                    "[DESC_PATENT_TYPE_PROBE] file=%s matched_heading=%s patent_type=%s",
                    str(input_file),
                    str(heading or ""),
                    str(patent_type),
                )
                return {"patent_type": patent_type, "matched_heading": heading}
        return {"patent_type": None, "matched_heading": None}
    finally:
        try:
            word_engine.quit_app()
        except Exception:
            pass


__all__ = ["probe_description_patent_type_heading"]
