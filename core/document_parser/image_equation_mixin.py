from __future__ import annotations

from core.document_parser.equation_mixin import EquationRenderingMixin
from core.document_parser.image_shape_mixin import ImageShapeMixin
from core.document_parser.paragraph_inline_mixin import ParagraphInlineObjectMixin
from core.logging_utils import swallow_exception


class ImageEquationMixin(
    EquationRenderingMixin,
    ImageShapeMixin,
    ParagraphInlineObjectMixin,
):
    """聚合图片/公式/段落行内对象处理逻辑的薄 mixin。

    具体实现分布在：
    - EquationRenderingMixin（公式判定与 PDF 渲染）
    - ImageShapeMixin（图片与浮动对象处理、截图）
    - ParagraphInlineObjectMixin（段落拆分、公式+编号行处理）
    """

    def _record_image_pipeline(self, source: str) -> None:
        """递增当前 DocumentParser 实例上的图像通路统计计数。

        source 只能是 "EMF" / "PDF" / "BITMAP" 之一；
        若当前实例未初始化 _img_pipeline_stats，则静默跳过。
        """
        stats = getattr(self, "_img_pipeline_stats", None)
        if not isinstance(stats, dict):
            return
        source_key = str(source or "").upper()
        if source_key not in {"EMF", "PDF", "BITMAP", "MEDIA", "SAVEAS"}:
            return
        if source_key not in stats:
            stats[source_key] = 0
        try:
            stats[source_key] = int(stats.get(source_key, 0)) + 1
        except Exception:
            # 统计异常不应影响主流程
            swallow_exception("_record_image_pipeline")
            return
