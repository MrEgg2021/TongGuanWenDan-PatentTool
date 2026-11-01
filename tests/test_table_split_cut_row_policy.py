from __future__ import annotations

import unittest

from core.document_parser.table_ops.process_steps import split_flow as split_flow_module


class TableSplitCutRowPolicyTests(unittest.TestCase):
    def test_choose_cut_row_prefers_coordinates_when_available(self) -> None:
        cut_row, method = split_flow_module._choose_cut_row(
            row_top_map={1: 0.0, 2: 120.0, 3: 260.0, 4: 380.0},
            row_heights=[70.0, 70.0, 70.0, 70.0],
            target_slice_pt=180.0,
        )

        self.assertEqual((cut_row, method), (3, 'coords'))

    def test_choose_cut_row_falls_back_to_row_heights_when_coordinates_missing(self) -> None:
        cut_row, method = split_flow_module._choose_cut_row(
            row_top_map={},
            row_heights=[70.0, 70.0, 70.0, 70.0],
            target_slice_pt=180.0,
        )

        self.assertEqual((cut_row, method), (3, 'row_height'))

    def test_iter_candidate_rows_moves_to_previous_safe_row(self) -> None:
        class _Scanner:
            def find_safe_cut_row(self, requested_row, working_table=None):
                _ = working_table
                mapping = {31: 31, 30: 28, 27: 26}
                return mapping.get(int(requested_row), int(requested_row))

        rows = list(split_flow_module._iter_candidate_rows(_Scanner(), object(), 31))

        self.assertEqual(rows, [(31, 31), (30, 28), (27, 26), (25, 25), (24, 24), (23, 23), (22, 22), (21, 21), (20, 20), (19, 19), (18, 18), (17, 17), (16, 16), (15, 15), (14, 14), (13, 13), (12, 12), (11, 11), (10, 10), (9, 9), (8, 8), (7, 7), (6, 6), (5, 5), (4, 4), (3, 3), (2, 2)])

    def test_pick_split_candidate_retries_when_first_probe_is_over_limit(self) -> None:
        class _Owner:
            def __init__(self) -> None:
                self.removed: list[str] = []

            def _remove_temp_image_if_exists(self, filename):
                self.removed.append(str(filename))

        class _Scanner:
            def find_safe_cut_row(self, requested_row, working_table=None):
                _ = working_table
                return int(requested_row)

        owner = _Owner()
        probe_results = {
            31: {'ok': True, 'file': 'frag31.jpg', 'width_mm': 104.73, 'height_mm': 240.8, 'safe_row': 31},
            30: {'ok': True, 'file': 'frag30.jpg', 'width_mm': 104.73, 'height_mm': 239.7, 'safe_row': 30},
        }

        def _probe(_owner, _table, safe_row, **kwargs):
            _ = _owner, _table, kwargs
            return dict(probe_results[int(safe_row)])

        original_probe = split_flow_module._probe_split_candidate
        try:
            split_flow_module._probe_split_candidate = _probe
            candidate, failure = split_flow_module._pick_split_candidate(
                owner,
                _Scanner(),
                object(),
                31,
                parent_node={},
                current_section_key='description',
                width_point=296.85,
                max_height_mm=240.0,
            )
        finally:
            split_flow_module._probe_split_candidate = original_probe

        self.assertIsNone(failure)
        self.assertEqual(candidate['requested_row'], 30)
        self.assertEqual(candidate['safe_row'], 30)
        self.assertEqual(owner.removed, ['frag31.jpg'])

    def test_pick_split_candidate_retries_when_first_probe_boundary_is_ambiguous(self) -> None:
        class _Owner:
            def __init__(self) -> None:
                self.removed: list[str] = []

            def _remove_temp_image_if_exists(self, filename):
                self.removed.append(str(filename))

        class _Scanner:
            def find_safe_cut_row(self, requested_row, working_table=None):
                _ = working_table
                return int(requested_row)

        owner = _Owner()
        probe_results = {
            31: {
                'ok': True,
                'file': 'frag31.jpg',
                'width_mm': 104.73,
                'height_mm': 120.0,
                'safe_row': 31,
                'ambiguous_access': True,
                'boundary_merge_origins': [{'col': 2, 'start_row': 1, 'end_row': 40}],
            },
            30: {
                'ok': True,
                'file': 'frag30.jpg',
                'width_mm': 104.73,
                'height_mm': 119.0,
                'safe_row': 30,
                'ambiguous_access': False,
                'boundary_merge_origins': [],
            },
        }

        def _probe(_owner, _table, safe_row, **kwargs):
            _ = _owner, _table, kwargs
            return dict(probe_results[int(safe_row)])

        original_probe = split_flow_module._probe_split_candidate
        try:
            split_flow_module._probe_split_candidate = _probe
            candidate, failure = split_flow_module._pick_split_candidate(
                owner,
                _Scanner(),
                object(),
                31,
                parent_node={},
                current_section_key='description',
                width_point=296.85,
                max_height_mm=240.0,
            )
        finally:
            split_flow_module._probe_split_candidate = original_probe

        self.assertIsNone(failure)
        self.assertEqual(candidate['requested_row'], 30)
        self.assertEqual(candidate['safe_row'], 30)
        self.assertEqual(owner.removed, ['frag31.jpg'])

    def test_pick_split_candidate_retries_when_first_probe_capture_fails_recoverably(self) -> None:
        class _Owner:
            def _remove_temp_image_if_exists(self, filename):
                _ = filename
                return None

        class _Scanner:
            def find_safe_cut_row(self, requested_row, working_table=None):
                _ = working_table
                return int(requested_row)

        owner = _Owner()
        probe_results = {
            31: {'ok': False, 'error_code': 'selection_export_failed', 'stage': 'probe.capture_fragment'},
            30: {'ok': True, 'file': 'frag30.jpg', 'width_mm': 104.73, 'height_mm': 239.7, 'safe_row': 30},
        }

        def _probe(_owner, _table, safe_row, **kwargs):
            _ = _owner, _table, kwargs
            return dict(probe_results[int(safe_row)])

        original_probe = split_flow_module._probe_split_candidate
        try:
            split_flow_module._probe_split_candidate = _probe
            candidate, failure = split_flow_module._pick_split_candidate(
                owner,
                _Scanner(),
                object(),
                31,
                parent_node={},
                current_section_key='description',
                width_point=296.85,
                max_height_mm=240.0,
            )
        finally:
            split_flow_module._probe_split_candidate = original_probe

        self.assertIsNone(failure)
        self.assertEqual(candidate['requested_row'], 30)
        self.assertEqual(candidate['safe_row'], 30)

    def test_apply_split_to_current_table_uses_closed_border_policy(self) -> None:
        calls: list[tuple[str, str]] = []

        class _Scanner:
            def find_safe_cut_row(self, requested_row, working_table=None):
                _ = working_table
                return int(requested_row)

        class _Splitter:
            def split_row_at(self, table, row_idx):
                _ = table, row_idx
                return object(), object()

            def apply_cut_border_policy(self, upper, lower, *, strategy, stage):
                _ = upper, lower
                calls.append((str(strategy), str(stage)))

        upper, lower, applied = split_flow_module._apply_split_to_current_table(
            _Scanner(),
            _Splitter(),
            object(),
            30,
            current_section_key='description',
        )

        self.assertIsNotNone(upper)
        self.assertIsNotNone(lower)
        self.assertEqual(applied, 30)
        self.assertEqual(calls, [('closed', 'apply')])

    def test_probe_split_candidate_uses_closed_border_policy(self) -> None:
        calls: list[tuple[str, str]] = []

        class _ScratchDoc:
            class _Content:
                @staticmethod
                def Delete():
                    return None

            Content = _Content()
            Tables = type('_Tables', (), {'Count': 1})()

            def Close(self, SaveChanges=0):
                _ = SaveChanges
                return None

        class _Documents:
            @staticmethod
            def Add(Visible=False):
                _ = Visible
                return _ScratchDoc()

        class _App:
            Documents = _Documents()

        class _Word:
            app = _App()

        class _Owner:
            word = _Word()
            img_proc = object()

            @staticmethod
            def _capture_table_in_canvas(table, **kwargs):
                _ = table, kwargs
                return 'probe.jpg', 100.0, 120.0

        class _ProbeScanner:
            def __init__(self, table):
                _ = table

            def find_safe_cut_row(self, requested_row, working_table=None):
                _ = working_table
                return int(requested_row)

        class _ProbeSplitter:
            def __init__(self, word_engine):
                _ = word_engine

            def split_row_at(self, table, row_idx):
                _ = table, row_idx
                return object(), object()

            def apply_cut_border_policy(self, upper, lower, *, strategy, stage):
                _ = upper, lower
                calls.append((str(strategy), str(stage)))

        original_scratch = split_flow_module._create_scratch_probe_context
        original_disable = split_flow_module._disable_heading_rows
        original_scanner = split_flow_module.TableTopologyScanner
        original_splitter = split_flow_module.CanvasSplitter
        try:
            split_flow_module._create_scratch_probe_context = lambda app, source_table: {
                'ok': True,
                'table': object(),
                'cleanup': lambda: None,
                'probe_source': 'scratch',
                'copy_method': 'copy_paste',
                'copy_success': True,
            }
            split_flow_module._disable_heading_rows = lambda table: None
            split_flow_module.TableTopologyScanner = _ProbeScanner
            split_flow_module.CanvasSplitter = _ProbeSplitter
            result = split_flow_module._probe_split_candidate(
                _Owner(),
                object(),
                30,
                parent_node={},
                current_section_key='description',
                width_point=296.85,
            )
        finally:
            split_flow_module._create_scratch_probe_context = original_scratch
            split_flow_module._disable_heading_rows = original_disable
            split_flow_module.TableTopologyScanner = original_scanner
            split_flow_module.CanvasSplitter = original_splitter

        self.assertTrue(result['ok'])
        self.assertEqual(calls, [('closed', 'probe')])

    def test_probe_split_candidate_falls_back_to_same_canvas_when_scratch_copy_fails(self) -> None:
        class _App:
            pass

        class _Word:
            app = _App()

        class _Owner:
            word = _Word()
            img_proc = object()

            @staticmethod
            def _capture_table_in_canvas(table, **kwargs):
                _ = table, kwargs
                return 'probe.jpg', 100.0, 120.0

        class _ProbeScanner:
            def __init__(self, table):
                _ = table

            def find_safe_cut_row(self, requested_row, working_table=None):
                _ = working_table
                return int(requested_row)

        class _ProbeSplitter:
            def __init__(self, word_engine):
                _ = word_engine

            def split_row_at(self, table, row_idx):
                _ = table, row_idx
                return object(), object()

            def apply_cut_border_policy(self, upper, lower, *, strategy, stage):
                _ = upper, lower, strategy, stage
                return None

        def _scratch(_app, _source_table):
            return {
                'ok': False,
                'error_code': 'split_stalled',
                'stage': 'probe.copy_table',
                'error_message': 'failed to copy current table into probe canvas',
                'probe_source': 'scratch',
                'copy_success': False,
            }

        def _same_canvas(_source_table):
            return {
                'ok': True,
                'table': object(),
                'cleanup': lambda: None,
                'probe_source': 'same_canvas',
                'copy_method': 'formatted_text',
                'copy_success': True,
            }

        original_scratch = split_flow_module._create_scratch_probe_context
        original_same_canvas = split_flow_module._create_same_canvas_probe_context
        original_disable = split_flow_module._disable_heading_rows
        original_scanner = split_flow_module.TableTopologyScanner
        original_splitter = split_flow_module.CanvasSplitter
        try:
            split_flow_module._create_scratch_probe_context = _scratch
            split_flow_module._create_same_canvas_probe_context = _same_canvas
            split_flow_module._disable_heading_rows = lambda table: None
            split_flow_module.TableTopologyScanner = _ProbeScanner
            split_flow_module.CanvasSplitter = _ProbeSplitter
            result = split_flow_module._probe_split_candidate(
                _Owner(),
                object(),
                30,
                parent_node={},
                current_section_key='description',
                width_point=296.85,
                prefer_same_canvas=False,
            )
        finally:
            split_flow_module._create_scratch_probe_context = original_scratch
            split_flow_module._create_same_canvas_probe_context = original_same_canvas
            split_flow_module._disable_heading_rows = original_disable
            split_flow_module.TableTopologyScanner = original_scanner
            split_flow_module.CanvasSplitter = original_splitter

        self.assertTrue(result['ok'])
        self.assertEqual(result['probe_source'], 'same_canvas')
        self.assertEqual(result['copy_method'], 'formatted_text')
        attempts = result.get('copy_attempts') or []
        self.assertEqual([item.get('probe_source') for item in attempts], ['scratch'])

    def test_probe_split_candidate_retries_with_forced_cell_split_after_over_limit_capture_failure(self) -> None:
        forced_rows: list[int] = []

        class _App:
            pass

        class _Word:
            app = _App()

        class _Owner:
            word = _Word()
            img_proc = object()

            def __init__(self) -> None:
                self._failure_ctx = None

            def _clear_table_process_failure_context(self):
                self._failure_ctx = None

            def _consume_table_process_failure_context(self):
                ctx = self._failure_ctx
                self._failure_ctx = None
                return ctx

            def _peek_table_process_failure_context(self):
                return self._failure_ctx

            def _capture_table_in_canvas(self, table, **kwargs):
                _ = table, kwargs
                if forced_rows:
                    return 'probe.jpg', 100.0, 120.0
                self._failure_ctx = {
                    'error_code': 'fragment_still_over_limit',
                    'stage': 'probe.capture_fragment',
                    'error_message': 'pdf-first probe capture did not yield a single legal fragment',
                }
                return None, 0.0, 0.0

        class _ProbeScanner:
            def __init__(self, table):
                _ = table

            def find_safe_cut_row(self, requested_row, working_table=None):
                _ = working_table
                return int(requested_row)

        class _ProbeSplitter:
            def __init__(self, word_engine):
                _ = word_engine

            def force_split_cells_at_row(self, table, row_idx):
                _ = table
                forced_rows.append(int(row_idx))
                return True

            def split_row_at(self, table, row_idx):
                _ = table, row_idx
                return object(), object()

            def apply_cut_border_policy(self, upper, lower, *, strategy, stage):
                _ = upper, lower, strategy, stage
                return None

        original_scratch = split_flow_module._create_scratch_probe_context
        original_disable = split_flow_module._disable_heading_rows
        original_scanner = split_flow_module.TableTopologyScanner
        original_splitter = split_flow_module.CanvasSplitter
        try:
            split_flow_module._create_scratch_probe_context = lambda app, source_table: {
                'ok': True,
                'table': object(),
                'cleanup': lambda: None,
                'probe_source': 'scratch',
                'copy_method': 'copy_paste',
                'copy_success': True,
            }
            split_flow_module._disable_heading_rows = lambda table: None
            split_flow_module.TableTopologyScanner = _ProbeScanner
            split_flow_module.CanvasSplitter = _ProbeSplitter
            result = split_flow_module._probe_split_candidate(
                _Owner(),
                object(),
                2,
                parent_node={},
                current_section_key='description',
                width_point=296.85,
                prefer_same_canvas=False,
            )
        finally:
            split_flow_module._create_scratch_probe_context = original_scratch
            split_flow_module._disable_heading_rows = original_disable
            split_flow_module.TableTopologyScanner = original_scanner
            split_flow_module.CanvasSplitter = original_splitter

        self.assertTrue(result['ok'])
        self.assertEqual(forced_rows, [2])
        self.assertTrue(result.get('forced_cell_split'))

    def test_probe_split_candidate_accepts_legal_multi_fragment_payload(self) -> None:
        class _App:
            pass

        class _Word:
            app = _App()

        class _Owner:
            word = _Word()
            img_proc = object()

            @staticmethod
            def _capture_table_in_canvas_payload(table, **kwargs):
                _ = table, kwargs
                return {
                    'ok': True,
                    'fragments': [('probe_p1.jpg', 100.0, 120.0), ('probe_p2.jpg', 100.0, 118.0)],
                    'fragment_count': 2,
                    'hard_table': True,
                }

        class _ProbeScanner:
            def __init__(self, table):
                _ = table

            def find_safe_cut_row(self, requested_row, working_table=None):
                _ = working_table
                return int(requested_row)

            def describe_boundary_merge_origins(self, row_idx, table=None):
                _ = row_idx, table
                return []

        class _ProbeSplitter:
            def __init__(self, word_engine):
                _ = word_engine

            def split_row_at(self, table, row_idx):
                _ = table, row_idx
                return object(), object()

            def apply_cut_border_policy(self, upper, lower, *, strategy, stage):
                _ = upper, lower, strategy, stage
                return None

        original_scratch = split_flow_module._create_scratch_probe_context
        original_disable = split_flow_module._disable_heading_rows
        original_scanner = split_flow_module.TableTopologyScanner
        original_splitter = split_flow_module.CanvasSplitter
        try:
            split_flow_module._create_scratch_probe_context = lambda app, source_table: {
                'ok': True,
                'table': object(),
                'cleanup': lambda: None,
                'probe_source': 'scratch',
                'copy_method': 'copy_paste',
                'copy_success': True,
            }
            split_flow_module._disable_heading_rows = lambda table: None
            split_flow_module.TableTopologyScanner = _ProbeScanner
            split_flow_module.CanvasSplitter = _ProbeSplitter
            result = split_flow_module._probe_split_candidate(
                _Owner(),
                object(),
                2,
                parent_node={},
                current_section_key='description',
                width_point=296.85,
                prefer_same_canvas=False,
            )
        finally:
            split_flow_module._create_scratch_probe_context = original_scratch
            split_flow_module._disable_heading_rows = original_disable
            split_flow_module.TableTopologyScanner = original_scanner
            split_flow_module.CanvasSplitter = original_splitter

        self.assertTrue(result['ok'])
        self.assertEqual(result['fragment_count'], 2)
        self.assertEqual(
            result['fragments'],
            [('probe_p1.jpg', 100.0, 120.0), ('probe_p2.jpg', 100.0, 118.0)],
        )
        self.assertTrue(result.get('top_fragment_inherently_multi_page'))

    def test_probe_split_candidate_records_boundary_vmerge_diagnostics_when_force_split_needed(self) -> None:
        forced_rows: list[int] = []

        class _App:
            pass

        class _Word:
            app = _App()

        class _Owner:
            word = _Word()
            img_proc = object()

            @staticmethod
            def _capture_table_in_canvas_payload(table, **kwargs):
                _ = table, kwargs
                return {
                    'ok': True,
                    'fragments': [('probe.jpg', 100.0, 120.0)],
                    'fragment_count': 1,
                }

        class _ProbeScanner:
            def __init__(self, table):
                _ = table

            def find_safe_cut_row(self, requested_row, working_table=None):
                _ = requested_row, working_table
                return -1

            def describe_boundary_merge_origins(self, row_idx, table=None):
                _ = table
                return [
                    {
                        'col': 1,
                        'start_row': 1,
                        'end_row': 40,
                        'row_span': 40,
                        'origin_range_start': 100,
                        'origin_range_end': 220,
                        'cut_row': int(row_idx),
                    }
                ]

        class _ProbeSplitter:
            def __init__(self, word_engine):
                _ = word_engine

            def force_split_cells_at_row(self, table, row_idx):
                _ = table
                forced_rows.append(int(row_idx))
                return True

            def split_row_at(self, table, row_idx):
                _ = table, row_idx
                return object(), object()

            def apply_cut_border_policy(self, upper, lower, *, strategy, stage):
                _ = upper, lower, strategy, stage
                return None

        original_scratch = split_flow_module._create_scratch_probe_context
        original_disable = split_flow_module._disable_heading_rows
        original_scanner = split_flow_module.TableTopologyScanner
        original_splitter = split_flow_module.CanvasSplitter
        try:
            split_flow_module._create_scratch_probe_context = lambda app, source_table: {
                'ok': True,
                'table': object(),
                'cleanup': lambda: None,
                'probe_source': 'scratch',
                'copy_method': 'copy_paste',
                'copy_success': True,
            }
            split_flow_module._disable_heading_rows = lambda table: None
            split_flow_module.TableTopologyScanner = _ProbeScanner
            split_flow_module.CanvasSplitter = _ProbeSplitter
            result = split_flow_module._probe_split_candidate(
                _Owner(),
                object(),
                12,
                parent_node={},
                current_section_key='description',
                width_point=296.85,
                prefer_same_canvas=False,
            )
        finally:
            split_flow_module._create_scratch_probe_context = original_scratch
            split_flow_module._disable_heading_rows = original_disable
            split_flow_module.TableTopologyScanner = original_scanner
            split_flow_module.CanvasSplitter = original_splitter

        self.assertTrue(result['ok'])
        self.assertEqual(forced_rows, [12])
        self.assertTrue(result.get('boundary_blocked_by_vmerge'))
        self.assertEqual(result.get('boundary_merge_origins')[0]['row_span'], 40)

    def test_process_table_split_flow_extends_multi_fragment_probe_candidate(self) -> None:
        class _CountHolder:
            def __init__(self, count: int) -> None:
                self.Count = int(count)

        class _Range:
            def __init__(self, start: int, end: int) -> None:
                self.Start = int(start)
                self.End = int(end)

        class _Table:
            def __init__(self, rows: int, *, start: int = 10, end: int = 20) -> None:
                self.Rows = _CountHolder(rows)
                self.Columns = _CountHolder(2)
                self.Range = _Range(start, end)

        class _Upper:
            def Delete(self):
                return None

        class _CanvasContent:
            @staticmethod
            def Delete():
                return None

        class _CanvasDoc:
            Content = _CanvasContent()

            def Close(self, SaveChanges=0):
                _ = SaveChanges
                return None

        class _Documents:
            @staticmethod
            def Add(Visible=False):
                _ = Visible
                return _CanvasDoc()

        class _App:
            Documents = _Documents()

        class _Word:
            app = _App()

        class _Parser:
            description_paragraph_split_mode = 'word'

            def __init__(self) -> None:
                self.word = _Word()
                self.emitted: list[tuple[str, float, float]] = []

            def _get_table_splitting_max_height_cm(self):
                return 24.0

            def _get_table_width_point(self, table):
                _ = table
                return 321.0

            def _prev_paragraph_ends_with_period(self, _parent_node) -> bool:
                return True

            def _capture_table_in_canvas_payload(self, table, **kwargs):
                _ = table, kwargs
                return {
                    'ok': True,
                    'fragments': [('final.jpg', 100.0, 90.0)],
                    'fragment_count': 1,
                }

            def _emit_fragments(self, fragments, parent_node, section, table_obj):
                _ = parent_node, section, table_obj
                self.emitted = list(fragments)
                return True

            def _set_table_process_failure_context(self, **kwargs):
                _ = kwargs
                return None

            def _remove_temp_image_if_exists(self, filename):
                _ = filename
                return None

        parser = _Parser()
        initial_table = _Table(78, start=100, end=200)
        lower_tables = [_Table(10, start=201, end=300)]
        cut_rows = iter([37, -1])

        def _pick_candidate(_owner, _scanner, _current_table, _start_row, **kwargs):
            _ = _owner, _scanner, _current_table, _start_row, kwargs
            return (
                {
                    'ok': True,
                    'fragments': [('probe_p1.jpg', 100.0, 120.0), ('probe_p2.jpg', 100.0, 118.0)],
                    'fragment_count': 2,
                    'safe_row': 2,
                    'requested_row': 2,
                    'height_mm': 120.0,
                },
                None,
            )

        def _apply_split(_scanner, _splitter, _current_table, safe_row, *, current_section_key):
            _ = _scanner, _splitter, _current_table, current_section_key
            return _Upper(), object(), int(safe_row)

        def _refresh(_canvas):
            _ = _canvas
            if lower_tables:
                return lower_tables.pop(0)
            return None

        original_copy = split_flow_module._copy_table_to_canvas
        original_disable = split_flow_module._disable_heading_rows
        original_scanner = split_flow_module.TableTopologyScanner
        original_splitter = split_flow_module.CanvasSplitter
        original_row_top = split_flow_module._build_row_top_map
        original_row_heights = split_flow_module._collect_row_heights
        original_choose = split_flow_module._choose_cut_row
        original_pick = split_flow_module._pick_split_candidate
        original_apply = split_flow_module._apply_split_to_current_table
        original_refresh = split_flow_module._refresh_first_canvas_table
        try:
            split_flow_module._copy_table_to_canvas = lambda source_table, canvas: initial_table
            split_flow_module._disable_heading_rows = lambda table: None
            split_flow_module.TableTopologyScanner = lambda *args, **kwargs: object()
            split_flow_module.CanvasSplitter = lambda *args, **kwargs: object()
            split_flow_module._build_row_top_map = lambda table: {}
            split_flow_module._collect_row_heights = lambda table: []
            split_flow_module._choose_cut_row = lambda row_top_map, row_heights, target_slice_pt: (int(next(cut_rows)), 'row_height')
            split_flow_module._pick_split_candidate = _pick_candidate
            split_flow_module._apply_split_to_current_table = _apply_split
            split_flow_module._refresh_first_canvas_table = _refresh

            result = split_flow_module.process_table_split_flow(parser, initial_table, {}, 'description')
        finally:
            split_flow_module._copy_table_to_canvas = original_copy
            split_flow_module._disable_heading_rows = original_disable
            split_flow_module.TableTopologyScanner = original_scanner
            split_flow_module.CanvasSplitter = original_splitter
            split_flow_module._build_row_top_map = original_row_top
            split_flow_module._collect_row_heights = original_row_heights
            split_flow_module._choose_cut_row = original_choose
            split_flow_module._pick_split_candidate = original_pick
            split_flow_module._apply_split_to_current_table = original_apply
            split_flow_module._refresh_first_canvas_table = original_refresh

        self.assertTrue(result)
        self.assertEqual(
            parser.emitted,
            [('probe_p1.jpg', 100.0, 120.0), ('probe_p2.jpg', 100.0, 118.0), ('final.jpg', 100.0, 90.0)],
        )

    def test_process_table_split_flow_accepts_multi_fragment_final_capture(self) -> None:
        class _CountHolder:
            def __init__(self, count: int) -> None:
                self.Count = int(count)

        class _Range:
            def __init__(self, start: int, end: int) -> None:
                self.Start = int(start)
                self.End = int(end)

        class _Table:
            def __init__(self, rows: int, *, start: int = 10, end: int = 20) -> None:
                self.Rows = _CountHolder(rows)
                self.Columns = _CountHolder(2)
                self.Range = _Range(start, end)

        class _CanvasContent:
            @staticmethod
            def Delete():
                return None

        class _CanvasDoc:
            Content = _CanvasContent()

            def Close(self, SaveChanges=0):
                _ = SaveChanges
                return None

        class _Documents:
            @staticmethod
            def Add(Visible=False):
                _ = Visible
                return _CanvasDoc()

        class _App:
            Documents = _Documents()

        class _Word:
            app = _App()

        class _Parser:
            description_paragraph_split_mode = 'word'

            def __init__(self) -> None:
                self.word = _Word()
                self.emitted: list[tuple[str, float, float]] = []

            def _get_table_splitting_max_height_cm(self):
                return 24.0

            def _get_table_width_point(self, table):
                _ = table
                return 321.0

            def _prev_paragraph_ends_with_period(self, _parent_node) -> bool:
                return True

            def _capture_table_in_canvas_payload(self, table, **kwargs):
                _ = table, kwargs
                return {
                    'ok': True,
                    'fragments': [('final_p1.jpg', 100.0, 120.0), ('final_p2.jpg', 100.0, 118.0)],
                    'fragment_count': 2,
                }

            def _emit_fragments(self, fragments, parent_node, section, table_obj):
                _ = parent_node, section, table_obj
                self.emitted = list(fragments)
                return True

            def _set_table_process_failure_context(self, **kwargs):
                _ = kwargs
                return None

            def _remove_temp_image_if_exists(self, filename):
                _ = filename
                return None

        parser = _Parser()
        initial_table = _Table(1, start=100, end=200)

        original_copy = split_flow_module._copy_table_to_canvas
        original_disable = split_flow_module._disable_heading_rows
        original_scanner = split_flow_module.TableTopologyScanner
        original_splitter = split_flow_module.CanvasSplitter
        original_row_top = split_flow_module._build_row_top_map
        original_row_heights = split_flow_module._collect_row_heights
        original_choose = split_flow_module._choose_cut_row
        try:
            split_flow_module._copy_table_to_canvas = lambda source_table, canvas: initial_table
            split_flow_module._disable_heading_rows = lambda table: None
            split_flow_module.TableTopologyScanner = lambda *args, **kwargs: object()
            split_flow_module.CanvasSplitter = lambda *args, **kwargs: object()
            split_flow_module._build_row_top_map = lambda table: {}
            split_flow_module._collect_row_heights = lambda table: []
            split_flow_module._choose_cut_row = lambda row_top_map, row_heights, target_slice_pt: (-1, 'row_height')

            result = split_flow_module.process_table_split_flow(parser, initial_table, {}, 'description')
        finally:
            split_flow_module._copy_table_to_canvas = original_copy
            split_flow_module._disable_heading_rows = original_disable
            split_flow_module.TableTopologyScanner = original_scanner
            split_flow_module.CanvasSplitter = original_splitter
            split_flow_module._build_row_top_map = original_row_top
            split_flow_module._collect_row_heights = original_row_heights
            split_flow_module._choose_cut_row = original_choose

        self.assertTrue(result)
        self.assertEqual(
            parser.emitted,
            [('final_p1.jpg', 100.0, 120.0), ('final_p2.jpg', 100.0, 118.0)],
        )

    def test_process_table_split_flow_keeps_scratch_first_on_second_loop(self) -> None:
        class _CountHolder:
            def __init__(self, count: int) -> None:
                self.Count = int(count)

        class _Range:
            def __init__(self, start: int, end: int) -> None:
                self.Start = int(start)
                self.End = int(end)

        class _Table:
            def __init__(self, rows: int, *, start: int = 10, end: int = 20) -> None:
                self.Rows = _CountHolder(rows)
                self.Columns = _CountHolder(2)
                self.Range = _Range(start, end)

        class _Upper:
            def Delete(self):
                return None

        class _CanvasContent:
            @staticmethod
            def Delete():
                return None

        class _CanvasDoc:
            Content = _CanvasContent()

            def Close(self, SaveChanges=0):
                _ = SaveChanges
                return None

        class _Documents:
            @staticmethod
            def Add(Visible=False):
                _ = Visible
                return _CanvasDoc()

        class _App:
            Documents = _Documents()

        class _Word:
            app = _App()

        class _Parser:
            description_paragraph_split_mode = 'word'

            def __init__(self) -> None:
                self.word = _Word()
                self.emitted: list[tuple[str, float, float]] = []

            def _get_table_splitting_max_height_cm(self):
                return 24.0

            def _get_table_width_point(self, table):
                _ = table
                return 321.0

            def _prev_paragraph_ends_with_period(self, _parent_node) -> bool:
                return True

            def _capture_table_in_canvas(self, table, **kwargs):
                _ = table, kwargs
                return 'final.jpg', 100.0, 120.0

            def _emit_fragments(self, fragments, parent_node, section, table_obj):
                _ = parent_node, section, table_obj
                self.emitted = list(fragments)
                return True

            def _set_table_process_failure_context(self, **kwargs):
                _ = kwargs
                return None

            def _remove_temp_image_if_exists(self, filename):
                _ = filename
                return None

        parser = _Parser()
        initial_table = _Table(89, start=100, end=200)
        lower_tables = [_Table(78, start=201, end=300), _Table(10, start=301, end=360)]
        cut_rows = iter([35, 30, -1])
        candidate_rows = iter([12, 17])
        loop_preferences: list[bool] = []

        def _pick_candidate(_owner, _scanner, _current_table, _start_row, **kwargs):
            loop_preferences.append(bool(kwargs['prefer_same_canvas']))
            safe_row = int(next(candidate_rows))
            return (
                {
                    'ok': True,
                    'file': f'frag{safe_row}.jpg',
                    'width_mm': 100.0,
                    'height_mm': 120.0,
                    'safe_row': safe_row,
                    'requested_row': safe_row,
                },
                None,
            )

        def _apply_split(_scanner, _splitter, _current_table, safe_row, *, current_section_key):
            _ = _scanner, _splitter, _current_table, current_section_key
            return _Upper(), object(), int(safe_row)

        def _refresh(_canvas):
            _ = _canvas
            if lower_tables:
                return lower_tables.pop(0)
            return None

        original_copy = split_flow_module._copy_table_to_canvas
        original_disable = split_flow_module._disable_heading_rows
        original_scanner = split_flow_module.TableTopologyScanner
        original_splitter = split_flow_module.CanvasSplitter
        original_row_top = split_flow_module._build_row_top_map
        original_row_heights = split_flow_module._collect_row_heights
        original_choose = split_flow_module._choose_cut_row
        original_pick = split_flow_module._pick_split_candidate
        original_apply = split_flow_module._apply_split_to_current_table
        original_refresh = split_flow_module._refresh_first_canvas_table
        try:
            split_flow_module._copy_table_to_canvas = lambda source_table, canvas: initial_table
            split_flow_module._disable_heading_rows = lambda table: None
            split_flow_module.TableTopologyScanner = lambda *args, **kwargs: object()
            split_flow_module.CanvasSplitter = lambda *args, **kwargs: object()
            split_flow_module._build_row_top_map = lambda table: {}
            split_flow_module._collect_row_heights = lambda table: []
            split_flow_module._choose_cut_row = lambda row_top_map, row_heights, target_slice_pt: (int(next(cut_rows)), 'row_height')
            split_flow_module._pick_split_candidate = _pick_candidate
            split_flow_module._apply_split_to_current_table = _apply_split
            split_flow_module._refresh_first_canvas_table = _refresh

            result = split_flow_module.process_table_split_flow(parser, initial_table, {}, 'description')
        finally:
            split_flow_module._copy_table_to_canvas = original_copy
            split_flow_module._disable_heading_rows = original_disable
            split_flow_module.TableTopologyScanner = original_scanner
            split_flow_module.CanvasSplitter = original_splitter
            split_flow_module._build_row_top_map = original_row_top
            split_flow_module._collect_row_heights = original_row_heights
            split_flow_module._choose_cut_row = original_choose
            split_flow_module._pick_split_candidate = original_pick
            split_flow_module._apply_split_to_current_table = original_apply
            split_flow_module._refresh_first_canvas_table = original_refresh

        self.assertTrue(result)
        self.assertEqual(loop_preferences, [False, False])
        self.assertEqual(len(parser.emitted), 3)


if __name__ == '__main__':
    unittest.main()
