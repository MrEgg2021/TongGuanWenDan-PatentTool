from __future__ import annotations

import os

from core.config import load_config
from core.logging_utils import logger
from core.word_engine import WordComHijackedError, WordEngine
from core.img_processor import ImageProcessor
from core.xml_generator import XMLBuilder


class ConversionCancelled(Exception):
    pass


def classify_conversion_error(exc: BaseException | None) -> str:
    if exc is None:
        return "UNEXPECTED_ERROR"
    if isinstance(exc, ConversionCancelled):
        return "CANCELLED"
    if isinstance(exc, WordComHijackedError):
        return "WORD_COM_HIJACKED"

    try:
        msg = str(exc or "")
    except Exception:
        msg = ""
    msg_lower = msg.lower()

    if ("word 窗口持续可见" in msg) or ("启动了 word/wps 进程" in msg):
        return "WORD_GUARD_ABORT"
    if "说明书附图内嵌图片数据已损坏" in msg:
        return "DRAWINGS_SOURCE_MEDIA_CORRUPT"
    if ("pdf" in msg_lower) and (("table" in msg_lower) or ("表格" in msg)):
        return "TABLE_PDF_EXPORT_FAIL"
    if ("table" in msg_lower) or ("表格" in msg):
        return "TABLE_COM_ERROR"
    if ("com" in msg_lower) and ("word" in msg_lower):
        return "WORD_COM_ERROR"
    return "UNEXPECTED_ERROR"


