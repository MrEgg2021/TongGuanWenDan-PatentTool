from __future__ import annotations

from .shared import (
    Issue,
    QColor,
    QFontMetrics,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSignalBlocker,
    QSize,
    QSizePolicy,
    QTableWidgetItem,
    QTextCharFormat,
    QTextCursor,
    QTextEdit,
    QTextFormat,
    QTimer,
    QTreeWidgetItem,
    QWidget,
    Qt,
    RULE_REGISTRY,
    _CLAIM_BODY_HEIGHT_PADDING,
    _CLAIM_BODY_MAX_HEIGHT,
    _CLAIM_BODY_MIN_HEIGHT,
    _CLAIM_HEADER_FONT_SIZE,
    _CLAIM_MARKER_HEIGHT_PADDING,
    _CLAIM_MARKER_HORIZONTAL_PADDING,
    _CONTEXT_RADIUS,
    _DEFAULT_HIGHLIGHT_COLORS,
    _RESULTS_TREE_COLUMN_WIDTHS_PREF_KEY,
    _RESULTS_TREE_DEFAULT_WIDTHS,
    _RESULTS_TREE_MIN_WIDTH,
    _SEVERITY_LABELS,
    _WIDGET_SIZE_MAX,
    _issue_group_label,
    _issue_group_label_compact_for_list,
    _issue_location_compact_for_list,
    _issue_location_text,
    _issue_matches_editor,
    _issue_reason_compact,
    _issue_type_key,
    _safe_int,
    build_instance_fingerprint,
    count_effective_chars,
    get_pref,
    html,
    locate_issue_in_word,
    logger,
    set_pref,
)

__all__ = [
    "_issue_context_triplet",
    "_issue_fingerprint",
    "_apply_ignore_state",
    "_set_claims_source_text_from_document",
    "_on_formal_review_workspace_splitter_moved",
    "_schedule_results_tree_layout_refresh",
    "_results_tree_mode_key",
    "_load_results_tree_column_widths_pref",
    "_persist_current_results_tree_column_widths",
    "_restore_results_tree_column_widths",
    "_on_results_tree_section_resized",
    "_apply_results_tree_row_heights",
    "_refresh_results_tree_layout",
    "_schedule_claims_dynamic_layout",
    "_update_claim_body_height",
    "_update_claim_marker_height",
    "_refresh_claims_dynamic_layout",
    "_render_claims_tree",
    "_update_abstract_count_label",
    "_formal_review_fill_claims_table",
    "_populate_document_views",
    "_issue_color",
    "_apply_highlights",
    "_refresh_highlights",
    "_focus_issue",
    "_expand_claim_tree_for_focus",
    "_get_issue_by_id",
    "_issues_for_editor",
    "_section_text_for_issue",
    "_sync_issue_detail_panel",
    "_populate_summary_views",
    "_render_issue_views",
    "_reset_issue_views",
    "_locate_issue",
    "_schedule_companion_comment_resync",
    "_toggle_issue_ignore",
    "on_formal_review_summary_item_clicked",
    "on_formal_review_summary_tree_item_changed",
    "on_formal_review_issue_toggle_changed",
    "on_formal_review_claim_tree_item_clicked",
    "on_formal_review_tab_changed",
    "on_formal_review_summary_table_cell_clicked",
    "on_formal_review_issue_table_cell_clicked",
    "on_formal_review_claim_row_clicked",
]

def _issue_context_triplet(self, issue: Issue, *, radius: int = 16) -> tuple[str, str, str]:
    source = self._section_text_for_issue(issue)
    if not source:
        return "", str(getattr(issue, "snippet", "") or ""), ""
    start = _safe_int(getattr(issue, "span_start", None), None)
    end = _safe_int(getattr(issue, "span_end", None), None)
    if start is None:
        return "", str(getattr(issue, "snippet", "") or ""), ""
    start = max(0, min(int(start), len(source)))
    if end is None:
        end = start
    end = max(start, min(int(end), len(source)))
    pre = source[max(0, start - max(1, int(radius))) : start]
    hit = source[start:end] if end > start else str(getattr(issue, "snippet", "") or "")
    post = source[end : min(len(source), end + max(1, int(radius)))]
    return pre, hit, post

def _issue_fingerprint(self, issue: Issue) -> str:
    pre, hit, post = self._issue_context_triplet(issue)
    return build_instance_fingerprint(
        rule_id=str(getattr(issue, "rule_id", "") or ""),
        section=str(getattr(issue, "section", "") or ""),
        claim_num=_safe_int(getattr(issue, "claim_num", None), None),
        pre_context=pre,
        snippet=hit,
        post_context=post,
    )

def _apply_ignore_state(self, issues: list[Issue]) -> None:
    ignore_enabled = self._ignore_enabled()
    store = getattr(self, "_formal_review_suppression_store", None) if ignore_enabled else None
    fingerprints: dict[str, str] = {}
    for issue in issues:
        if not ignore_enabled:
            issue.ignored = False
            continue
        fp = self._issue_fingerprint(issue)
        issue_key = str(getattr(issue, "issue_id", "") or "")
        if issue_key:
            fingerprints[issue_key] = fp
        issue.ignored = bool(store and store.is_suppressed(issue, fp))
    self._formal_review_issue_fingerprints = fingerprints if ignore_enabled else {}

