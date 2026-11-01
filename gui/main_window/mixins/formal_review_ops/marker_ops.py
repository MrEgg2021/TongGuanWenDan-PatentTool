from __future__ import annotations

from core.user_messages import user_error_text

from .shared import (
    MarkerNormalizationWritePlan,
    Path,
    QMessageBox,
    _SectionSegment,
    apply_write_commands,
    build_marker_normalization_write_plan,
    logger,
    parse_marker_note_map,
    parse_marker_note_payload,
    run_write_preflight,
    show_blocking_alert_modal,
)

__all__ = [
    "_marker_note_map",
    "_description_segments_for_marker_write",
    "_truncate_dialog_text",
    "_build_marker_plan_summary_text",
    "_format_claim_refs",
    "_format_markers_with_mapping",
    "_build_combined_write_plan",
    "on_formal_review_apply_marker_revision_direct",
]

def _marker_note_map(self) -> dict[str, str]:
    marker_edit = getattr(self, "formal_review_marker_edit", None)
    text = str(marker_edit.toPlainText() or "") if marker_edit is not None else ""
    return parse_marker_note_map(text)

def _description_segments_for_marker_write(self) -> list[_SectionSegment]:
    segments = getattr(self, "_formal_review_section_segments", {}) or {}
    rows = list(segments.get("description", []) or [])
    if rows:
        return rows
    document = getattr(self, "_formal_review_document", None)
    text = str(getattr(document, "description", "") or "")
    if not text:
        return []
    return [_SectionSegment("description", None, 0, len(text), 0, raw_text=text)]

def _truncate_dialog_text(value: str, max_len: int = 80) -> str:
    text = str(value or "").replace("\r", "\\r").replace("\n", "\\n")
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}..."

def _build_marker_plan_summary_text(self, plan, *, parser_warnings: list[str], include_warning_lines: int = 6) -> str:
    lines = [
        f"候选命中（权利要求）：{int(getattr(plan, 'candidate_claims', 0) or 0)}",
        f"候选命中（说明书实施段）：{int(getattr(plan, 'candidate_description', 0) or 0)}",
        f"预计新增：{int(getattr(plan, 'inserted_count', 0) or 0)}",
        f"预计替换：{int(getattr(plan, 'replaced_count', 0) or 0)}",
        f"预计跳过（已正确）：{int(getattr(plan, 'skipped_correct_count', 0) or 0)}",
        f"预计跳过（不可定位）：{int(getattr(plan, 'skipped_unsupported_count', 0) or 0)}",
        f"权利要求名称风险跳过：{int(getattr(plan, 'claim_name_unsafe_continue_count', 0) or 0)}",
        f"预计修改项：{int(getattr(plan, 'command_count', 0) or 0)}",
    ]
    warnings = list(parser_warnings or []) + list(getattr(plan, "warnings", []) or [])
    if warnings:
        lines.append("")
        lines.append("警告：")
        for row in warnings[: max(0, int(include_warning_lines))]:
            lines.append(f"- {user_error_text(str(row))}")
        if len(warnings) > int(include_warning_lines):
            lines.append(f"- ... 其余 {len(warnings) - int(include_warning_lines)} 条未显示")
    return "\n".join(lines)


def _build_marker_apply_compact_summary(report) -> str:
    return "\n".join(
        [
            f"计划修改项：{int(getattr(report, 'planned_count', 0) or 0)}",
            f"实际应用：{int(getattr(report, 'applied_count', 0) or 0)}",
            f"新增：{int(getattr(report, 'inserted_count', 0) or 0)}",
            f"替换：{int(getattr(report, 'replaced_count', 0) or 0)}",
            f"失败：{int(getattr(report, 'failed_count', 0) or 0)}",
        ]
    )


