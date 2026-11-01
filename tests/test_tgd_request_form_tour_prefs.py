from __future__ import annotations

import unittest

import gui.tgd_request_form_tour as tour


class TgdRequestFormTourPrefsTests(unittest.TestCase):
    def test_mark_auto_opened_round_trip(self) -> None:
        self.assertIsInstance(tour.TGD_DATA_MANAGEMENT_GUIDE_AUTO_OPENED_KEY, str)

    def test_build_guide_steps_uses_common_info_language(self) -> None:
        steps = tour.build_data_management_request_guide_steps()

        self.assertEqual(3, len(steps))
        self.assertEqual("批量导入并整理信息", steps[0][0])
        self.assertEqual("转档时勾选请求书即可复用", steps[1][0])
        self.assertEqual("修改后可写回继续复用", steps[2][0])
        self.assertIn("历史案卷包", steps[0][1])
        self.assertIn("转档功能中勾选请求书", steps[1][1])
        self.assertIn("保存回这里", steps[2][1])

    def test_build_guide_summary_mentions_request_form_reuse(self) -> None:
        summary = tour.get_data_management_request_guide_summary()

        self.assertIn("请求书", summary)
        self.assertIn("历史案卷包", summary)
        self.assertIn("转档功能中勾选请求书", summary)


if __name__ == "__main__":
    unittest.main()