def run_conversion(
    input_file,
    config_path=None,
    progress_callback=None,
    optimize_equation_centering=None,
    optimize_table_image_centering=None,
    case_id=None,
    patent_type=None,
    request_info=None,
    enabled_sections=None,
    description_paragraph_split_mode=None,
    image_processing_overrides: dict | None = None,
    output_dir_override=None,
    temp_dir_override=None,
    forced_section_key=None,
    output_body_root_tags: dict | None = None,
    image_prefix_overrides: dict | None = None,
):
    def _emit_progress(stage, message):
        if progress_callback is None:
            return
        try:
            progress_callback(stage, {"message": message})
        except ConversionCancelled:
            raise
        except Exception:
            pass

    if config_path is None:
        _emit_progress("init_load_config", "正在后台加载默认配置文件 config.yaml...")
        config = load_config()
    else:
        _emit_progress("init_load_config", f"正在后台加载配置文件 {os.path.basename(config_path)}...")
        config = load_config(config_path)

    if output_dir_override is not None:
        config.setdefault("paths", {})["output_dir"] = str(output_dir_override)
    if temp_dir_override is not None:
        config.setdefault("paths", {})["temp_dir"] = str(temp_dir_override)

    # 应用公式转图缩放等高级设置覆盖（来源：GUI/持久化普通偏好）
    if image_processing_overrides:
        ratio = image_processing_overrides.get("equation_display_scale_ratio")
        if ratio is not None:
            r = float(ratio)
            if r <= 0:
                raise ValueError("Equation display scale ratio must be positive.")
            config["equation_display_scale_ratio"] = max(0.4, min(1.0, r))

    eq_cfg = config.get('equation_centering') or {}
    if optimize_equation_centering is not None:
        eq_cfg['enabled'] = bool(optimize_equation_centering)
    elif 'enabled' not in eq_cfg:
        eq_cfg['enabled'] = False
    config['equation_centering'] = eq_cfg

    table_cfg = config.get('table_image_centering') or {}
    if optimize_table_image_centering is not None:
        table_cfg['enabled'] = bool(optimize_table_image_centering)
    elif 'enabled' not in table_cfg:
        table_cfg['enabled'] = True
    config['table_image_centering'] = table_cfg

    _emit_progress("init_modules", "正在准备图片和公式转换...")

    word_engine = WordEngine(config['word_engine'])
    img_processor = ImageProcessor(config['image_processing'])
    xml_builder = XMLBuilder(config['xml_rules'])

    from core.document_parser.document_parser import DocumentParser

    parser = DocumentParser(
        word_engine,
        img_processor,
        xml_builder,
        config,
        progress_callback=progress_callback,
    )
    if enabled_sections is not None:
        parser.enabled_sections = enabled_sections
    if forced_section_key is not None:
        parser.forced_section_key = str(forced_section_key)
    if output_body_root_tags is not None:
        parser.output_body_root_tags = dict(output_body_root_tags)
    if image_prefix_overrides is not None:
        parser.image_prefix_overrides = dict(image_prefix_overrides)
    if description_paragraph_split_mode is not None:
        parser.description_paragraph_split_mode = str(description_paragraph_split_mode)
    word_version = None
    try:
        _emit_progress("init_start_word", "正在后台启动 Word 应用并准备文档环境...")
        word_engine.start_app()
        try:
            word_version = getattr(word_engine, "version", None)
        except Exception:
            word_version = None

        logger.info("[CONVERSION_STAGE] stage=parse_document status=start file=%s word_version=%s", str(input_file), word_version)
        result = parser.run(
            input_file,
            case_id=case_id,
            patent_type=patent_type,
            request_info=request_info,
        )
        logger.info("[CONVERSION_STAGE] stage=parse_document status=done file=%s", str(input_file))
        logger.info("✅ 所有任务已完成")

        # 统一在日志中输出表格截图失败的摘要信息，便于非 GUI / 命令行场景感知风险
        try:
            if isinstance(result, dict):
                table_failures = result.get("table_screenshot_failures") or []
                if table_failures:
                    total_failures = len(table_failures)
                    logger.warning(
                        "[TABLE_SCREENSHOT_FAILURES] total=%d",
                        total_failures,
                    )
                    sample_limit = 20
                    for idx, item in enumerate(table_failures[:sample_limit], start=1):
                        section = item.get("section")
                        desc_para_num = item.get("desc_para_num")
                        claim_num = item.get("claim_num")
                        para_index = item.get("paragraph_index")
                        rs = item.get("range_start")
                        error_code = item.get("error_code")
                        stage = item.get("stage")
                        resolution_code = item.get("resolution_code")
                        if section == "description" and desc_para_num:
                            human = f"说明书第 {desc_para_num} 段附近的表格"
                        elif section == "claims" and claim_num:
                            human = f"权利要求 {claim_num} 中的表格"
                        else:
                            human = f"section={section} paragraph_index={para_index}"
                        logger.warning(
                            "[TABLE_SCREENSHOT_FAILURE] #%d %s (range_start=%r code=%s stage=%s resolution=%s)",
                            idx,
                            human,
                            rs,
                            error_code,
                            stage,
                            resolution_code,
                        )
                    if total_failures > sample_limit:
                        logger.warning(
                            "[TABLE_SCREENSHOT_FAILURES_MORE] %d additional entries not listed",
                            total_failures - sample_limit,
                        )
        except Exception:
            pass

        try:
            if isinstance(result, dict):
                object_fallbacks = result.get("object_fallback_failures") or []
                if object_fallbacks:
                    logger.warning("[OBJECT_FALLBACKS] total=%d", len(object_fallbacks))
                    for idx, item in enumerate(object_fallbacks[:20], start=1):
                        if not isinstance(item, dict):
                            continue
                        logger.warning(
                            "[OBJECT_FALLBACK] #%d section=%s kind=%s classifier=%s resolution=%s range_start=%r source=%s",
                            idx,
                            item.get("section"),
                            item.get("object_kind"),
                            item.get("classifier"),
                            item.get("resolution_code"),
                            item.get("range_start"),
                            item.get("source_hint"),
                        )
        except Exception:
            pass

        # 将检测到的 Word 版本透传给调用方（例如 GUI），不影响核心转换逻辑
        if isinstance(result, dict) and "word_version" not in result:
            result["word_version"] = word_version
        if isinstance(result, dict):
            result.setdefault("source_path", str(input_file))
            result.setdefault("patent_type", patent_type)
            if request_info is not None:
                result.setdefault("request_info", request_info)
            if enabled_sections is not None:
                result.setdefault("enabled_sections", enabled_sections)
            result.setdefault(
                "output_paths",
                {
                    "inner_zip_path": str(result.get("inner_zip_path") or ""),
                    "outer_zip_path": str(result.get("outer_zip_path") or ""),
                    "final_zip_path": str(result.get("final_zip_path") or ""),
                },
            )
            if "table_failures_detail" not in result:
                try:
                    result["table_failures_detail"] = list(result.get("table_screenshot_failures") or [])
                except Exception:
                    result["table_failures_detail"] = []

        return result
    except ConversionCancelled:
        raise
    except Exception as e:
        error_code = classify_conversion_error(e)
        try:
            setattr(e, "conversion_error_code", error_code)
        except Exception:
            pass
        logger.error(
            "[CONVERSION_ERROR] stage=parse_document code=%s message=%s",
            error_code,
            str(e),
            exc_info=True,
        )
        raise
    finally:
        word_engine.quit_app()
        logger.info("🛑 程序退出")
