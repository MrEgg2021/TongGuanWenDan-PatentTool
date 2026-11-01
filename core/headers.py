from __future__ import annotations

import os

from core.config import load_config
from core.logging_utils import logger
from core.word_engine import WordEngine


def probe_required_headers_with_meta(input_file, config_path=None):
    if config_path is None:
        config = load_config()
    else:
        config = load_config(config_path)

    word_engine = WordEngine(config['word_engine'])
    from core.document_parser.document_parser import DocumentParser
    parser = DocumentParser(word_engine, None, None, config)

    doc_meta = {}
    try:
        abs_path = os.path.abspath(input_file)
        doc_meta["source_writable"] = bool(os.access(abs_path, os.W_OK))
    except Exception:
        doc_meta["source_writable"] = None
    try:
        word_engine.start_app()
        word_engine.open_doc(input_file)
        doc = word_engine.doc

        # 文档保护状态（A4）：保护模式下部分 Range 操作可能异常
        try:
            protection_type = getattr(doc, "ProtectionType", None)
            doc_meta["protection_type"] = protection_type
            doc_meta["protected"] = protection_type not in (None, -1)
        except Exception as e:
            doc_meta["protection_type"] = None
            doc_meta["protected"] = None
            doc_meta["protection_check_error"] = str(e)

        section_plan = parser._build_section_plan_from_headers(doc)

        found = {
            'claims': False,
            'description': False,
            'abstract': False,
            'drawings': False,
            'request_meta': False,
        }
        for _start, _end, key in section_plan:
            if key == 'claims':
                found['claims'] = True
            elif key == 'description':
                found['description'] = True
            elif key == 'abstract':
                found['abstract'] = True
            elif key == 'drawings':
                found['drawings'] = True
            elif key == 'request_meta':
                found['request_meta'] = True

        logger.info(f"[HEADER_PROBE] {input_file} -> {found}")
        return found, doc_meta
    finally:
        try:
            word_engine.quit_app()
        except Exception:
            pass
