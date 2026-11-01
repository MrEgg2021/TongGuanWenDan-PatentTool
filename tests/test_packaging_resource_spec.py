import unittest
from pathlib import Path


class PackagingResourceSpecTests(unittest.TestCase):
    def test_gui_spec_includes_required_runtime_resources(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        spec_text = (repo_root / "CPCXMLGui.spec").read_text(encoding="utf-8")
        normalized = spec_text.replace("\\\\", "\\")

        required_snippets = [
            r"resources\OPEN_SOURCE_LICENSE.zh-CN.md",
            r"resources\official_doc_supported_types.json",
            r"resources\official_doc_pdf_field_matrix.json",
            r"resources\codeset_local_guobie.json",
            r"resources\assets\github.svg",
            r"gui\ui_layout_impl\assets\check_dark.svg",
            r"gui\ui_layout_impl\assets\chevron_right.svg",
        ]

        missing = [s for s in required_snippets if s not in normalized]
        self.assertFalse(missing, "Missing required spec resources:\n" + "\n".join(missing))

    def test_main_spec_excludes_optional_data_stack_unused_at_runtime(self) -> None:
        text = (Path(__file__).resolve().parents[1] / "CPCXMLGui.spec").read_text(encoding="utf-8")
        self.assertIn("'scipy'", text)
        self.assertIn("'numpy.f2py'", text)
        self.assertIn("'pandas'", text)

    def test_main_spec_has_no_private_keys_or_activation_resources(self) -> None:
        text = (Path(__file__).resolve().parents[1] / "CPCXMLGui.spec").read_text(encoding="utf-8")
        for forbidden in ("*private*key*.pem", "license_public_keys.json"):
            self.assertNotIn(forbidden, text)

    def test_main_spec_retains_build_options_and_license_material(self) -> None:
        text = (Path(__file__).resolve().parents[1] / "CPCXMLGui.spec").read_text(encoding="utf-8")
        self.assertIn("upx=False", text)
        self.assertNotIn("upx=True", text)
        self.assertIn('return f"{base_name}_v{_load_app_version()}"', text)
        for required in ("LICENSE", "THIRD_PARTY_NOTICES.md", "third_party_licenses"):
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