def _build_marker_apply_detail_text(plan, report) -> str:
    lines = [
        _build_marker_apply_compact_summary(report),
        "",
        f"权利要求 strict定位失败：{int(getattr(plan, 'claim_resolve_strict_failed_count', 0) or 0)}",
        f"权利要求 loose救援成功：{int(getattr(plan, 'claim_resolve_loose_rescued_count', 0) or 0)}",
        f"权利要求定位路径 projection：{int(getattr(plan, 'claim_resolve_projection_count', 0) or 0)}",
        f"权利要求定位路径 word_find_com：{int(getattr(plan, 'claim_resolve_word_find_com_count', 0) or 0)}",
        f"权利要求定位路径 word_find_legacy：{int(getattr(plan, 'claim_resolve_word_find_legacy_count', 0) or 0)}",
        f"权利要求名称精确校验失败：{int(getattr(plan, 'claim_name_exact_check_failed_count', 0) or 0)}",
        f"权利要求名称邻域救援成功：{int(getattr(plan, 'claim_name_nearby_rescued_count', 0) or 0)}",
        f"权利要求名称风险跳过：{int(getattr(plan, 'claim_name_unsafe_continue_count', 0) or 0)}",
    ]
    failed_cmd_ids = list(getattr(report, "failed_cmd_ids", []) or [])
    if failed_cmd_ids:
        lines.extend(["", "失败命令样本："])
        lines.extend([f"- {row}" for row in failed_cmd_ids[:8]])
        if len(failed_cmd_ids) > 8:
            lines.append(f"- ... 其余 {len(failed_cmd_ids) - 8} 条未显示")
    warnings = [str(row) for row in list(getattr(report, "warnings", []) or []) if str(row).strip()]
    if warnings:
        lines.extend(["", "执行警告："])
        lines.extend([f"- {row}" for row in warnings[:10]])
        if len(warnings) > 10:
            lines.append(f"- ... 其余 {len(warnings) - 10} 条未显示")
    errors = [str(row) for row in list(getattr(report, "errors", []) or []) if str(row).strip()]
    if errors:
        lines.extend(["", "执行错误："])
        lines.extend([f"- {row}" for row in errors[:10]])
        if len(errors) > 10:
            lines.append(f"- ... 其余 {len(errors) - 10} 条未显示")
    return "\n".join(lines)


def _show_marker_apply_result_dialog(
    self,
    *,
    title: str,
    headline: str,
    summary_text: str,
    detail_text: str,
    icon: QMessageBox.Icon,
) -> None:
    box = QMessageBox(self)
    box.setWindowTitle(str(title or "处理结果"))
    box.setIcon(icon)
    box.setText(str(headline or "处理完成。"))
    box.setInformativeText(str(summary_text or ""))
    detail_btn = box.addButton("技术详情", QMessageBox.ActionRole)
    ok_btn = box.addButton("确定", QMessageBox.AcceptRole)
    box.setDefaultButton(ok_btn)
    box.exec()
    if box.clickedButton() is detail_btn:
        QMessageBox.information(self, f"{title} - 技术详情", str(detail_text or "无更多详情。"))

def _format_claim_refs(refs: list[int] | None) -> str:
    values = [int(value) for value in list(refs or [])]
    if not values:
        return "无"
    return "权" + "/".join(str(value) for value in values)

def _format_markers_with_mapping(markers: list[str] | None, marker_map: dict[str, str]) -> str:
    values = [str(value) for value in list(markers or [])]
    if not values:
        return "无"
    rows: list[str] = []
    for marker in values:
        name = str(marker_map.get(marker) or "").strip()
        if name:
            rows.append(f"{marker}({name})")
        else:
            rows.append(f"{marker}(未在标号说明中定义)")
    return "、".join(rows)

