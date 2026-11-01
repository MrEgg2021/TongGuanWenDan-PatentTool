from __future__ import annotations
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QDialog
from gui.batch_run_impl.request_form_flow import collect_request_form_settings

class _DummyCheck:

    def __init__(self, checked: bool):
        self._checked = checked

    def isChecked(self) -> bool:
        return bool(self._checked)

class _DummyBatchWindow:

    def __init__(self, confirm_req: bool=True):
        self.batch_chk_confirm_req = _DummyCheck(confirm_req)
        self._batch_file_types = {}
        self._batch_header_probe_map = {}
        self.current_files = []

    def update_progress(self, *_args, **_kwargs):
        return None

    def _set_current_file_label(self, file_path):
        self.current_files.append(file_path)

    def _build_request_form_initial_info(self, source_info, current_patent_type):
        return {'source_info': source_info, 'patent_type': current_patent_type}

class BatchPatentTypeResolutionFlowTests(unittest.TestCase):

    def test_request_form_disabled_uses_probe_and_centralized_prompt(self) -> None:
        window = _DummyBatchWindow()
        files = ['a.docx', 'b.docx', 'c.docx']

        def _probe(file_path, config_path=None):
            mapping = {'a.docx': {'patent_type': 'invention', 'matched_heading': '发明内容'}, 'b.docx': {'patent_type': None, 'matched_heading': None}, 'c.docx': {'patent_type': 'utility_model', 'matched_heading': '实用新型内容'}}
            return mapping[file_path]
        with patch('gui.batch_run_impl.request_form_flow.parse_request_info') as parse_mock, patch('gui.batch_run_impl.request_form_flow.probe_description_patent_type_heading', side_effect=_probe), patch('gui.batch_run_impl.request_form_flow.prompt_batch_patent_type_choices', return_value={'b.docx': 'utility_model'}) as prompt_mock:
            settings = collect_request_form_settings(window, files, config_path=None, enabled_sections={'claims': True, 'description': True, 'drawings': True, 'abstract': True, 'request_form': False})
        self.assertIsNotNone(settings)
        self.assertEqual(settings['a.docx']['effective_patent_type'], 'invention')
        self.assertEqual(settings['b.docx']['effective_patent_type'], 'utility_model')
        self.assertEqual(settings['c.docx']['effective_patent_type'], 'utility_model')
        self.assertEqual(settings['b.docx']['effective_patent_type_source'], 'manual_prompt')
        self.assertEqual(window._batch_file_types['a.docx'], 'invention')
        self.assertEqual(window._batch_file_types['b.docx'], 'utility_model')
        self.assertEqual(window._batch_file_types['c.docx'], 'utility_model')
        parse_mock.assert_not_called()
        prompt_mock.assert_called_once()

    def test_request_form_disabled_cancel_aborts_batch(self) -> None:
        window = _DummyBatchWindow()
        with patch('gui.batch_run_impl.request_form_flow.parse_request_info') as parse_mock, patch('gui.batch_run_impl.request_form_flow.probe_description_patent_type_heading', return_value={'patent_type': None, 'matched_heading': None}), patch('gui.batch_run_impl.request_form_flow.prompt_batch_patent_type_choices', return_value=None):
            settings = collect_request_form_settings(window, ['a.docx'], config_path=None, enabled_sections={'claims': True, 'description': True, 'drawings': True, 'abstract': True, 'request_form': False})
        self.assertIsNone(settings)
        parse_mock.assert_not_called()

    def test_request_form_and_description_disabled_skip_probe_and_prompt(self) -> None:
        window = _DummyBatchWindow()
        files = ['a.docx', 'b.docx']
        with patch('gui.batch_run_impl.request_form_flow.parse_request_info') as parse_mock, patch('gui.batch_run_impl.request_form_flow.probe_description_patent_type_heading') as probe_mock, patch('gui.batch_run_impl.request_form_flow.prompt_batch_patent_type_choices') as prompt_mock:
            settings = collect_request_form_settings(window, files, config_path=None, enabled_sections={'claims': True, 'description': False, 'drawings': True, 'abstract': True, 'request_form': False})
        self.assertEqual(settings, {'a.docx': {'patent_type': None, 'effective_patent_type': None, 'effective_patent_type_source': None, 'request_info': None, 'request_form_prefill_available': None, 'effective_enabled_sections': {'claims': True, 'description': False, 'drawings': True, 'abstract': True, 'request_form': False}}, 'b.docx': {'patent_type': None, 'effective_patent_type': None, 'effective_patent_type_source': None, 'request_info': None, 'request_form_prefill_available': None, 'effective_enabled_sections': {'claims': True, 'description': False, 'drawings': True, 'abstract': True, 'request_form': False}}})
        self.assertEqual(window._batch_file_types, {})
        parse_mock.assert_not_called()
        probe_mock.assert_not_called()
        prompt_mock.assert_not_called()

    def test_request_form_enabled_keeps_missing_request_meta_files_in_confirmation_flow(self) -> None:
        window = _DummyBatchWindow()
        files = ['drawings_only.docx', 'description.docx', 'request_form.docx']
        window._batch_header_probe_map = {'drawings_only.docx': {'claims': False, 'description': False, 'drawings': True, 'abstract': False, 'request_meta': False}, 'description.docx': {'claims': False, 'description': True, 'drawings': False, 'abstract': True, 'request_meta': False}, 'request_form.docx': {'claims': False, 'description': False, 'drawings': False, 'abstract': False, 'request_meta': True}}

        def _exec_embedded(**kwargs):
            return (QDialog.Accepted, {'title': '请求书文件'}, 'utility_model')
        window._exec_request_form_embedded = _exec_embedded
        with patch('gui.batch_run_impl.request_form_flow.parse_request_info', return_value={'title': '请求书文件', 'patent_type': 'utility_model'}) as parse_mock, patch('gui.batch_run_impl.request_form_flow.probe_description_patent_type_heading') as probe_mock, patch('gui.batch_run_impl.request_form_flow.prompt_batch_patent_type_choices') as prompt_mock:
            settings = collect_request_form_settings(window, files, config_path=None, enabled_sections={'claims': True, 'description': True, 'drawings': True, 'abstract': True, 'request_form': True})
        self.assertIsNotNone(settings)
        self.assertEqual(settings['drawings_only.docx']['effective_enabled_sections'], {'claims': False, 'description': False, 'drawings': True, 'abstract': False, 'request_form': True})
        self.assertFalse(settings['drawings_only.docx']['request_form_prefill_available'])
        self.assertFalse(settings['description.docx']['request_form_prefill_available'])
        self.assertTrue(settings['request_form.docx']['request_form_prefill_available'])
        self.assertEqual(settings['drawings_only.docx']['effective_patent_type'], 'utility_model')
        self.assertEqual(settings['description.docx']['effective_patent_type'], 'utility_model')
        self.assertEqual(settings['request_form.docx']['effective_patent_type'], 'utility_model')
        self.assertEqual(settings['request_form.docx']['effective_patent_type_source'], 'request_form')
        self.assertEqual(parse_mock.call_count, 3)
        self.assertEqual(window.current_files, files)
        probe_mock.assert_not_called()
        prompt_mock.assert_not_called()

    def test_request_form_enabled_without_batch_confirm_force_confirms_only_missing_request_meta_files(self) -> None:
        window = _DummyBatchWindow(confirm_req=False)
        files = ['missing_confirm.docx', 'with_confirm.docx']
        window._batch_header_probe_map = {'missing_confirm.docx': {'claims': True, 'description': True, 'drawings': True, 'abstract': True, 'request_meta': False}, 'with_confirm.docx': {'claims': True, 'description': True, 'drawings': True, 'abstract': True, 'request_meta': True}}
        exec_calls = []

        def _exec_embedded(**kwargs):
            exec_calls.append(kwargs)
            return (QDialog.Accepted, {'title': '缺页手填'}, 'utility_model')
        window._exec_request_form_embedded = _exec_embedded

        def _parse_request_info(file_path, config_path=None):
            mapping = {'missing_confirm.docx': None, 'with_confirm.docx': {'title': '已有确认页', 'patent_type': 'invention'}}
            return mapping[file_path]
        with patch('gui.batch_run_impl.request_form_flow.parse_request_info', side_effect=_parse_request_info) as parse_mock, patch('gui.batch_run_impl.request_form_flow.probe_description_patent_type_heading') as probe_mock, patch('gui.batch_run_impl.request_form_flow.prompt_batch_patent_type_choices') as prompt_mock:
            settings = collect_request_form_settings(window, files, config_path=None, enabled_sections={'claims': True, 'description': True, 'drawings': True, 'abstract': True, 'request_form': True})
        self.assertIsNotNone(settings)
        self.assertEqual(parse_mock.call_count, 2)
        self.assertEqual(len(exec_calls), 1)
        self.assertEqual(exec_calls[0]['cache_key'], 'missing_confirm.docx')
        self.assertFalse(settings['missing_confirm.docx']['request_form_prefill_available'])
        self.assertTrue(settings['with_confirm.docx']['request_form_prefill_available'])
        self.assertEqual(settings['missing_confirm.docx']['effective_patent_type'], 'utility_model')
        self.assertEqual(settings['missing_confirm.docx']['effective_patent_type_source'], 'request_form')
        self.assertEqual(settings['with_confirm.docx']['effective_patent_type'], 'invention')
        self.assertEqual(settings['with_confirm.docx']['effective_patent_type_source'], 'request_form')
        probe_mock.assert_not_called()
        prompt_mock.assert_not_called()
if __name__ == '__main__':
    unittest.main()