def _set_claims_source_text_from_document(self) -> None:
    editor = getattr(self, "formal_review_claims_input_text", None)
    document = getattr(self, "_formal_review_document", None)
    if editor is None:
        return
    claims = list(getattr(document, "claims", []) or [])
    rows: list[str] = []
    for claim in claims:
        claim_num = int(claim.num)
        claim_text = self._segment_text(f"claims:{claim_num}", fallback=str(claim.text or "").strip())
        rows.append(f"{claim_num}、{claim_text}")
    editor.setPlainText("\n".join(rows))

def _on_formal_review_workspace_splitter_moved(self, *_args) -> None:
    self._refresh_results_tree_layout()
    self._schedule_results_tree_layout_refresh()
    self._schedule_claims_dynamic_layout()

def _schedule_results_tree_layout_refresh(self) -> None:
    if bool(getattr(self, "_formal_review_results_layout_refresh_pending", False)):
        return
    self._formal_review_results_layout_refresh_pending = True

    def _run() -> None:
        self._formal_review_results_layout_refresh_pending = False
        self._refresh_results_tree_layout()

    QTimer.singleShot(0, _run)


def _results_tree_mode_key(self) -> str:
    return "plain_text" if bool(self._ignore_enabled()) else "word"


def _load_results_tree_column_widths_pref(self) -> dict[str, list[int]]:
    payload = get_pref(_RESULTS_TREE_COLUMN_WIDTHS_PREF_KEY, {})
    defaults = [int(value) for value in _RESULTS_TREE_DEFAULT_WIDTHS]
    normalized: dict[str, list[int]] = {"plain_text": list(defaults), "word": list(defaults)}
    if isinstance(payload, dict):
        for mode in ("plain_text", "word"):
            raw = payload.get(mode)
            if not isinstance(raw, (list, tuple)) or len(raw) < 4:
                continue
            row: list[int] = []
            for idx, default in enumerate(defaults):
                value = _safe_int(raw[idx], default)
                row.append(max(int(_RESULTS_TREE_MIN_WIDTH), int(value if value is not None else default)))
            normalized[mode] = row
    if payload != normalized:
        set_pref(_RESULTS_TREE_COLUMN_WIDTHS_PREF_KEY, normalized)
    return normalized


def _current_results_tree_column_widths(self) -> list[int]:
    tree = getattr(self, "formal_review_results_tree", None)
    defaults = [int(value) for value in _RESULTS_TREE_DEFAULT_WIDTHS]
    if tree is None:
        return list(defaults)
    widths: list[int] = []
    for index, default in enumerate(defaults):
        value = _safe_int(tree.columnWidth(int(index)), default)
        widths.append(max(int(_RESULTS_TREE_MIN_WIDTH), int(value if value is not None else default)))
    return widths


def _persist_current_results_tree_column_widths(self) -> None:
    tree = getattr(self, "formal_review_results_tree", None)
    if tree is None:
        return
    mode = self._results_tree_mode_key()
    widths = self._current_results_tree_column_widths()
    payload = getattr(self, "_formal_review_results_tree_column_widths_by_mode", None)
    if not isinstance(payload, dict):
        payload = self._load_results_tree_column_widths_pref()
    payload = dict(payload or {})
    previous = list(payload.get(mode) or [])
    if len(previous) >= 4 and previous[:4] == widths[:4]:
        return
    payload[mode] = list(widths)
    self._formal_review_results_tree_column_widths_by_mode = dict(payload)
    set_pref(_RESULTS_TREE_COLUMN_WIDTHS_PREF_KEY, dict(payload))


def _restore_results_tree_column_widths(self, *, force: bool = False) -> None:
    tree = getattr(self, "formal_review_results_tree", None)
    if tree is None:
        return
    mode = self._results_tree_mode_key()
    applied_mode = str(getattr(self, "_formal_review_results_tree_width_mode_applied", "") or "")
    if (not force) and applied_mode == mode:
        return
    payload = getattr(self, "_formal_review_results_tree_column_widths_by_mode", None)
    if not isinstance(payload, dict):
        payload = self._load_results_tree_column_widths_pref()
    defaults = [int(value) for value in _RESULTS_TREE_DEFAULT_WIDTHS]
    target = list((payload or {}).get(mode) or defaults)
    if len(target) < 4:
        target = list(defaults)
    self._formal_review_results_tree_restoring_widths = True
    try:
        for index in range(4):
            value = _safe_int(target[index], defaults[index])
            tree.setColumnWidth(
                int(index),
                max(int(_RESULTS_TREE_MIN_WIDTH), int(value if value is not None else defaults[index])),
            )
    finally:
        self._formal_review_results_tree_restoring_widths = False
    self._formal_review_results_tree_width_mode_applied = mode


def _on_results_tree_section_resized(self, *_args) -> None:
    tree = getattr(self, "formal_review_results_tree", None)
    if tree is None:
        return
    if bool(getattr(self, "_formal_review_results_tree_restoring_widths", False)):
        return
    self._apply_results_tree_row_heights(tree)
    try:
        tree.doItemsLayout()
    except Exception:
        pass
    if bool(getattr(self, "_formal_review_results_tree_width_save_pending", False)):
        return
    self._formal_review_results_tree_width_save_pending = True

    def _run() -> None:
        self._formal_review_results_tree_width_save_pending = False
        self._persist_current_results_tree_column_widths()

    QTimer.singleShot(120, _run)