def _build_combined_write_plan(self) -> tuple[MarkerNormalizationWritePlan, bool]:
    plan = MarkerNormalizationWritePlan()
    document = getattr(self, "_formal_review_document", None)
    if document is None:
        plan.errors.append("文档尚未解析，无法生成修订计划。")
        return plan, False
    marker_edit = getattr(self, "formal_review_marker_edit", None)
    marker_text = str(marker_edit.toPlainText() or "") if marker_edit is not None else ""
    parser_warnings: list[str] = []
    scope_missing = False
    if marker_text.strip():
        parsed = parse_marker_note_payload(marker_text)
        parser_warnings.extend(list(parsed.warnings or []))
        if parsed.errors:
            plan.errors.extend(list(parsed.errors or []))
        if parsed.name_to_marker:
            marker_plan = build_marker_normalization_write_plan(
                document=document,
                name_to_marker=dict(parsed.name_to_marker),
                description_segments=self._description_segments_for_marker_write(),
                doc=getattr(getattr(self, "_formal_review_companion_session", None), "doc", None)
                if str(getattr(self, "_formal_review_input_mode", "word") or "word") == "word"
                else None,
                projections=getattr(self, "_formal_review_projections", None)
                if str(getattr(self, "_formal_review_input_mode", "word") or "word") == "word"
                else None,
            )
            scope_missing = not bool(getattr(marker_plan, "description_scope_found", True))
            if scope_missing:
                plan.warnings.extend(list(getattr(marker_plan, "errors", []) or []))
            else:
                plan.errors.extend(list(getattr(marker_plan, "errors", []) or []))
            plan.warnings.extend(list(getattr(marker_plan, "warnings", []) or []))
            plan.candidate_claims += int(getattr(marker_plan, "candidate_claims", 0) or 0)
            plan.candidate_description += int(getattr(marker_plan, "candidate_description", 0) or 0)
            plan.inserted_count += int(getattr(marker_plan, "inserted_count", 0) or 0)
            plan.replaced_count += int(getattr(marker_plan, "replaced_count", 0) or 0)
            plan.skipped_correct_count += int(getattr(marker_plan, "skipped_correct_count", 0) or 0)
            plan.skipped_unsupported_count += int(getattr(marker_plan, "skipped_unsupported_count", 0) or 0)
            plan.claim_resolve_strict_failed_count += int(
                getattr(marker_plan, "claim_resolve_strict_failed_count", 0) or 0
            )
            plan.claim_resolve_loose_rescued_count += int(
                getattr(marker_plan, "claim_resolve_loose_rescued_count", 0) or 0
            )
            plan.claim_resolve_projection_count += int(
                getattr(marker_plan, "claim_resolve_projection_count", 0) or 0
            )
            plan.claim_resolve_word_find_com_count += int(
                getattr(marker_plan, "claim_resolve_word_find_com_count", 0) or 0
            )
            plan.claim_resolve_word_find_legacy_count += int(
                getattr(marker_plan, "claim_resolve_word_find_legacy_count", 0) or 0
            )
            plan.claim_name_exact_check_failed_count += int(
                getattr(marker_plan, "claim_name_exact_check_failed_count", 0) or 0
            )
            plan.claim_name_nearby_rescued_count += int(
                getattr(marker_plan, "claim_name_nearby_rescued_count", 0) or 0
            )
            plan.claim_name_unsafe_continue_count += int(
                getattr(marker_plan, "claim_name_unsafe_continue_count", 0) or 0
            )
            plan.commands.extend(list(getattr(marker_plan, "commands", []) or []))
        else:
            parser_warnings.append("标号说明未解析出有效映射，无法生成附图标记修订。")
    else:
        parser_warnings.append("标号说明为空，无法生成附图标记修订。")
    plan.warnings.extend(parser_warnings)
    plan.commands.sort(key=lambda item: int(getattr(item, "word_start", 0) or 0), reverse=True)
    return plan, scope_missing

