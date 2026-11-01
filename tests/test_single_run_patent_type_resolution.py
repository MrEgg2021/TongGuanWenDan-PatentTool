from __future__ import annotations
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QDialog
from gui.single_run_impl.preflight_flow import SingleRunContext, prepare_single_run_context

class _DummyWindow:

    def __init__(self, enabled_sections: dict, exec_result=None, header_probe=None):
        self._enabled_sections = enabled_sections
        self._request_form_cache = {}
        self._exec_request_form_embedded = exec_result
        self._last_header_probe_single = header_probe

    def get_enabled_sections(self):
        return dict(self._enabled_sections)

    def get_description_paragraph_split_mode(self):
        return 'word'

    def _build_request_form_initial_info(self, source_info, current_patent_type):
        return {'source_info': source_info, 'patent_type': current_patent_type}

class SingleRunPatentTypeResolutionTests(unittest.TestCase):

    def test_request_form_disabled_uses_description_heading_and_skips_request_info(self) -> None:
        window = _DummyWindow({'claims': True, 'description': True, 'drawings': True, 'abstract': True, 'request_form': False})
        with patch('gui.single_run_impl.preflight_flow.parse_request_info') as parse_mock, patch('gui.single_run_impl.preflight_flow.prevalidate_single', return_value=True), patch('gui.single_run_impl.preflight_flow.probe_description_patent_type_heading', return_value={'patent_type': 'utility_model', 'matched_heading': '实用新型内容'}), patch('gui.single_run_impl.preflight_flow.prompt_single_patent_type_choice') as prompt_mock:
            ctx = prepare_single_run_context(window, 'demo.docx', config_path=None)
        self.assertIsInstance(ctx, SingleRunContext)
        self.assertEqual(ctx.effective_patent_type, 'utility_model')
        self.assertEqual(ctx.effective_patent_type_source, 'description_heading')
        self.assertEqual(ctx.patent_type, 'utility_model')
        self.assertEqual(ctx.requested_enabled_sections['description'], True)
        self.assertEqual(ctx.effective_enabled_sections['description'], True)
        parse_mock.assert_not_called()
        prompt_mock.assert_not_called()

    def test_request_form_disabled_prompts_when_description_has_no_direct_heading(self) -> None:
        window = _DummyWindow({'claims': True, 'description': True, 'drawings': True, 'abstract': True, 'request_form': False})
        with patch('gui.single_run_impl.preflight_flow.parse_request_info') as parse_mock, patch('gui.single_run_impl.preflight_flow.prevalidate_single', return_value=True), patch('gui.single_run_impl.preflight_flow.probe_description_patent_type_heading', return_value={'patent_type': None, 'matched_heading': None}), patch('gui.single_run_impl.preflight_flow.prompt_single_patent_type_choice', return_value='invention') as prompt_mock:
            ctx = prepare_single_run_context(window, 'demo.docx', config_path=None)
        self.assertEqual(ctx.effective_patent_type, 'invention')
        self.assertEqual(ctx.effective_patent_type_source, 'manual_prompt')
        self.assertEqual(ctx.effective_enabled_sections['description'], True)
        parse_mock.assert_not_called()
        prompt_mock.assert_called_once()

    def test_request_form_disabled_cancel_aborts_conversion(self) -> None:
        window = _DummyWindow({'claims': True, 'description': True, 'drawings': True, 'abstract': True, 'request_form': False})
        with patch('gui.single_run_impl.preflight_flow.parse_request_info') as parse_mock, patch('gui.single_run_impl.preflight_flow.prevalidate_single', return_value=True), patch('gui.single_run_impl.preflight_flow.probe_description_patent_type_heading', return_value={'patent_type': None, 'matched_heading': None}), patch('gui.single_run_impl.preflight_flow.prompt_single_patent_type_choice', return_value=None):
            ctx = prepare_single_run_context(window, 'demo.docx', config_path=None)
        self.assertIsNone(ctx)
        parse_mock.assert_not_called()

    def test_request_form_and_description_disabled_skip_probe_and_prompt(self) -> None:
        window = _DummyWindow({'claims': True, 'description': False, 'drawings': True, 'abstract': True, 'request_form': False})
        with patch('gui.single_run_impl.preflight_flow.parse_request_info') as parse_mock, patch('gui.single_run_impl.preflight_flow.prevalidate_single', return_value=True), patch('gui.single_run_impl.preflight_flow.probe_description_patent_type_heading') as probe_mock, patch('gui.single_run_impl.preflight_flow.prompt_single_patent_type_choice') as prompt_mock:
            ctx = prepare_single_run_context(window, 'demo.docx', config_path=None)
        self.assertIsInstance(ctx, SingleRunContext)
        self.assertIsNone(ctx.patent_type)
        self.assertIsNone(ctx.effective_patent_type)
        self.assertIsNone(ctx.effective_patent_type_source)
        self.assertEqual(ctx.effective_enabled_sections['description'], False)
        self.assertEqual(ctx.effective_enabled_sections['request_form'], False)
        parse_mock.assert_not_called()
        probe_mock.assert_not_called()
        prompt_mock.assert_not_called()

    def test_requested_description_is_ignored_when_header_probe_shows_drawings_only(self) -> None:
        window = _DummyWindow({'claims': True, 'description': True, 'drawings': True, 'abstract': True, 'request_form': False}, header_probe={'claims': False, 'description': False, 'drawings': True, 'abstract': False, 'request_meta': False})
        with patch('gui.single_run_impl.preflight_flow.parse_request_info') as parse_mock, patch('gui.single_run_impl.preflight_flow.prevalidate_single', return_value=True), patch('gui.single_run_impl.preflight_flow.probe_description_patent_type_heading') as probe_mock, patch('gui.single_run_impl.preflight_flow.prompt_single_patent_type_choice') as prompt_mock:
            ctx = prepare_single_run_context(window, 'demo.docx', config_path=None)
        self.assertIsInstance(ctx, SingleRunContext)
        self.assertEqual(ctx.effective_enabled_sections, {'claims': False, 'description': False, 'drawings': True, 'abstract': False, 'request_form': False})
        self.assertIsNone(ctx.patent_type)
        self.assertIsNone(ctx.effective_patent_type)
        self.assertIsNone(ctx.effective_patent_type_source)
        parse_mock.assert_not_called()
        probe_mock.assert_not_called()
        prompt_mock.assert_not_called()

    def test_requested_request_form_stays_enabled_when_request_meta_is_missing(self) -> None:
        exec_calls = []

        def _exec_embedded(**kwargs):
            exec_calls.append(kwargs)
            return (QDialog.Accepted, {'title': '手工补填标题'}, 'utility_model')
        window = _DummyWindow({'claims': True, 'description': False, 'drawings': True, 'abstract': True, 'request_form': True}, exec_result=_exec_embedded, header_probe={'claims': True, 'description': False, 'drawings': True, 'abstract': True, 'request_meta': False})
        with patch('gui.single_run_impl.preflight_flow.parse_request_info', return_value=None) as parse_mock, patch('gui.single_run_impl.preflight_flow.prevalidate_single', return_value=True), patch('gui.single_run_impl.preflight_flow.probe_description_patent_type_heading', return_value={'patent_type': 'utility_model', 'matched_heading': '实用新型内容'}) as probe_mock, patch('gui.single_run_impl.preflight_flow._ensure_office_closed_for_request_form', return_value=True), patch('gui.single_run_impl.preflight_flow.prompt_single_patent_type_choice') as prompt_mock:
            ctx = prepare_single_run_context(window, 'demo.docx', config_path=None)
        self.assertIsInstance(ctx, SingleRunContext)
        self.assertEqual(ctx.requested_enabled_sections['request_form'], True)
        self.assertEqual(ctx.effective_enabled_sections['request_form'], True)
        self.assertEqual(ctx.request_form_prefill_available, False)
        self.assertEqual(ctx.effective_patent_type, 'utility_model')
        self.assertEqual(ctx.effective_patent_type_source, 'request_form')
        self.assertEqual(len(exec_calls), 1)
        self.assertIsNone(exec_calls[0]['initial_request_info']['source_info'])
        parse_mock.assert_called_once()
        probe_mock.assert_called_once()
        prompt_mock.assert_not_called()

    def test_request_form_enabled_still_uses_request_form_result_as_effective_type(self) -> None:

        def _exec_embedded(**_kwargs):
            return (QDialog.Accepted, {'title': '一种装置'}, 'utility_model')
        window = _DummyWindow({'claims': True, 'description': True, 'drawings': True, 'abstract': True, 'request_form': True}, exec_result=_exec_embedded)
        with patch('gui.single_run_impl.preflight_flow.parse_request_info', return_value={'title': '一种装置', 'patent_type': 'invention'}) as parse_mock, patch('gui.single_run_impl.preflight_flow.prevalidate_single', return_value=True), patch('gui.single_run_impl.preflight_flow._ensure_office_closed_for_request_form', return_value=True), patch('gui.single_run_impl.preflight_flow.prompt_single_patent_type_choice') as prompt_mock:
            ctx = prepare_single_run_context(window, 'demo.docx', config_path=None)
        self.assertEqual(ctx.effective_patent_type, 'utility_model')
        self.assertEqual(ctx.effective_patent_type_source, 'request_form')
        self.assertEqual(ctx.patent_type, 'utility_model')
        parse_mock.assert_called_once()
        prompt_mock.assert_not_called()
if __name__ == '__main__':
    unittest.main()