def _apply_results_tree_row_heights(self, tree) -> None:
    if tree is None:
        return
    reason_width = max(1, int(tree.columnWidth(2) or 0) - 8)
    if reason_width <= 1:
        return
    metrics = QFontMetrics(tree.font())
    default_height = max(24, int(metrics.height()) + 8)

    def _row_height(text: str) -> int:
        content = str(text or "").strip()
        if not content:
            return default_height
        wrapped = metrics.boundingRect(0, 0, reason_width, 0, int(Qt.TextFlag.TextWordWrap), content)
        return max(default_height, int(wrapped.height()) + 10)

    for index in range(tree.topLevelItemCount()):
        root = tree.topLevelItem(index)
        if root is None:
            continue
        root_height = _row_height(str(root.text(0) or ""))
        for col in range(tree.columnCount()):
            root.setSizeHint(col, QSize(0, root_height))
        for child_index in range(root.childCount()):
            child = root.child(child_index)
            if child is None:
                continue
            child_height = _row_height(str(child.text(2) or ""))
            for col in range(tree.columnCount()):
                child.setSizeHint(col, QSize(0, child_height))


def _refresh_results_tree_layout(self) -> None:
    tree = getattr(self, "formal_review_results_tree", None)
    if tree is None:
        return
    try:
        header = tree.header()
        if header is None:
            return
        ignore_enabled = bool(self._ignore_enabled())
        hide_ignore_column = bool(not ignore_enabled)
        if bool(tree.isColumnHidden(3)) != hide_ignore_column:
            tree.setColumnHidden(3, hide_ignore_column)
        tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        self._restore_results_tree_column_widths()
        viewport_width = max(0, int(tree.viewport().width() or 0))
        visible_cols = [idx for idx in range(4) if not bool(tree.isColumnHidden(idx))]
        visible_total = sum(max(0, int(tree.columnWidth(idx) or 0)) for idx in visible_cols)
        spare = int(viewport_width - visible_total)
        if spare > 0 and 2 in visible_cols:
            self._formal_review_results_tree_restoring_widths = True
            try:
                tree.setColumnWidth(2, max(int(_RESULTS_TREE_MIN_WIDTH), int(tree.columnWidth(2) or 0) + int(spare)))
            finally:
                self._formal_review_results_tree_restoring_widths = False
        self._apply_results_tree_row_heights(tree)
        tree.doItemsLayout()
    except Exception:
        pass

def _schedule_claims_dynamic_layout(self, *_args) -> None:
    if bool(getattr(self, "_formal_review_claim_layout_refresh_pending", False)):
        return
    self._formal_review_claim_layout_refresh_pending = True
    QTimer.singleShot(0, self._refresh_claims_dynamic_layout)

def _update_claim_body_height(self, editor: QTextEdit) -> None:
    viewport_width = max(1, int(editor.viewport().width() or 0))
    if viewport_width <= 1:
        return
    document = editor.document()
    document.setTextWidth(float(viewport_width))
    doc_layout = document.documentLayout()
    if doc_layout is None:
        return
    content_height = int(doc_layout.documentSize().height()) + _CLAIM_BODY_HEIGHT_PADDING
    target_height = max(_CLAIM_BODY_MIN_HEIGHT, min(_CLAIM_BODY_MAX_HEIGHT, content_height))
    needs_scroll = content_height > _CLAIM_BODY_MAX_HEIGHT
    editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if needs_scroll else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    if int(editor.minimumHeight()) != target_height or int(editor.maximumHeight()) != target_height:
        editor.setMinimumHeight(target_height)
        editor.setMaximumHeight(target_height)

def _update_claim_marker_height(self, tree, row: dict[str, object]) -> None:
    marker_item = row.get("item")
    container = row.get("container")
    label = row.get("label")
    if marker_item is None or container is None or label is None:
        return
    if not isinstance(label, QLabel):
        return

    marker_rect = tree.visualItemRect(marker_item)
    available_width = int(marker_rect.width() or 0) - _CLAIM_MARKER_HORIZONTAL_PADDING
    if available_width <= 0:
        available_width = int(tree.viewport().width() or 0) - _CLAIM_MARKER_HORIZONTAL_PADDING
    if available_width <= 0:
        return

    label.setMinimumHeight(0)
    label.setMaximumHeight(_WIDGET_SIZE_MAX)
    if hasattr(container, "setMinimumHeight"):
        container.setMinimumHeight(0)
    if hasattr(container, "setMaximumHeight"):
        container.setMaximumHeight(_WIDGET_SIZE_MAX)

    metrics = QFontMetrics(label.font())
    wrapped_rect = metrics.boundingRect(0, 0, available_width, 0, int(Qt.TextFlag.TextWordWrap), str(label.text() or ""))
    content_height = max(24, int(wrapped_rect.height() or 0))
    target_height = int(content_height + _CLAIM_MARKER_HEIGHT_PADDING + 12)
    label.setFixedHeight(target_height)
    if hasattr(container, "setFixedHeight"):
        container.setFixedHeight(target_height)

def _refresh_claims_dynamic_layout(self) -> None:
    self._formal_review_claim_layout_refresh_pending = False
    tree = getattr(self, "formal_review_claims_tree", None)
    if tree is None:
        return
    for editor in list((getattr(self, "_formal_review_claim_content_views", {}) or {}).values()):
        if editor is None:
            continue
        self._update_claim_body_height(editor)
    for row in list((getattr(self, "_formal_review_claim_marker_rows", {}) or {}).values()):
        if row is None:
            continue
        self._update_claim_marker_height(tree, row)
    try:
        tree.doItemsLayout()
    except Exception:
        pass

