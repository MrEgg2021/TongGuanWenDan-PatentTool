from __future__ import annotations

import unittest
from unittest.mock import patch

from core.official_docs.pdf_entity_extract import extract_pdf_entity_fields


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = str(text or "")

    def get_text(self, mode: str) -> str:
        _ = mode
        return self._text


class _FakeDoc:
    def __init__(self, text: str) -> None:
        self.page_count = 1
        self._page = _FakePage(text)

    def __getitem__(self, index: int) -> _FakePage:
        _ = index
        return self._page

    def close(self) -> None:
        return None


class OfficialDocsPdfEntityExtractRulesTests(unittest.TestCase):
    def test_extract_applicant_or_patentee_for_procedures_correction_notice(self) -> None:
        sample_text = "申请人或专利权人：中国联合网络通信有限公司清远市分公司"
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="200029|办理手续补正通知书",
            )

        self.assertEqual(result.status, "成功")
        self.assertEqual(result.applicant, "中国联合网络通信有限公司清远市分公司")

    def test_extract_applicant_or_requester_consumes_complete_label(self) -> None:
        sample_text = "申请人或请求人：讯豪电子（昆山）有限公司"
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210326|向外国申请专利保密审查意见通知书",
            )

        self.assertEqual(result.status, "成功")
        self.assertEqual(result.applicant, "讯豪电子（昆山）有限公司")

    def test_extract_applicant_inventor_department_agency(self) -> None:
        sample_text = "\n".join(
            [
                "审查部门：专利审查协作湖北中心",
                "专利权人：西安交通大学,中国航发四川燃气涡轮研究院",
                "发明人：乔百杰,贾思腾,杜军",
                "专利代理机构：中济纬天专利代理有限公司",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="200101|受理通知书",
            )

        self.assertEqual(result.status, "成功")
        self.assertEqual(result.department, "专利审查协作湖北中心")
        self.assertEqual(result.center, "专利审查协作湖北中心")
        self.assertIn("西安交通大学", result.applicant)
        self.assertIn("中国航发四川燃气涡轮研究院", result.applicant)
        self.assertIn("乔百杰", result.inventor)
        self.assertIn("贾思腾", result.inventor)
        self.assertIn("杜军", result.inventor)
        self.assertIn("中济纬天专利代理有限公司", result.agency_raw)
        self.assertIn("evidence_department", result.evidence)
        self.assertIn("evidence_applicant", result.evidence)
        self.assertIn("evidence_inventor", result.evidence)
        self.assertIn("evidence_agency_raw", result.evidence)

    def test_extract_panel_info_for_review_notice(self) -> None:
        sample_text = "\n".join(
            [
                "复审请求人：西安交通大学",
                "合议组组长：刘丽伟",
                "主审员：徐锦丹",
                "参审员：李慧子",
                "专利代理机构：中济纬天专利代理有限公司",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="200912|复审决定书",
            )

        self.assertEqual(result.status, "成功")
        self.assertEqual(result.applicant, "西安交通大学")
        self.assertEqual(result.panel_head, "刘丽伟")
        self.assertEqual(result.panel_main, "徐锦丹")
        self.assertEqual(result.panel_member, "李慧子")
        self.assertIn("中济纬天专利代理有限公司", result.agency_raw)
        self.assertIn("evidence_applicant", result.evidence)
        self.assertIn("evidence_panel_head", result.evidence)
        self.assertIn("evidence_panel_main", result.evidence)
        self.assertIn("evidence_panel_member", result.evidence)

    def test_extract_reject_reason_checked_rows_for_invention_only(self) -> None:
        sample_text = "\n".join(
            [
                "申请号或专利号：2025113838195",
                "☐权利要求____不符合专利法第九条第一款的规定。",
                "☒权利要求1不符合专利法第26条第4款的规定。",
                "☒权利要求1-7不具备专利法第22条第3款规定的创造性。",
                "对比文件：CN1234567A，CN7654321B。",
                "审查员：张三",
                "审查员电话：010-12345678",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )

        self.assertEqual(result.status, "成功")
        self.assertNotIn("☐", result.reject_reason)
        self.assertEqual(result.reject_reason, "权利要求1-7不具备专利法第22条第3款规定的创造性。")
        self.assertEqual(result.prior_art, "CN1234567A;CN7654321B")
        self.assertEqual(result.examiner, "张三")
        self.assertEqual(result.examiner_phone, "010-12345678")
        self.assertIn("evidence_reject_reason", result.evidence)
        self.assertIn("evidence_prior_art", result.evidence)

    def test_reject_reason_empty_for_non_invention(self) -> None:
        sample_text = "\n".join(
            [
                "申请号或专利号：2025301788232",
                "☒权利要求1不符合专利法第26条第4款的规定。",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="230302|第N次审查意见通知书",
            )
        self.assertEqual(result.reject_reason, "")

    def test_designer_maps_to_inventor(self) -> None:
        sample_text = "\n".join(
            [
                "申请号：2025301788232",
                "设计人：查晶娟,王晖,王恒,彭诗雨,贾悦",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="200101|受理通知书",
            )
        self.assertIn("查晶娟", result.inventor)
        self.assertIn("王晖", result.inventor)
        self.assertIn("王恒", result.inventor)
        self.assertIn("彭诗雨", result.inventor)
        self.assertIn("贾悦", result.inventor)

    def test_extract_applicant_compound_orgs_without_delimiter(self) -> None:
        sample_text = "\n".join(
            [
                "申请号或专利号：2025113838195",
                "申请人：西安交通大学中国航发四川燃气涡轮研究院",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertEqual(result.applicant, "西安交通大学中国航发四川燃气涡轮研究院")

    def test_extract_agency_ignores_noise_and_handles_wrapped_name(self) -> None:
        sample_text = "\n".join(
            [
                "专利代理机构：北京前审知识产",
                "权代理有限公司",
                "代理人：张三",
                "专利代理委托书 1 份2 页",
                "(4) 未经预约，申请人和/或代理师不得前来国家知识产权局与审查员举行会晤。",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertIn("北京前审知识产权代理有限公司", result.agency_raw.replace(" ", ""))
        self.assertNotIn("委托书", result.agency_raw)
        self.assertNotIn("会晤", result.agency_raw)

    def test_extract_agency_from_header_context_without_label(self) -> None:
        sample_text = "\n".join(
            [
                "北京市西城区广安门内大街169 号翔达国际商务酒店1623 室 北京",
                "北京中济纬天专利代理有限公司 覃婧婵(010-57150818)",
                "发文日：",
                "2025 年01 月24 日",
                "申请号或专利号：202122605037.5",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="201004|无效宣告请求受理通知书",
            )
        self.assertEqual(result.agency_raw, "北京中济纬天专利代理有限公司")

    def test_extract_agent_from_next_line_after_agency_context(self) -> None:
        sample_text = "\n".join(
            [
                "北京市西城区广安门内大街169号翔达国际商务酒店1623室 北京",
                "中济纬天专利代理有限公司",
                "覃婧婧(15810332554)",
                "发文日：2025年07月04日",
                "申请号：202310783301.0",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="200101|受理通知书",
            )

        self.assertTrue(result.agency_raw.endswith("中济纬天专利代理有限公司"))
        self.assertEqual(result.agent, "覃婧婧")

    def test_extract_agent_from_same_line_tail_after_agency_context(self) -> None:
        sample_text = "\n".join(
            [
                "北京市西城区广安门内大街169号翔达国际商务酒店1623室 北京",
                "中济纬天专利代理有限公司 覃婧婧(010-57150818)",
                "发文日：2025年07月04日",
                "申请号：202310783301.0",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="200101|受理通知书",
            )

        self.assertTrue(result.agency_raw.endswith("中济纬天专利代理有限公司"))
        self.assertEqual(result.agent, "覃婧婧")

    def test_extract_agent_does_not_misread_stop_lines_after_agency(self) -> None:
        sample_text = "\n".join(
            [
                "中济纬天专利代理有限公司",
                "发文日：2025年07月04日",
                "申请号：202310783301.0",
                "自动受理",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="200101|受理通知书",
            )

        self.assertTrue(result.agency_raw.endswith("中济纬天专利代理有限公司"))
        self.assertEqual(result.agent, "")

    def test_extract_examiner_name_variant_and_auto_review(self) -> None:
        sample_text = "\n".join(
            [
                "申请号或专利号：2025113838195",
                "审查员名称：自动审查",
                "联系电话：010-62356655",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertEqual(result.examiner, "自动审查")
        self.assertEqual(result.examiner_phone, "010-62356655")

    def test_extract_reject_reason_fallback_without_checkbox(self) -> None:
        sample_text = "\n".join(
            [
                "申请号或专利号：2025113838195",
                "权利要求1-10不具备专利法第22条第3款规定的创造性。",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertIn("权利要求1-10不具备专利法第22条第3款规定的创造性。", result.reject_reason)

    def test_extract_department_fallback_initial_review_department(self) -> None:
        sample_text = "\n".join(
            [
                "申请号或专利号：2025113838195",
                "国家知识产权局 初审及流程管理部",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertEqual(result.department, "初审及流程管理部")

    def test_extract_applicant_from_reexamination_requester_label(self) -> None:
        sample_text = "\n".join(
            [
                "复审请求人：西安交通大学",
                "发明人：张三",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertEqual(result.applicant, "西安交通大学")

    def test_reexamination_requester_phrase_without_colon_not_treated_as_applicant(self) -> None:
        sample_text = "\n".join(
            [
                "对国家知识产权局发出的复审通知书，复审请求人应当在收到该通知书之日起1个月内针对通知书指出的问题陈述意见。",
                "主审员：徐锦丹",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="200908|复审通知书",
            )
        self.assertEqual(result.applicant, "")

    def test_reexamination_sentence_with_applicant_word_without_delimiter_not_treated_as_applicant(self) -> None:
        sample_text = "\n".join(
            [
                "应申请人西安交通大学（下称复审请求人）于2024年12月17日提出的复审请求，现通知如下。",
                "主审员：徐锦丹",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="200908|复审通知书",
            )
        self.assertEqual(result.applicant, "")

    def test_extract_applicant_for_natural_person(self) -> None:
        sample_text = "\n".join(
            [
                "申请人：张三",
                "发明人：李四",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertEqual(result.applicant, "张三")

    def test_extract_applicant_for_foreign_enterprise(self) -> None:
        sample_text = "\n".join(
            [
                "专利权人：苹果公司(Apple Inc.)",
                "发明人：李四",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertEqual(result.applicant, "苹果公司(Apple Inc.)")

    def test_extract_applicant_for_hospital_org(self) -> None:
        sample_text = "\n".join(
            [
                "申请人：某某市第一人民医院",
                "发明人：李四",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertEqual(result.applicant, "某某市第一人民医院")

    def test_extract_applicant_preserves_semicolon_for_multi_entities(self) -> None:
        sample_text = "\n".join(
            [
                "申请人：浙江大学；杭州某某科技有限公司",
                "发明人：李四",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertEqual(result.applicant, "浙江大学；杭州某某科技有限公司")

    def test_extract_applicant_fallback_without_end_anchor(self) -> None:
        sample_text = "\n".join(
            [
                "申请人：某某科技有限公司",
                "继续说明第一行",
                "继续说明第二行",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertIn("某某科技有限公司", result.applicant)
        self.assertIn("继续说明第一行", result.applicant)

    def test_extract_applicant_stops_before_notice_title_line(self) -> None:
        sample_text = "\n".join(
            [
                "申请人或专利权人：西安交通大学 北京微纳精密机械有限公司",
                "延长期限审批通知书",
                "审查员：段立彦",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="200916|延长期限审批通知书",
            )
        self.assertEqual(result.applicant, "西安交通大学；北京微纳精密机械有限公司")

    def test_extract_applicant_skips_pct_header_noise_and_uses_labeled_value(self) -> None:
        sample_text = "\n".join(
            [
                "申请人或代理人的档案号 BJ-QSPCT-23022501",
                "国际申请号 PCT/CN2023/078301",
                "国际申请日(年/月/日) 2023年2月26日",
                "申请人：宁波诺丁汉新材料研究院有限公司",
                "发明人：张三",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="PCT/RO/102C|关于缴纳规定费用的通知书",
            )
        self.assertEqual(result.applicant, "宁波诺丁汉新材料研究院有限公司")

    def test_extract_applicant_supports_label_in_single_line_and_value_in_next_line(self) -> None:
        sample_text = "\n".join(
            [
                "申请人",
                "宁波诺丁汉新材料研究院有限公司",
                "发明人：张三",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="200101|受理通知书",
            )
        self.assertEqual(result.applicant, "宁波诺丁汉新材料研究院有限公司")

    def test_extract_applicant_stops_on_invention_title_standalone_label(self) -> None:
        sample_text = "\n".join(
            [
                "申请人",
                "宁波诺丁汉新材料研究院有限公司",
                "发明名称",
                "一种竖式微波热解沼渣制备合成气的系统和方法",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="PCT/RO/102C|关于国际申请号和国际申请日通知书",
            )
        self.assertEqual(result.applicant, "宁波诺丁汉新材料研究院有限公司")

    def test_extract_applicant_stops_on_invention_title_with_colon(self) -> None:
        sample_text = "\n".join(
            [
                "申请人：宁波诺丁汉新材料研究院有限公司",
                "发明创造名称：一种竖式微波热解沼渣制备合成气的系统和方法",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="PCT/RO/102C|关于国际申请号和国际申请日通知书",
            )
        self.assertEqual(result.applicant, "宁波诺丁汉新材料研究院有限公司")

    def test_extract_applicant_trims_pct_isa_210c_narrative_tail(self) -> None:
        sample_text = "\n".join(
            [
                "申请人",
                "宁波诺丁汉新材料研究院有限公司",
                "按照条约第18条，本国际检索报告由本国际检索单位做出并送交申请人。报告副本送交国际局。",
                "本国际检索报告总计",
                "5",
                "页。",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="PCT/ISA/210C|国际检索报告",
            )
        self.assertEqual(result.applicant, "宁波诺丁汉新材料研究院有限公司")

    def test_extract_applicant_trims_pct_isa_220c_narrative_tail(self) -> None:
        sample_text = "\n".join(
            [
                "申请人",
                "宁波诺丁汉新材料研究院有限公司",
                "兹通知申请人,国际检索报告和国际检索单位书面意见已经做出并随本通知传送。",
                "按条约第19条提出修改和声明：",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="PCT/ISA/220C|传送国际检索报告和国际检索单位书面意见或宣布的通知书",
            )
        self.assertEqual(result.applicant, "宁波诺丁汉新材料研究院有限公司")

    def test_extract_applicant_normalizes_space_separated_multi_orgs(self) -> None:
        sample_text = "\n".join(
            [
                "复审请求人：西安交通大学 北京微纳精密机械有限公司",
                "审查员：段立彦",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="200905|复审请求受理通知书",
            )
        self.assertEqual(result.applicant, "西安交通大学；北京微纳精密机械有限公司")

    def test_extract_applicant_skips_checkbox_body_noise(self) -> None:
        sample_text = "\n".join(
            [
                "申请人或代理人的档案号 BJ-QSPCT-23022501",
                "✓ 全部规定费用已经缴纳。",
                "申请人：宁波诺丁汉新材料研究院有限公司",
                "发明人：张三",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="PCT/RO/102C|关于缴纳规定费用的通知书",
            )
        self.assertEqual(result.applicant, "宁波诺丁汉新材料研究院有限公司")

    def test_extract_agency_fallback_without_end_anchor(self) -> None:
        sample_text = "\n".join(
            [
                "专利代理机构：杭州君度专利代理事务所（特殊普通合伙）",
                "补充说明一",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertIn("杭州君度专利代理事务所（特殊普通合伙）", result.agency_raw)

    def test_extract_agency_from_header_context_with_wrapped_name(self) -> None:
        sample_text = "\n".join(
            [
                "北京市西城区广安门内大街169号翔达国际商务酒店1623室 北京",
                "北京前审知识产",
                "权代理有限公司 覃婧婵(010-57150818)",
                "发文日：2025年01月24日",
                "申请号或专利号：202122605037.5",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="201004|无效宣告请求受理通知书",
            )
        self.assertEqual(result.agency_raw, "北京前审知识产权代理有限公司")

    def test_extract_agency_strips_generic_name_prefix(self) -> None:
        sample_text = "\n".join(
            [
                "代理机构名称:北京前审知识产权代理有限公司",
                "申请号或专利号：202230755975.0",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertEqual(result.agency_raw, "北京前审知识产权代理有限公司")

    def test_extract_agency_recovers_prefix_from_split_header_fragments(self) -> None:
        sample_text = "\n".join(
            [
                "北京市西城区广安门内大街169号翔达国际商务酒店1623室",
                "北京中",
                "济纬天专利代理有限公司",
                "发文日：2025年01月24日",
                "申请号或专利号：202211197054.2",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertEqual(result.agency_raw, "北京中济纬天专利代理有限公司")

    def test_extract_agency_recovers_special_partnership_split_prefix(self) -> None:
        sample_text = "\n".join(
            [
                "杭州市余杭区文一西路998号海创园18幢507室",
                "杭州君",
                "度专利代理事务所（特殊普通合伙）",
                "发文日：2025年12月03日",
                "申请号：202530286658.2",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertEqual(result.agency_raw, "杭州君度专利代理事务所（特殊普通合伙）")

    def test_extract_agency_does_not_take_ascii_room_suffix_as_prefix(self) -> None:
        sample_text = "\n".join(
            [
                "北京市西城区西直门南大街2号9层2门902A",
                "北京前审知识产权代理有限公司 张波涛,李锋(15001399417)",
                "发文日：2024年08月30日",
                "申请号或专利号：202010298596.3",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="200913|复审案件结案通知书",
            )
        self.assertEqual(result.agency_raw, "北京前审知识产权代理有限公司")

    def test_extract_examiner_skips_body_sentence_uses_strict_label(self) -> None:
        sample_text = "\n".join(
            [
                "对上述申请进行审查，审查员认为该申请不符合专利法相关规定。",
                "审查员：段立彦",
                "审查员电话：18575593139",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="210401|第一次审查意见通知书",
            )
        self.assertEqual(result.examiner, "段立彦")
        self.assertEqual(result.examiner_phone, "18575593139")

    def test_extract_applicant_trims_review_title_fragments(self) -> None:
        sample_text = "\n".join(
            [
                "复审请求人：",
                "西安交通大学",
                "复",
                "审",
                "决",
                "定",
                "书",
                "（第 1860546 号）",
                "合议组组长：刘丽伟",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="200912|复审决定书（首页）",
            )
        self.assertEqual(result.applicant, "西安交通大学")

    def test_extract_applicant_trims_address_and_designer_tail(self) -> None:
        sample_text = "\n".join(
            [
                "专利权人：安徽维电时代科技有限公司",
                "地",
                "址：230088 安徽省合肥市高新区黄山路602号",
                "设",
                "计",
                "人：查晶娟；王晖",
            ]
        )
        with patch("core.official_docs.pdf_entity_extract_v3.fitz.open", return_value=_FakeDoc(sample_text)):
            result = extract_pdf_entity_fields(
                pdf_bytes=b"pdf",
                notice_key="400003|外观设计专利证书",
            )
        self.assertEqual(result.applicant, "安徽维电时代科技有限公司")


if __name__ == "__main__":
    unittest.main()
