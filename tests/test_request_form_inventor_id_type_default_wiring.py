import unittest
from pathlib import Path


class RequestFormInventorIdTypeDefaultWiringTests(unittest.TestCase):
    def test_inventor_id_type_combo_is_fixed_and_non_editable(self) -> None:
        source = Path("gui/widgets_impl/request_form/tabs_impl.py").read_text(encoding="utf-8")
        self.assertIn("_INVENTOR_ID_TYPE_OPTIONS =", source)
        self.assertIn("id_type_combo.setEditable(False)", source)
        self.assertIn("id_type_combo.setCurrentIndex(0)", source)
        self.assertIn(r"\u5c45\u6c11\u8eab\u4efd\u8bc1", source)
        self.assertIn(r"\u62a4\u7167", source)
        self.assertIn(r"\u5176\u4ed6", source)

    def test_inventor_id_type_normalization_falls_back_to_default(self) -> None:
        source = Path("gui/widgets_impl/request_form/tabs_impl.py").read_text(encoding="utf-8")
        self.assertIn("def _normalize_inventor_id_type_value(value: object) -> str:", source)
        self.assertIn("if not text:", source)
        self.assertIn("return _INVENTOR_ID_TYPE_OPTIONS[0]", source)

    def test_autofill_paths_do_not_clear_inventor_id_type_to_empty(self) -> None:
        anchor_source = Path("gui/widgets_impl/request_form/fact_autofill_impl/anchor_ops.py").read_text(encoding="utf-8")
        activation_source = Path("gui/widgets_impl/request_form/fact_autofill_impl/activation_ops.py").read_text(encoding="utf-8")
        prefill_source = Path("gui/widgets_impl/request_form/fact_autofill_impl/prefill_ops.py").read_text(encoding="utf-8")

        self.assertIn("default_idx = id_type_w.findText(", anchor_source)
        self.assertIn("default_idx = id_type_combo.findText(", activation_source)
        self.assertIn("_normalize_inventor_id_type(", prefill_source)
        self.assertIn("_set_combo_by_data_or_text(", prefill_source)


if __name__ == "__main__":
    unittest.main()