def _render_claims_tree(self) -> None:
    tree = getattr(self, "formal_review_claims_tree", None)
    document = getattr(self, "_formal_review_document", None)
    if tree is None:
        return
    tree.clear()
    self._formal_review_claim_content_views = {}
    self._formal_review_claim_marker_labels = {}
    self._formal_review_claim_marker_rows = {}
    if document is None:
        return
    marker_map = self._marker_note_map()
    claims = list(getattr(document, "claims", []) or [])
    for claim in claims:
        claim_num = int(claim.num)
        refs_text = self._format_claim_refs(getattr(claim, "refs", None))
        base_title = f"权利要求{claim_num}    字数：{claim.word_count}    引用前述：{refs_text}"
        root = QTreeWidgetItem([base_title])
        root_font = root.font(0)
        root_font.setPointSize(max(int(root_font.pointSize() or 12), _CLAIM_HEADER_FONT_SIZE))
        root_font.setBold(True)
        root.setFont(0, root_font)
        root.setForeground(0, QColor("#0F172A"))
        root.setData(0, Qt.UserRole, f"claim:{claim_num}")
        root.setData(0, Qt.UserRole + 2, base_title)
        tree.addTopLevelItem(root)
        content_item = QTreeWidgetItem([""])
        content_item.setData(0, Qt.UserRole, f"claim_content:{claim_num}")
        root.addChild(content_item)
        content_editor = QTextEdit()
        content_editor.setObjectName("FormalReviewClaimBodyView")
        content_editor.setAcceptRichText(False)
        content_editor.setReadOnly(not self._is_word_mode_editable())
        content_editor.setPlainText(self._segment_text(f"claims:{claim_num}", fallback=str(claim.text or "")))
        content_editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        content_editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content_editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        try:
            content_editor.document().setDocumentMargin(0)
        except Exception:
            pass
        try:
            content_editor.textChanged.connect(lambda num=claim_num: self._on_formal_review_claim_text_edited(num))
        except Exception:
            pass
        tree.setItemWidget(content_item, 0, content_editor)
        self._formal_review_claim_content_views[claim_num] = content_editor

        markers_text = self._format_markers_with_mapping(getattr(claim, "markers", None), marker_map)
        marker_item = QTreeWidgetItem([""])
        marker_item.setData(0, Qt.UserRole, f"claim_markers:{claim_num}")
        root.addChild(marker_item)
        marker_container = QWidget()
        marker_layout = QHBoxLayout(marker_container)
        marker_layout.setContentsMargins(0, 0, 0, 0)
        marker_layout.setSpacing(0)
        marker_label = QLabel(f"附图标记：{markers_text}")
        marker_label.setObjectName("FormalReviewClaimMarkerLabel")
        marker_label.setWordWrap(True)
        marker_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        marker_layout.addWidget(marker_label, 1)
        tree.setItemWidget(marker_item, 0, marker_container)
        self._formal_review_claim_marker_labels[claim_num] = marker_label
        self._formal_review_claim_marker_rows[claim_num] = {
            "item": marker_item,
            "container": marker_container,
            "label": marker_label,
        }
        root.setExpanded(True)
    if claims:
        self._formal_review_selected_claim_num = int(claims[0].num)
    self._schedule_claims_dynamic_layout()

def _update_abstract_count_label(self) -> None:
    label = getattr(self, "formal_review_abstract_count_label", None)
    if label is None:
        return
    editor = getattr(self, "formal_review_abstract_text", None)
    source_text = str(editor.toPlainText() or "") if editor is not None else ""
    count = int(count_effective_chars(source_text))
    threshold = 300
    over_limit = count > threshold
    state_text = "超限" if over_limit else "合规"
    label.setText(f"摘要字数：{count}/{threshold}（{state_text}）")
    label.setProperty("overLimit", over_limit)
    try:
        style = label.style()
        if style is not None:
            style.unpolish(label)
            style.polish(label)
    except Exception:
        pass

def _formal_review_fill_claims_table(self) -> None:
    table = getattr(self, "formal_review_claims_table", None)
    document = getattr(self, "_formal_review_document", None)
    if table is None:
        return
    claims = list(getattr(document, "claims", []) or [])
    table.setRowCount(len(claims))
    for row, claim in enumerate(claims):
        cells = [str(claim.num), str(claim.word_count), "、".join(claim.markers or [])]
        for col, value in enumerate(cells):
            item = QTableWidgetItem(value)
            item.setFlags((item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled) & ~Qt.ItemIsEditable)
            table.setItem(row, col, item)

def _populate_document_views(self) -> None:
    document = getattr(self, "_formal_review_document", None)
    if document is None:
        self._clear_document_views()
        return
    self._formal_review_syncing_ui = True
    try:
        for attr, key in (
            ("formal_review_description_text", "description"),
            ("formal_review_abstract_text", "abstract"),
            ("formal_review_drawings_text", "drawings"),
        ):
            editor = getattr(self, attr, None)
            if editor is not None:
                editor.setPlainText(self._segment_text(f"{key}:0", fallback=str(getattr(document, key, "") or "")))
        self._set_claims_source_text_from_document()
        self._formal_review_fill_claims_table()
        self._render_claims_tree()
        self._update_abstract_count_label()
    finally:
        self._formal_review_syncing_ui = False
    self._refresh_results_tree_layout()

def _issue_color(self, issue: Issue) -> str:
    colors = dict(getattr(self, "_formal_review_highlight_colors", {}) or {})
    rule_id = str(issue.rule_id or "")
    registry_row = RULE_REGISTRY.get(rule_id) if isinstance(RULE_REGISTRY, dict) else None
    color_key = str((registry_row or {}).get("color_key") or _issue_type_key(issue))
    return (
        colors.get(rule_id)
        or colors.get(color_key)
        or colors.get(_issue_type_key(issue))
        or colors.get("default")
        or _DEFAULT_HIGHLIGHT_COLORS["default"]
    )

