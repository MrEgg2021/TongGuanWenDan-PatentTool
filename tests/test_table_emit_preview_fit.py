from __future__ import annotations

import unittest

from core.document_parser.table_ops.emit_fragment_ops import _emit_fragments


class _PreviewFitEmitter:
    description_paragraph_split_mode = 'word'

    def __init__(self) -> None:
        self.config = {
            'equation_centering': {
                'precise': {
                    'line_width_mm': 165.0,
                    'desc_reserved_mm': 20.0,
                }
            },
            'table_capture': {
                'preview_fit': {
                    'enabled': True,
                    'safe_max_he_mm': 240.0,
                    'max_excess_mm': 3.0,
                }
            },
        }
        self.emitted: list[tuple[float, float, bool]] = []

    def _prev_paragraph_ends_with_period(self, _parent_node) -> bool:
        return True

    def _get_table_splitting_max_height_cm(self) -> float:
        return 24.0

    def _apply_table_centering_if_enabled(
        self,
        filename,
        width_mm,
        height_mm,
        *,
        current_section_key,
        target_width_mm,
    ) -> tuple[float, float]:
        _ = filename, width_mm, height_mm, current_section_key, target_width_mm
        return 145.0, 241.5

    def _emit_final_table_image(self, parent_node, section, fn, w, h, table_obj, need_num):
        _ = parent_node, section, fn, table_obj
        self.emitted.append((float(w), float(h), bool(need_num)))
        return True


class TableEmitPreviewFitTests(unittest.TestCase):
    def test_emit_fragments_scales_slightly_oversized_fragment_before_guard(self) -> None:
        parser = _PreviewFitEmitter()

        result = _emit_fragments(parser, [('frag.jpg', 104.73, 226.92)], {}, 'description', object())

        self.assertTrue(result)
        self.assertEqual(len(parser.emitted), 1)
        width_mm, height_mm, need_num = parser.emitted[0]
        self.assertAlmostEqual(height_mm, 240.0, places=2)
        self.assertAlmostEqual(width_mm, 145.0 * (240.0 / 241.5), places=2)
        self.assertTrue(need_num)


if __name__ == '__main__':
    unittest.main()
