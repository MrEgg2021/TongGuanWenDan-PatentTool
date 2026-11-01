from __future__ import annotations

import unittest

from lxml import etree

from core.document_parser.structure_mixin_impl import StructureNormalizationMixin


class _DummyXmlBuilder:
    def create_paragraph(self, parent, text: str = ""):
        node = etree.SubElement(parent, "p")
        node.text = text
        return node


class _DummyStructureOwner(StructureNormalizationMixin):
    def __init__(self, patent_type: str | None, *paragraphs: str):
        self.patent_type = patent_type
        self.xml = _DummyXmlBuilder()
        root = etree.Element("description")
        for text in paragraphs:
            p = etree.SubElement(root, "p")
            p.text = text
        self.sections = {"description": root}


class StructureDisclosureHeadingResolutionTests(unittest.TestCase):
    def test_patent_type_controls_only_invention_vs_utility_heading(self) -> None:
        owner = _DummyStructureOwner(
            "utility_model",
            "一种装置",
            "发明内容 本实用新型提供了一种改进结构。",
        )

        owner._normalize_description_structure()

        disclosure = owner.sections["description"].find("disclosure")
        self.assertIsNotNone(disclosure)
        heading = disclosure.find("heading")
        self.assertEqual(heading.text, "实用新型内容")

    def test_other_disclosure_titles_are_preserved(self) -> None:
        owner = _DummyStructureOwner(
            "utility_model",
            "一种装置",
            "技术方案 包括处理器和存储器。",
        )

        owner._normalize_description_structure()

        disclosure = owner.sections["description"].find("disclosure")
        self.assertIsNotNone(disclosure)
        heading = disclosure.find("heading")
        self.assertEqual(heading.text, "技术方案")


if __name__ == "__main__":
    unittest.main()