def _apply_highlights(
    self,
    editor,
    issues: list[Issue],
    selected_issue_id: str = "",
    *,
    section: str,
    claim_num: int | None = None,
) -> None:
    if editor is None:
        return
    text_len = len(editor.toPlainText())
    selections: list[QTextEdit.ExtraSelection] = []
    for issue in issues:
        start = _safe_int(issue.span_start, None)
        end = _safe_int(issue.span_end, None)
        if start is None or end is None:
            continue
        start = max(0, min(int(start), text_len))
        end = max(start, min(int(end), text_len))
        if end <= start:
            continue
        selection = QTextEdit.ExtraSelection()
        cursor = editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        selection.cursor = cursor
        selection.format.setBackground(QColor(self._issue_color(issue)))
        selection.format.setProperty(QTextFormat.FullWidthSelection, False)
        selections.append(selection)
    if selected_issue_id:
        selected_issue = self._get_issue_by_id(selected_issue_id)
        if (
            selected_issue is not None
            and not selected_issue.ignored
            and _issue_matches_editor(selected_issue, section=section, claim_num=claim_num)
        ):
            start = _safe_int(selected_issue.span_start, None)
            end = _safe_int(selected_issue.span_end, None)
            if start is not None and end is not None:
                start = max(0, min(int(start), text_len))
                end = max(start, min(int(end), text_len))
                if end > start:
                    overlay = QTextEdit.ExtraSelection()
                    cursor = editor.textCursor()
                    cursor.setPosition(start)
                    cursor.setPosition(end, QTextCursor.KeepAnchor)
                    overlay.cursor = cursor
                    selected_color = (getattr(self, "_formal_review_highlight_colors", {}) or {}).get(
                        "selected", _DEFAULT_HIGHLIGHT_COLORS["selected"]
                    )
                    overlay.format.setBackground(QColor(selected_color))
                    overlay.format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
                    overlay.format.setUnderlineColor(QColor("#1E3A8A"))
                    overlay.format.setProperty(QTextFormat.FullWidthSelection, False)
                    selections.append(overlay)
    editor.setExtraSelections(selections)

def _refresh_highlights(self) -> None:
    if str(getattr(self, "_formal_review_input_mode", "word") or "word") == "word":
        return
    selected_issue_id = str(getattr(self, "_formal_review_selected_issue_id", "") or "")
    for claim_num, editor in dict(getattr(self, "_formal_review_claim_content_views", {}) or {}).items():
        self._apply_highlights(
            editor,
            self._issues_for_editor(section="claims", claim_num=int(claim_num)),
            selected_issue_id,
            section="claims",
            claim_num=int(claim_num),
        )
    self._apply_highlights(
        getattr(self, "formal_review_description_text", None),
        self._issues_for_editor(section="description"),
        selected_issue_id,
        section="description",
    )
    self._apply_highlights(
        getattr(self, "formal_review_abstract_text", None),
        self._issues_for_editor(section="abstract"),
        selected_issue_id,
        section="abstract",
    )
    self._apply_highlights(
        getattr(self, "formal_review_drawings_text", None),
        self._issues_for_editor(section="drawings"),
        selected_issue_id,
        section="drawings",
    )

def _focus_issue(self, issue: Issue | None) -> None:
    if str(getattr(self, "_formal_review_input_mode", "word") or "word") == "word":
        return
    if issue is None or bool(getattr(issue, "ignored", False)):
        return
    editor = None
    if issue.section == "claims":
        claim_num = _safe_int(issue.claim_num, None)
        if claim_num is not None:
            self._expand_claim_tree_for_focus(int(claim_num))
            editor = (getattr(self, "_formal_review_claim_content_views", {}) or {}).get(int(claim_num))
    elif issue.section == "description":
        editor = getattr(self, "formal_review_description_text", None)
    elif issue.section == "abstract":
        editor = getattr(self, "formal_review_abstract_text", None)
    elif issue.section == "drawings":
        editor = getattr(self, "formal_review_drawings_text", None)
    if editor is None:
        return
    source = str(editor.toPlainText() or "")
    start = _safe_int(issue.span_start, None)
    end = _safe_int(issue.span_end, None)
    if not source or start is None:
        return
    start = max(0, min(int(start), len(source)))
    if end is None:
        end = start
    end = max(start, min(int(end), len(source)))
    cursor = editor.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.KeepAnchor)
    editor.setTextCursor(cursor)
    try:
        editor.ensureCursorVisible()
    except Exception:
        pass

def _expand_claim_tree_for_focus(self, claim_num: int) -> None:
    tree = getattr(self, "formal_review_claims_tree", None)
    if tree is None:
        return
    target_token = f"claim:{int(claim_num)}"
    for index in range(tree.topLevelItemCount()):
        root = tree.topLevelItem(index)
        if root is None:
            continue
        token = str(root.data(0, Qt.UserRole) or "")
        if token != target_token:
            continue
        root.setExpanded(True)
        focus_item = root
        for child_idx in range(root.childCount()):
            child = root.child(child_idx)
            if child is None:
                continue
            child_token = str(child.data(0, Qt.UserRole) or "")
            if child_token.startswith("claim_content:"):
                focus_item = child
                break
        if focus_item is not None:
            tree.setCurrentItem(focus_item)
            try:
                tree.scrollToItem(focus_item)
            except Exception:
                pass
        return

