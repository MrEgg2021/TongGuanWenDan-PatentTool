from __future__ import annotations

import unittest
from unittest.mock import patch

from gui.request_form_ui import build_request_form_initial_info


class RequestFormUiWrapperTests(unittest.TestCase):
    def test_build_request_form_initial_info_delegates_to_builder(self) -> None:
        parsed_info = {"k": "v"}
        patent_type = "invention"

        with (
            patch("gui.request_form_ui.ensure_request_form_extractors_ready") as mock_extract,
            patch("gui.request_form_ui.ensure_request_form_code_maps_ready") as mock_maps,
            patch("gui.request_form_ui.build_request_form_payload", return_value={"ok": 1}) as mock_builder,
        ):
            result = build_request_form_initial_info(parsed_info, patent_type)

        self.assertEqual(result, {"ok": 1})
        mock_extract.assert_called_once_with()
        mock_maps.assert_called_once_with()
        mock_builder.assert_called_once_with(parsed_info, patent_type)


if __name__ == "__main__":
    unittest.main()
