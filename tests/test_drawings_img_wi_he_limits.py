import unittest

from lxml import etree

from core.xml_generator import XMLBuilder


class DrawingsImgWiHeLimitsTests(unittest.TestCase):
    def _builder(self, max_wi: float = 164.0, max_he: float = 230.0) -> XMLBuilder:
        return XMLBuilder(
            {
                "drawings_img_max_wi_mm": float(max_wi),
                "drawings_img_max_he_mm": float(max_he),
            }
        )

    def test_drawings_dims_within_limits_kept(self) -> None:
        xml = self._builder()
        parent = etree.Element("p")
        img = xml.create_image_node(parent, "a.jpg", 100.0, 200.0, img_type="draw", inline=True)
        self.assertEqual(img.attrib["wi"], "100.00")
        self.assertEqual(img.attrib["he"], "200.00")

    def test_drawings_dims_exceed_width_scaled_down(self) -> None:
        xml = self._builder()
        parent = etree.Element("p")
        img = xml.create_image_node(parent, "a.jpg", 200.0, 100.0, img_type="draw", inline=True)
        self.assertEqual(img.attrib["wi"], "164.00")
        self.assertEqual(img.attrib["he"], "82.00")

    def test_drawings_dims_exceed_height_scaled_down(self) -> None:
        xml = self._builder()
        parent = etree.Element("p")
        img = xml.create_image_node(parent, "a.jpg", 100.0, 300.0, img_type="draw", inline=True)
        self.assertEqual(img.attrib["wi"], "76.66")
        self.assertEqual(img.attrib["he"], "229.98")

    def test_desc_images_not_clamped(self) -> None:
        xml = self._builder()
        parent = etree.Element("p")
        img = xml.create_image_node(parent, "a.jpg", 200.0, 300.0, img_type="desc", inline=True)
        self.assertEqual(img.attrib["wi"], "200.00")
        self.assertEqual(img.attrib["he"], "300.00")


if __name__ == "__main__":
    unittest.main()