def _get_issue_by_id(self, issue_id: str) -> Issue | None:
    return (getattr(self, "_formal_review_issue_map", {}) or {}).get(str(issue_id or ""))

def _issues_for_editor(self, *, section: str, claim_num: int | None = None) -> list[Issue]:
    result: list[Issue] = []
    for issue in list(getattr(self, "_formal_review_issues", []) or []):
        if issue.ignored:
            continue
        if not _issue_matches_editor(issue, section=section, claim_num=claim_num):
            continue
        result.append(issue)
    return result

def _section_text_for_issue(self, issue: Issue | None) -> str:
    if issue is None:
        return ""
    mode = str(getattr(self, "_formal_review_input_mode", "word") or "word")
    if mode == "word":
        document = getattr(self, "_formal_review_document", None)
        if document is None:
            return ""
        if issue.section == "claims":
            claim_num = _safe_int(issue.claim_num, None)
            if claim_num is None:
                return ""
            for claim in list(getattr(document, "claims", []) or []):
                if int(getattr(claim, "num", 0) or 0) == int(claim_num):
                    return str(getattr(claim, "text", "") or "")
            return ""
        if issue.section == "description":
            return str(getattr(document, "description", "") or "")
        if issue.section == "abstract":
            return str(getattr(document, "abstract", "") or "")
        if issue.section == "drawings":
            return str(getattr(document, "drawings", "") or "")
        return ""
    if issue.section == "claims":
        editor = (getattr(self, "_formal_review_claim_content_views", {}) or {}).get(int(issue.claim_num or -1))
        return str(editor.toPlainText() or "") if editor is not None else ""
    if issue.section == "description":
        editor = getattr(self, "formal_review_description_text", None)
        return str(editor.toPlainText() or "") if editor is not None else ""
    if issue.section == "abstract":
        editor = getattr(self, "formal_review_abstract_text", None)
        return str(editor.toPlainText() or "") if editor is not None else ""
    if issue.section == "drawings":
        editor = getattr(self, "formal_review_drawings_text", None)
        return str(editor.toPlainText() or "") if editor is not None else ""
    return ""

def _sync_issue_detail_panel(self, issue: Issue | None) -> None:
    meta_label = getattr(self, "formal_review_issue_meta_label", None)
    before_edit = getattr(self, "formal_review_issue_context_before", None)
    hit_edit = getattr(self, "formal_review_issue_context_hit", None)
    after_edit = getattr(self, "formal_review_issue_context_after", None)
    preview = getattr(self, "formal_review_issue_preview", None)
    toggle = getattr(self, "formal_review_issue_ignore_toggle", None)
    ignore_enabled = bool(self._ignore_enabled())
    if issue is None:
        if meta_label is not None:
            meta_label.setText("未选择问题")
        if before_edit is not None:
            before_edit.setPlainText("")
        if hit_edit is not None:
            hit_edit.setHtml("")
        if after_edit is not None:
            after_edit.setPlainText("")
        if preview is not None:
            preview.setHtml("")
        if toggle is not None:
            toggle.blockSignals(True)
            toggle.setChecked(False)
            toggle.setEnabled(False)
            toggle.blockSignals(False)
        return
    severity_text = _SEVERITY_LABELS.get(str(issue.severity or "").lower(), str(issue.severity or ""))
    ignored_text = "（已忽略）" if (ignore_enabled and bool(issue.ignored)) else ""
    if meta_label is not None:
        meta_label.setText(f"{_issue_group_label(issue)} {ignored_text}\n{_issue_location_text(issue)}\n{str(issue.message or '')}".strip())
    source = self._section_text_for_issue(issue)
    start = _safe_int(issue.span_start, None)
    end = _safe_int(issue.span_end, None)
    before_text = ""
    hit_text = str(issue.snippet or "")
    after_text = ""
    if start is not None and end is not None and source:
        start = max(0, min(int(start), len(source)))
        end = max(start, min(int(end), len(source)))
        before_text = source[max(0, start - _CONTEXT_RADIUS) : start]
        hit_text = source[start:end] if end > start else hit_text
        after_text = source[end : min(len(source), end + _CONTEXT_RADIUS)]
    if before_edit is not None:
        before_edit.setPlainText("")
    if hit_edit is not None:
        hit_edit.setHtml("")
    if after_edit is not None:
        after_edit.setPlainText("")
    if preview is not None:
        rule_label = html.escape(str(RULE_REGISTRY.get(issue.rule_id, {}).get("label") or "其他检查项目"))
        preview.setHtml(
            "<div style='line-height:1.6'>"
            f"{html.escape(before_text)}"
            f"<span style='text-decoration: underline; font-weight: 600;'>{html.escape(hit_text)}</span>"
            f"{html.escape(after_text)}"
            f"<div style='margin-top:8px;color:#64748B'>严重度：{html.escape(severity_text)}</div>"
            f"<div style='margin-top:2px;color:#94A3B8'>检查项目：{rule_label}</div>"
            "</div>"
        )
    if toggle is not None:
        toggle.blockSignals(True)
        toggle.setEnabled(bool(ignore_enabled and issue.issue_id))
        toggle.setChecked(bool(ignore_enabled and issue.ignored))
        toggle.blockSignals(False)