def on_formal_review_apply_marker_revision_direct(self):
    self._ensure_formal_review_state()
    if str(getattr(self, "_formal_review_input_mode", "word") or "word") != "word":
        QMessageBox.information(self, "形式审查", "仅 Word 模式支持附图标记修订。")
        return
    session = getattr(self, "_formal_review_companion_session", None)
    if session is None:
        QMessageBox.information(self, "形式审查", "请先连接 Word 文档。")
        return
    if not self._ensure_com_find_ready_or_prompt(context="marker_apply_direct"):
        return
    if bool(getattr(self, "_formal_review_busy", False)):
        QMessageBox.information(self, "形式审查", "当前任务正在执行，请稍后重试。")
        return
    current_file = str(getattr(self, "_formal_review_current_file", "") or "")
    overlay_file = Path(current_file).name if current_file else ""
    overlay_title = "正在以修订模式生成附图标记，请不要进行其他操作，请稍等。"
    analysis_overlay_visible = self._show_formal_review_overlay(overlay_title, overlay_file)
    self._update_formal_review_overlay(10, "正在准备分析环境，请稍等。", overlay_file)
    try:
        if not list(getattr(self, "_formal_review_issues", []) or []):
            self._run_review_on_current_document()
        self._update_formal_review_overlay(35, "正在解析标号说明并生成修订计划，请稍等。", overlay_file)
        plan, scope_missing = self._build_combined_write_plan()
        self._update_formal_review_overlay(70, "正在校验应用范围，请稍等。", overlay_file)
        self._update_formal_review_overlay(100, "分析完成，等待确认。", overlay_file)
    finally:
        self._hide_formal_review_overlay(analysis_overlay_visible)

    if scope_missing:
        if not self._ask_continue_cancel_cn(
            "说明书范围提示",
            "未在说明书中定位到“具体实施方式/具体实施例”标题。是否仅对权利要求部分应用附图标记修订？",
            default_continue=False,
        ):
            return

    if list(getattr(plan, "errors", []) or []):
        errors = [str(row) for row in list(getattr(plan, "errors", []) or [])]
        show_blocking_alert_modal(self, "附图标记修订失败", "无法生成修订计划：\n" + "\n".join(f"- {row}" for row in errors))
        return
    if int(getattr(plan, "command_count", 0) or 0) <= 0:
        summary = _build_marker_plan_summary_text(self, plan, parser_warnings=[], include_warning_lines=10)
        QMessageBox.information(
            self,
            "附图标记修订",
            "未找到可应用的修改。\n\n" + str(summary or ""),
        )
        return

    if not self._ask_continue_cancel_cn(
        "应用附图标记修订",
        (
            "将直接在当前 Word 文档中应用附图标记修订，并开启修订模式。\n"
            "修改前会核对原文，可能部分完成；结果会显示完成和失败数量。\n"
            f"计划修改项：{int(getattr(plan, 'command_count', 0) or 0)}\n\n"
            "是否继续？"
        ),
        default_continue=False,
    ):
        return

    overlay_visible = self._show_formal_review_overlay(overlay_title, overlay_file)
    self._update_formal_review_overlay(8, overlay_title, overlay_file)
    self._formal_review_busy = True
    self._set_formal_review_busy(True, action="正在应用附图标记修订...")
    try:
        self._update_formal_review_overlay(40, "正在执行修订预检，请稍等。", overlay_file)
        preflight = run_write_preflight(session.doc, list(getattr(plan, "commands", []) or []))
        if not bool(getattr(preflight, "passed", False)):
            rows = []
            for item in list(getattr(preflight, "failures", []) or [])[:20]:
                rows.append(
                    f"- 修改内容核对未通过：{user_error_text(str(item.reason))}；预计原文：{self._truncate_dialog_text(item.expected)}；当前原文：{self._truncate_dialog_text(item.actual)}"
                )
            if int(len(getattr(preflight, "failures", []) or [])) > 20:
                rows.append(f"- ... 另有 {len(preflight.failures) - 20} 条失败")
            if not self._ask_continue_cancel_cn(
                "预检风险提示",
                "写入预检未通过。\n"
                f"已检查修改项：{int(getattr(preflight, 'checked_count', 0) or 0)}\n\n"
                + "\n".join(rows)
                + "\n\n是否继续修改（仅跳过未通过检查的项目）？",
                default_continue=False,
            ):
                self._set_status_text("形式审查：已取消提交（预检存在风险）。")
                return
        self._update_formal_review_overlay(76, "正在应用修订，请稍等。", overlay_file)
        report = apply_write_commands(
            session.doc,
            commands=list(getattr(plan, "commands", []) or []),
            enforce_track_revisions=True,
            atomic_commit=False,
        )
        self._update_formal_review_overlay(100, "附图标记修订已完成。", overlay_file)
    finally:
        self._formal_review_busy = False
        self._set_formal_review_busy(False)
        self._hide_formal_review_overlay(overlay_visible)

    applied_count = int(getattr(report, "applied_count", 0) or 0)
    failed_count = int(getattr(report, "failed_count", 0) or 0)
    failed_cmd_ids = list(getattr(report, "failed_cmd_ids", []) or [])
    logger.info(
        "[formal_review][marker_apply] direct_done planned=%s applied=%s failed=%s failed_sample=%s",
        int(getattr(report, "planned_count", 0) or 0),
        applied_count,
        failed_count,
        ",".join([str(item) for item in failed_cmd_ids[:5]]) if failed_cmd_ids else "",
    )

    if not bool(getattr(report, "committed", False)) and applied_count <= 0:
        detail_text = _build_marker_apply_detail_text(plan, report)
        summary_text = _build_marker_apply_compact_summary(report)
        _show_marker_apply_result_dialog(
            self,
            title="附图标记修订结果",
            headline="附图标记修订提交失败（未修改文档）。",
            summary_text=summary_text,
            detail_text=detail_text,
            icon=QMessageBox.Critical,
        )
        self._set_status_text("形式审查：附图标记修订失败（未修改文档）。")
        return

    summary = _build_marker_apply_compact_summary(report)
    detail = _build_marker_apply_detail_text(plan, report)
    tip_line = "提示：如需重新审查/刷新，请先在 Word 中接受所有修订、删除全部批注、关闭修订并保存，然后再点击开始审查。"

    if failed_count > 0:
        _show_marker_apply_result_dialog(
            self,
            title="附图标记修订结果",
            headline="附图标记修订已部分提交到 Word（无法完成的修改已跳过）。",
            summary_text=f"{summary}\n\n{tip_line}",
            detail_text=detail,
            icon=QMessageBox.Warning,
        )
        self._set_status_text(f"形式审查：附图标记修订部分成功（成功{applied_count}，失败{failed_count}）。")
    else:
        _show_marker_apply_result_dialog(
            self,
            title="附图标记修订结果",
            headline="附图标记修订已提交到 Word。",
            summary_text=f"{summary}\n\n{tip_line}",
            detail_text=detail,
            icon=QMessageBox.Information,
        )
        self._set_status_text("形式审查：已提交修订。提示：重审前需清理批注/修订并保存。")