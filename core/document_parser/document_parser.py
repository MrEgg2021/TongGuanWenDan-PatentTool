from __future__ import annotations

from lxml import etree

from core.document_parser.claims_mixin import ClaimsMixin
from core.document_parser.image_equation_mixin import ImageEquationMixin
from core.document_parser.output_mixin import OutputGenerationMixin
from core.document_parser.paragraph_mixin import ParagraphTraversalMixin
from core.document_parser.sections_mixin import SectionsMixin
from core.document_parser.structure_mixin import StructureNormalizationMixin
from core.document_parser.table_mixin import TableProcessingMixin


class DocumentParser(
    SectionsMixin,
    ParagraphTraversalMixin,
    TableProcessingMixin,
    ImageEquationMixin,
    ClaimsMixin,
    StructureNormalizationMixin,
    OutputGenerationMixin,
):
    def __init__(self, word_engine, img_processor, xml_builder, config, progress_callback=None):
        self.word = word_engine
        self.img_proc = img_processor
        self.xml = xml_builder
        self.config = config
        # 说明书段号生成方式：
        # - word: 按 Word 段落（现有逻辑）
        # - period: 按中文句号“。”生成段号（仅影响说明书 description）
        self.description_paragraph_split_mode = "word"
        # 可选进度回调：签名 progress_callback(stage: str, payload: dict)
        self.progress_callback = progress_callback
        self.processed_tables = set()  # 记录已处理的表格 Range.Start
        self._table_capture_success = {}
        self._table_placeholder_inserted = set()
        self._table_process_failure_context = None
        self.table_screenshot_failures = []
        self.object_fallback_failures = []
        self._drawings_quality_warnings = []
        self._drawings_media_quality_meta_by_file = {}
        self._claims_pending_segments = []
        self._claims_pending_num = None
        self._desc_p_positions = []
        self._claim_ranges = []
        # 图像处理通路统计（EMF / PDF / 普通截图），仅用于日志观测
        self._img_pipeline_stats = {"EMF": 0, "PDF": 0, "BITMAP": 0, "MEDIA": 0, "SAVEAS": 0}

        # 存储各部分的 XML 根节点 (临时)
        # 虽然我们会生成多个 XML 文件，但这里先用 Element 对象暂存内容
        self.sections = {
            "claims": None,  # <cn-claims>
            "description": None,  # <description>
            "drawings": None,  # <cn-drawings>
            "abstract": None,  # <cn-abstract>
        }
        self._current_paragraph_index = None  # 仅用于调试日志
        self._logical_section_override = None  # 逻辑章节覆盖（用于页眉滞后场景）
        # 初始化各个 Root 的容器
        # 注意：这些只是各 XML 文件内部的业务根节点，保存时会包裹在 cn-application-body 中
        self.sections["claims"] = etree.Element("cn-claims")
        self.sections["description"] = etree.Element("description")
        self.sections["drawings"] = etree.Element("cn-drawings")
        self.sections["abstract"] = etree.Element("cn-abstract")

    def _get_list_marker(self, para):
        """安全读取段落的 ListFormat.ListString，失败时返回空串"""
        try:
            lst_fmt = para.Range.ListFormat
            list_string = getattr(lst_fmt, "ListString", "")
            if list_string:
                return str(list_string)
        except Exception:
            return ""
        return ""