def _populate_summary_views(self, issues: list[Issue]) -> None:
    tree = getattr(self, "formal_review_results_tree", None)
    if tree is None:
        return
    ignore_enabled = self._ignore_enabled()
    self._formal_review_syncing_ui = True
    try:
        with QSignalBlocker(tree):
            tree.clear()
            groups: dict[str, QTreeWidgetItem] = {}
            for issue in issues:
                key = _issue_group_label_compact_for_list(issue)
                root = groups.get(key)
                if root is None:
                    root = QTreeWidgetItem([key, "", "", ""])
                    root.setData(0, Qt.UserRole, "")
                    root.setFlags((root.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled) & ~Qt.ItemIsUserCheckable)
                    tree.addTopLevelItem(root)
                    groups[key] = root
                severity = _SEVERITY_LABELS.get(str(issue.severity or "").lower(), str(issue.severity or ""))
                message = _issue_reason_compact(issue)
                if ignore_enabled and bool(issue.ignored):
                    message = f"{message} [已忽略]"
                child = QTreeWidgetItem([_issue_location_compact_for_list(issue), severity, message, ""])
                child.setData(0, Qt.UserRole, str(issue.issue_id or ""))
                flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
                if ignore_enabled:
                    flags |= Qt.ItemIsUserCheckable
                    child.setCheckState(3, Qt.CheckState.Checked if issue.ignored else Qt.CheckState.Unchecked)
                child.setFlags(flags)
                child.setToolTip(2, str(issue.message or ""))
                root.addChild(child)
            for root in groups.values():
                root.setText(0, f"{root.text(0)}（{root.childCount()}）")
                root.setExpanded(True)
    finally:
        self._formal_review_syncing_ui = False
    self._schedule_results_tree_layout_refresh()

def _render_issue_views(self) -> None:
    self._formal_review_issue_map = {str(issue.issue_id or ""): issue for issue in list(getattr(self, "_formal_review_issues", []) or [])}
    self._populate_summary_views(list(getattr(self, "_formal_review_issues", []) or []))
    selected = self._get_issue_by_id(str(getattr(self, "_formal_review_selected_issue_id", "") or ""))
    self._sync_issue_detail_panel(selected)
    self._refresh_highlights()
    self._schedule_results_tree_layout_refresh()

def _reset_issue_views(self, *, clear_ignore: bool) -> None:
    if clear_ignore:
        store = getattr(self, "_formal_review_suppression_store", None)
        if store is not None:
            store.clear_current()
    self._formal_review_issues = []
    self._formal_review_skipped_rule_labels = []
    self._formal_review_skipped_rule_reason = ""
    self._formal_review_issue_map = {}
    self._formal_review_issue_fingerprints = {}
    self._formal_review_selected_issue_id = ""
    tree = getattr(self, "formal_review_results_tree", None)
    if tree is not None:
        tree.clear()
    self._sync_issue_detail_panel(None)
    self._refresh_highlights()
    self._schedule_results_tree_layout_refresh()

def _locate_issue(self, issue_id: str) -> None:
    issue = self._get_issue_by_id(issue_id)
    if issue is None:
        return
    is_word_mode = str(getattr(self, "_formal_review_input_mode", "word") or "word") == "word"
    self._formal_review_selected_issue_id = str(issue_id or "")
    if (not is_word_mode) and issue.section == "claims" and issue.claim_num is not None:
        self._formal_review_selected_claim_num = int(issue.claim_num)
    if not is_word_mode:
        tabs = getattr(self, "formal_review_tabs", None)
        if tabs is not None:
            tabs.setCurrentIndex({"claims": 0, "description": 1, "abstract": 2, "drawings": 3}.get(issue.section, 0))
    if not is_word_mode:
        self._sync_issue_detail_panel(issue)
    if not is_word_mode:
        self._refresh_highlights()
        self._focus_issue(issue)
    if is_word_mode:
        session = getattr(self, "_formal_review_companion_session", None)
        if session is not None:
            if not self._ensure_com_find_ready_or_prompt(context=f"locate_issue:{str(issue_id or '')}"):
                return
            try:
                used_loose = False
                locate = locate_issue_in_word(
                    session,
                    issue,
                    projections=getattr(self, "_formal_review_projections", None),
                    activate_window=True,
                    strict=True,
                    require_com_ready=True,
                )
                if not bool(getattr(locate, "ok", False)):
                    # Navigation-only fallback: strict -> loose (still paragraph-scoped, no full-doc match).
                    locate = locate_issue_in_word(
                        session,
                        issue,
                        projections=getattr(self, "_formal_review_projections", None),
                        activate_window=True,
                        strict=False,
                        require_com_ready=True,
                    )
                    used_loose = bool(getattr(locate, "ok", False))
            except Exception as exc:
                self._set_status_text(f"形式审查：Word定位失败（{exc}）")
            else:
                if not bool(getattr(locate, "ok", False)):
                    self._set_status_text(f"形式审查：Word定位失败（{getattr(locate, 'message', '未知原因')}）")
                else:
                    tag = "（请核对定位位置）" if used_loose else ""
                    self._set_status_text(f"形式审查：{getattr(locate, 'message', '')}{tag}")

def _schedule_companion_comment_resync(
    self,
    trigger: str,
    *,
    notify_failure: bool,
    debounce_ms: int = 350,
) -> None:
    self._ensure_formal_review_state()
    if str(getattr(self, "_formal_review_input_mode", "word") or "word") != "word":
        return
    if getattr(self, "_formal_review_companion_session", None) is None:
        return
    try:
        seq = int(getattr(self, "_formal_review_ignore_resync_seq", 0) or 0) + 1
    except Exception:
        seq = 1
    self._formal_review_ignore_resync_seq = int(seq)
    logger.debug(
        "[formal_review][ignore] resync_scheduled: trigger=%s seq=%s debounce_ms=%s",
        str(trigger or ""),
        int(seq),
        int(debounce_ms),
    )

    def _run() -> None:
        try:
            if int(getattr(self, "_formal_review_ignore_resync_seq", 0) or 0) != int(seq):
                return
        except Exception:
            return
        if str(getattr(self, "_formal_review_input_mode", "word") or "word") != "word":
            return
        if getattr(self, "_formal_review_companion_session", None) is None:
            return
        logger.info("[formal_review][ignore] resync_begin: trigger=%s seq=%s", str(trigger or ""), int(seq))
        try:
            self._auto_sync_comments_to_copy(trigger=str(trigger or ""), notify_failure=bool(notify_failure))
        except Exception as exc:
            logger.exception("[formal_review][ignore] resync_exception: %s", exc)

    try:
        QTimer.singleShot(max(0, int(debounce_ms)), _run)
    except Exception:
        _run()

def _toggle_issue_ignore(self, issue_id: str, ignored: bool) -> None:
    if not self._ignore_enabled():
        return
    issue = self._get_issue_by_id(issue_id)
    if issue is None:
        return
    if bool(issue.ignored) == bool(ignored):
        return
    logger.info(
        "[formal_review][ignore] toggle: issue_id=%s ignored=%s",
        str(issue_id or ""),
        bool(ignored),
    )
    issue.ignored = bool(ignored)
    issue_key = str(getattr(issue, "issue_id", "") or "")
    fingerprint_map = dict(getattr(self, "_formal_review_issue_fingerprints", {}) or {})
    fp = str(fingerprint_map.get(issue_key, "") or "")
    store = getattr(self, "_formal_review_suppression_store", None)
    if store is not None and fp:
        store.mark_instance(fp, bool(ignored))
    if str(getattr(self, "_formal_review_input_mode", "word") or "word") == "word":
        self._schedule_companion_comment_resync("ignore", notify_failure=False)
    self._render_issue_views()

def on_formal_review_summary_item_clicked(self, item, _column):
    if item is None:
        return
    issue_id = str(item.data(0, Qt.UserRole) or "")
    if issue_id:
        self._locate_issue(issue_id)
        return
    item.setExpanded(not item.isExpanded())

def on_formal_review_summary_tree_item_changed(self, item, column: int):
    if bool(getattr(self, "_formal_review_syncing_ui", False)) or item is None or column != 3:
        return
    if not self._ignore_enabled():
        return
    issue_id = str(item.data(0, Qt.UserRole) or "")
    if not issue_id:
        return
    self._toggle_issue_ignore(issue_id, item.checkState(3) == Qt.CheckState.Checked)

def on_formal_review_issue_toggle_changed(self, state) -> None:
    if bool(getattr(self, "_formal_review_syncing_ui", False)):
        return
    if not self._ignore_enabled():
        return
    issue_id = str(getattr(self, "_formal_review_selected_issue_id", "") or "")
    if not issue_id:
        return
    try:
        checked = Qt.CheckState(state) == Qt.CheckState.Checked
    except Exception:
        checked = bool(state)
    self._toggle_issue_ignore(issue_id, checked)

def on_formal_review_claim_tree_item_clicked(self, item, _column):
    if item is None:
        return
    token = str(item.data(0, Qt.UserRole) or "")
    claim_num = None
    if token.startswith("claim:"):
        claim_num = _safe_int(token.split(":", 1)[1], None)
    elif token.startswith("claim_content:") or token.startswith("claim_markers:"):
        claim_num = _safe_int(token.split(":", 1)[1], None)
    elif item.parent() is not None:
        parent_token = str(item.parent().data(0, Qt.UserRole) or "")
        if parent_token.startswith("claim:"):
            claim_num = _safe_int(parent_token.split(":", 1)[1], None)
    if claim_num is not None:
        self._formal_review_selected_claim_num = int(claim_num)
        self._refresh_highlights()

def on_formal_review_tab_changed(self, _index: int):
    self._ensure_formal_review_state()
    if str(getattr(self, "_formal_review_input_mode", "word") or "word") == "word":
        return
    tabs = getattr(self, "formal_review_tabs", None)
    if tabs is not None and int(tabs.currentIndex()) == 0:
        self._schedule_claims_dynamic_layout()
    self._schedule_results_tree_layout_refresh()
    self._refresh_highlights()

def on_formal_review_summary_table_cell_clicked(self, row: int, _column: int):
    table = getattr(self, "formal_review_summary_table", None)
    if table is None or row < 0:
        return
    item = table.item(row, 0)
    issue_id = str(item.data(Qt.UserRole) or "") if item is not None else ""
    if issue_id:
        self._locate_issue(issue_id)

def on_formal_review_issue_table_cell_clicked(self, row: int, _column: int):
    table = self.sender()
    if table is None or row < 0:
        return
    item = table.item(row, 0)
    issue_id = str(item.data(Qt.UserRole) or "") if item is not None else ""
    if issue_id:
        self._locate_issue(issue_id)

def on_formal_review_claim_row_clicked(self, row: int, _column: int):
    table = getattr(self, "formal_review_claims_table", None)
    if table is None or row < 0:
        return
    item = table.item(row, 0)
    claim_num = _safe_int(item.text(), None) if item is not None else None
    if claim_num is not None:
        self._formal_review_selected_claim_num = int(claim_num)


