from __future__ import annotations

from core.user_messages import user_error_text

from .shared import (
    Iterable,
    NamingGroupConfig,
    NoticeInputBundle,
    NoticeInputLeaf,
    NoticeMeta,
    NoticeTypeNamingConfig,
    OFFICIAL_DOC_BASE_TYPES,
    ParsedNotice,
    ProcessOptions,
    QFileDialog,
    QMessageBox,
    QSignalBlocker,
    QTimer,
    QTreeWidgetItem,
    Qt,
    TREE_DATA_ROLE,
    TREE_NODE_BUNDLE,
    TREE_NODE_LEAF,
    _canonical_notice_name_for_display,
    _group_config_notice_type_hint,
    _leaf_display_name,
    normalize_notice_input_paths,
    normalize_notice_name_for_meta,
    normalize_notice_type,
    normalize_type_naming_config,
    os,
    parse_official_notice_archive,
    resolve_notice_inputs,
)


def _sync_official_docs_list_detail_toggle_text(self, visible: bool | None = None) -> None:
    button = getattr(self, "official_docs_toggle_task_details_button", None)
    if button is None:
        return
    if visible is None:
        splitter = getattr(self, "official_docs_task_splitter", None)
        if splitter is None:
            visible = False
        else:
            try:
                visible = bool(splitter.isVisible())
            except Exception:
                visible = False
    task_count = len(getattr(self, "_official_docs_leaves", {}) or {})
    try:
        action_text = "隐藏列表/详情" if bool(visible) else "显示列表/详情"
        button.setText(f"{action_text}（{task_count}）")
    except Exception:
        return


def _set_official_docs_list_detail_visible(self, visible: bool) -> None:
    splitter = getattr(self, "official_docs_task_splitter", None)
    if splitter is None:
        _sync_official_docs_list_detail_toggle_text(self, False)
        return
    try:
        splitter.setVisible(bool(visible))
    except Exception:
        _sync_official_docs_list_detail_toggle_text(self, False)
        return
    _sync_official_docs_list_detail_toggle_text(self, bool(visible))


def _sync_official_docs_bundle_item_text(self, item: QTreeWidgetItem | None) -> None:
    bundle_item = item
    if bundle_item is None:
        return
    data = bundle_item.data(0, TREE_DATA_ROLE)
    if not (isinstance(data, dict) and str(data.get("type", "") or "") == TREE_NODE_BUNDLE):
        bundle_item = bundle_item.parent()
        if bundle_item is None:
            return
        data = bundle_item.data(0, TREE_DATA_ROLE)
        if not (isinstance(data, dict) and str(data.get("type", "") or "") == TREE_NODE_BUNDLE):
            return

    bundle_key = str(data.get("key", "") or "").strip()
    bundle_name = ""
    bundles = getattr(self, "_official_docs_bundles", {})
    if isinstance(bundles, dict):
        bundle = bundles.get(bundle_key)
        if isinstance(bundle, dict):
            bundle_name = str(bundle.get("display_name", "") or "").strip()
    if not bundle_name:
        bundle_name = str(bundle_item.text(0) or "").split(" (", 1)[0].strip()
    visible_count = int(bundle_item.childCount())
    checked_count = 0
    for child_index in range(visible_count):
        child = bundle_item.child(child_index)
        if child is not None and child.checkState(0) == Qt.Checked:
            checked_count += 1
    bundle_item.setText(0, f"{bundle_name or '通知书总包'} ({checked_count}/{visible_count})")


def _sync_official_docs_start_button_enabled(self) -> None:
    start_btn = getattr(self, "official_docs_start_button", None)
    if start_btn is None:
        return
    settings = getattr(self, "_official_docs_working_settings", {})
    if not isinstance(settings, dict):
        settings = {}
    setting_errors = self._validate_official_docs_settings(dict(settings))
    has_checked = any(True for _ in self._iter_checked_leaf_ids())
    start_btn.setEnabled(has_checked and not bool(setting_errors))


def on_official_docs_toggle_task_details_visibility(self) -> None:
    splitter = getattr(self, "official_docs_task_splitter", None)
    if splitter is None:
        _sync_official_docs_list_detail_toggle_text(self, False)
        return
    try:
        current_visible = bool(splitter.isVisible())
    except Exception:
        current_visible = False
    _set_official_docs_list_detail_visible(self, not current_visible)


def _add_official_docs_inputs(self, input_paths: Iterable[str]) -> int:
    self._init_official_docs_state()
    normalized_paths = normalize_notice_input_paths(input_paths)
    if not normalized_paths:
        self._official_docs_last_import_ignored = []
        return 0

    temp_root = self._ensure_official_docs_temp_root()
    settings = self._get_official_docs_settings_snapshot(sync_current_type=False)
    resolved = resolve_notice_inputs(
        normalized_paths,
        temp_root_dir=temp_root,
        no_list_multi_pdf_mode=str(settings.get("no_list_multi_pdf_mode", "split_each_pdf") or "split_each_pdf"),
    )
    self._official_docs_last_import_ignored = list(getattr(resolved, "ignored", []) or [])

    added = 0
    leaves = getattr(self, "_official_docs_leaves", {})
    bundles = getattr(self, "_official_docs_bundles", {})
    node_list = getattr(self, "_official_docs_nodes", [])

    for node in resolved.nodes:
        if isinstance(node, NoticeInputBundle):
            bundle_key = str(node.key or "").strip()
            if not bundle_key:
                continue
            bundle_node = self._ensure_node_exists(
                bundle_key,
                is_bundle=True,
                display_name=str(node.display_name or "").strip() or os.path.basename(node.source_path),
                source_path=str(node.source_path or ""),
            )
            bundle_node["children"] = bundle_node.get("children", [])
            bundles[bundle_key] = bundle_node
            for leaf in node.children or []:
                leaf_id = str(leaf.id or "").strip()
                if not leaf_id or leaf_id in leaves:
                    continue
                leaf_data = {
                    "id": leaf_id,
                    "zip_path": str(leaf.zip_path or ""),
                    "display_name": str(leaf.display_name or ""),
                    "source_path": str(leaf.source_path or ""),
                    "bundle_key": bundle_key,
                    "bundle_name": str(leaf.bundle_name or node.display_name or ""),
                    "inner_zip_name": str(leaf.inner_zip_name or ""),
                    "source_label": str(leaf.source_label or ""),
                    "checked": True,
                    "parsed": None,
                    "last_result": None,
                }
                leaves[leaf_id] = leaf_data
                bundle_node["children"].append(leaf_id)
                added += 1
            continue

        if isinstance(node, NoticeInputLeaf):
            leaf_id = str(node.id or "").strip()
            if not leaf_id or leaf_id in leaves:
                continue
            leaf_data = {
                "id": leaf_id,
                "zip_path": str(node.zip_path or ""),
                "display_name": str(node.display_name or ""),
                "source_path": str(node.source_path or ""),
                "bundle_key": "",
                "bundle_name": "",
                "inner_zip_name": "",
                "source_label": str(node.source_label or ""),
                "checked": True,
                "parsed": None,
                "last_result": None,
            }
            leaves[leaf_id] = leaf_data
            node_list.append(
                {
                    "key": leaf_id,
                    "is_bundle": False,
                    "display_name": str(node.display_name or ""),
                    "source_path": str(node.source_path or ""),
                    "children": [],
                }
            )
            added += 1

    if added <= 0:
        return 0

    for leaf_id in self._iter_leaf_ids_in_order():
        self._parse_official_docs_leaf_if_needed(leaf_id)

    self._refresh_official_docs_type_list()
    self._render_official_docs_tree()
    if not str(getattr(self, "_official_docs_selected_leaf_id", "") or "").strip():
        for leaf_id in self._iter_leaf_ids_in_order():
            self._official_docs_selected_leaf_id = leaf_id
            break
    self._refresh_official_docs_detail()
    _set_official_docs_list_detail_visible(self, True)
    ignored = list(getattr(resolved, "ignored", []) or [])
    if ignored:
        preview_lines = [f"{item.display_name}: {item.reason}" for item in ignored[:8]]
        if len(ignored) > 8:
            preview_lines.append(f"... 其余 {len(ignored) - 8} 项已跳过")
        QMessageBox.warning(self, "部分 ZIP 未导入", user_error_text("\n".join(preview_lines)))
    return added

def on_official_docs_choose_zips(self) -> None:
    self._init_official_docs_state()
    default_dir = os.getcwd()
    paths, _ = QFileDialog.getOpenFileNames(
        self,
        "选择官方通知书 ZIP",
        default_dir,
        "ZIP 文件 (*.zip)",
    )
    if not paths:
        return
    added = self._add_official_docs_inputs(paths)
    if added <= 0 and not list(getattr(self, "_official_docs_last_import_ignored", []) or []):
        QMessageBox.information(self, "提示", "没有识别到新的可处理通知书 ZIP。")

def on_official_docs_choose_folder(self) -> None:
    self._init_official_docs_state()
    selected = QFileDialog.getExistingDirectory(self, "选择包含官方通知书 ZIP 的文件夹", os.getcwd())
    if not selected:
        return
    added = self._add_official_docs_inputs([selected])
    if added <= 0 and not list(getattr(self, "_official_docs_last_import_ignored", []) or []):
        QMessageBox.information(self, "提示", "所选目录下未识别到新的 ZIP 文件。")

def on_official_docs_paths_dropped(self, paths: Iterable[str]) -> None:
    self._init_official_docs_state()
    added = self._add_official_docs_inputs(paths)
    if added <= 0 and not list(getattr(self, "_official_docs_last_import_ignored", []) or []):
        QMessageBox.information(self, "提示", "未识别到可导入的 ZIP 文件。")

def on_official_docs_clear_items(self) -> None:
    self._init_official_docs_state()
    self._official_docs_nodes = []
    self._official_docs_bundles = {}
    self._official_docs_leaves = {}
    self._official_docs_bundle_expanded = {}
    self._official_docs_selected_leaf_id = ""
    self._official_docs_search_text = ""
    self._official_docs_last_import_ignored = []
    search_edit = getattr(self, "official_docs_search_edit", None)
    if search_edit is not None:
        with QSignalBlocker(search_edit):
            search_edit.clear()
    self._cleanup_official_docs_temp()
    self._refresh_official_docs_type_list()
    self._render_official_docs_tree()
    self._refresh_official_docs_detail()
    _set_official_docs_list_detail_visible(self, False)

def _parse_official_docs_leaf_if_needed(self, leaf_id: str) -> ParsedNotice | None:
    leaves = getattr(self, "_official_docs_leaves", {})
    leaf = leaves.get(leaf_id) if isinstance(leaves, dict) else None
    if not isinstance(leaf, dict):
        return None
    parsed = leaf.get("parsed")
    if isinstance(parsed, ParsedNotice):
        return parsed
    zip_path = str(leaf.get("zip_path", "") or "").strip()
    if not zip_path:
        parsed = ParsedNotice(source_zip_path="", notice_kind="unknown", meta=NoticeMeta(), errors=["ZIP 路径为空"])
        leaf["parsed"] = parsed
        return parsed
    try:
        parsed = parse_official_notice_archive(zip_path)
    except Exception as exc:
        parsed = ParsedNotice(source_zip_path=zip_path, notice_kind="unknown", meta=NoticeMeta(), errors=[str(exc)])
    leaf["parsed"] = parsed
    return parsed

def _leaf_search_payload(self, leaf_id: str) -> str:
    leaves = getattr(self, "_official_docs_leaves", {})
    leaf = leaves.get(leaf_id) if isinstance(leaves, dict) else None
    if not isinstance(leaf, dict):
        return ""
    parsed = leaf.get("parsed")
    canonical_notice_name = ""
    if isinstance(parsed, ParsedNotice):
        canonical_notice_name = _canonical_notice_name_for_display(
            normalize_notice_name_for_meta(parsed.meta) or parsed.meta.notice_name
        )
    chunks = [
        _leaf_display_name(leaf),
        str(leaf.get("inner_zip_name", "") or ""),
        os.path.basename(str(leaf.get("source_path", "") or "")),
    ]
    if isinstance(parsed, ParsedNotice):
        chunks.extend(
            [
                parsed.meta.app_no,
                canonical_notice_name,
                parsed.meta.notice_code,
                parsed.meta.internal_no,
            ]
        )
    return " ".join([str(x or "").strip() for x in chunks if str(x or "").strip()]).lower()

def on_official_docs_search_changed(self, text: str) -> None:
    self._init_official_docs_state()
    self._official_docs_search_text = str(text or "").strip().lower()
    self._render_official_docs_tree()

def _create_leaf_tree_item(self, leaf_id: str) -> QTreeWidgetItem | None:
    leaves = getattr(self, "_official_docs_leaves", {})
    leaf = leaves.get(leaf_id) if isinstance(leaves, dict) else None
    if not isinstance(leaf, dict):
        return None
    parsed = self._parse_official_docs_leaf_if_needed(leaf_id)

    name = _leaf_display_name(leaf)
    if isinstance(parsed, ParsedNotice):
        app_no = str(parsed.meta.app_no or "").strip()
        notice_name = _canonical_notice_name_for_display(
            normalize_notice_name_for_meta(parsed.meta) or parsed.meta.notice_name
        )
        summary_parts = [notice_name]
        if app_no:
            summary_parts.append(app_no)
        if name:
            summary_parts.append(name)
        text = " | ".join(part for part in summary_parts if part)
        if parsed.errors:
            text = f"❌ {text}"
    else:
        text = name

    item = QTreeWidgetItem([text])
    item.setData(0, TREE_DATA_ROLE, {"type": TREE_NODE_LEAF, "id": leaf_id})
    item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
    item.setCheckState(0, Qt.Checked if bool(leaf.get("checked", True)) else Qt.Unchecked)
    return item

def _refresh_official_docs_tree_column_width(self) -> None:
    tree = getattr(self, "official_docs_tree", None)
    if tree is None:
        return
    try:
        tree.resizeColumnToContents(0)
        font_metrics = tree.fontMetrics()
        max_text_width = 0
        stack: list[tuple[QTreeWidgetItem, int]] = []
        for top_index in range(tree.topLevelItemCount()):
            top_item = tree.topLevelItem(top_index)
            if top_item is not None:
                stack.append((top_item, 0))

        while stack:
            item, depth = stack.pop()
            text_width = int(font_metrics.horizontalAdvance(str(item.text(0) or "")))
            depth_indent = max(0, int(depth)) * max(0, int(tree.indentation()))
            row_width = text_width + depth_indent + 72
            if row_width > max_text_width:
                max_text_width = row_width
            for child_index in range(item.childCount() - 1, -1, -1):
                child = item.child(child_index)
                if child is not None:
                    stack.append((child, depth + 1))

        hint_width = int(tree.sizeHintForColumn(0))
        current_width = int(tree.columnWidth(0))
        viewport_width = int(tree.viewport().width())
        target_width = max(hint_width, current_width, max_text_width)
        if target_width <= 0:
            target_width = max(180, viewport_width)
        if target_width > viewport_width:
            tree.setColumnWidth(0, target_width + 24)
            return
        tree.setColumnWidth(0, max(viewport_width - 2, target_width))
    except Exception:
        return

def _render_official_docs_tree(self) -> None:
    self._init_official_docs_state()
    tree = getattr(self, "official_docs_tree", None)
    if tree is None:
        return

    current_leaf_id = str(getattr(self, "_official_docs_selected_leaf_id", "") or "").strip()
    keyword = str(getattr(self, "_official_docs_search_text", "") or "").strip().lower()

    self._official_docs_tree_rebuilding = True
    try:
        with QSignalBlocker(tree):
            tree.clear()
            visible_leaf_count = 0

            for node in list(getattr(self, "_official_docs_nodes", []) or []):
                if bool(node.get("is_bundle", False)):
                    bundle_key = str(node.get("key", "") or "").strip()
                    child_ids = [str(cid or "").strip() for cid in list(node.get("children", []) or []) if str(cid or "").strip()]
                    visible_children: list[tuple[str, QTreeWidgetItem]] = []
                    checked_count = 0
                    for leaf_id in child_ids:
                        payload = self._leaf_search_payload(leaf_id)
                        if keyword and keyword not in payload:
                            continue
                        child_item = self._create_leaf_tree_item(leaf_id)
                        if child_item is None:
                            continue
                        visible_children.append((leaf_id, child_item))
                        visible_leaf_count += 1
                        leaf = (getattr(self, "_official_docs_leaves", {}) or {}).get(leaf_id, {})
                        if isinstance(leaf, dict) and bool(leaf.get("checked", True)):
                            checked_count += 1

                    if not visible_children:
                        continue

                    bundle_name = str(node.get("display_name", "") or "").strip() or "通知书集合"
                    root_text = f"{bundle_name} ({checked_count}/{len(visible_children)})"
                    root_item = QTreeWidgetItem([root_text])
                    root_item.setData(0, TREE_DATA_ROLE, {"type": TREE_NODE_BUNDLE, "key": bundle_key})
                    root_item.setFlags(root_item.flags() | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    for _leaf_id, child_item in visible_children:
                        root_item.addChild(child_item)
                    tree.addTopLevelItem(root_item)
                    if bool((getattr(self, "_official_docs_bundle_expanded", {}) or {}).get(bundle_key, False)):
                        root_item.setExpanded(True)
                    continue

                leaf_id = str(node.get("key", "") or "").strip()
                payload = self._leaf_search_payload(leaf_id)
                if keyword and keyword not in payload:
                    continue
                leaf_item = self._create_leaf_tree_item(leaf_id)
                if leaf_item is None:
                    continue
                tree.addTopLevelItem(leaf_item)
                visible_leaf_count += 1

            selected_item: QTreeWidgetItem | None = None
            if current_leaf_id:
                iterator = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
                while iterator:
                    node = iterator.pop(0)
                    if node is None:
                        continue
                    data = node.data(0, TREE_DATA_ROLE)
                    if isinstance(data, dict):
                        if str(data.get("type")) == TREE_NODE_LEAF and str(data.get("id", "")) == current_leaf_id:
                            selected_item = node
                            break
                    for child_index in range(node.childCount()):
                        child = node.child(child_index)
                        if child is not None:
                            iterator.append(child)

            if selected_item is None and tree.topLevelItemCount() > 0:
                top_item = tree.topLevelItem(0)
                if top_item is not None:
                    data = top_item.data(0, TREE_DATA_ROLE)
                    if isinstance(data, dict) and str(data.get("type")) == TREE_NODE_BUNDLE and top_item.childCount() > 0:
                        selected_item = top_item.child(0)
                    else:
                        selected_item = top_item

            if selected_item is not None:
                tree.setCurrentItem(selected_item)
                data = selected_item.data(0, TREE_DATA_ROLE)
                if isinstance(data, dict) and str(data.get("type")) == TREE_NODE_LEAF:
                    self._official_docs_selected_leaf_id = str(data.get("id", "") or "")
            else:
                self._official_docs_selected_leaf_id = ""

            count_label = getattr(self, "official_docs_list_count_label", None)
            if count_label is not None:
                count_label.setText(f"{visible_leaf_count} 项")
            _sync_official_docs_list_detail_toggle_text(self)

            self._refresh_official_docs_tree_column_width()
            try:
                QTimer.singleShot(0, self._refresh_official_docs_tree_column_width)
            except Exception:
                pass
    finally:
        self._official_docs_tree_rebuilding = False

def on_official_docs_item_check_changed(self, item: QTreeWidgetItem, column: int) -> None:
    self._init_official_docs_state()
    if bool(getattr(self, "_official_docs_tree_rebuilding", False)):
        return
    if int(column) != 0:
        return
    data = item.data(0, TREE_DATA_ROLE)
    if not isinstance(data, dict):
        return
    if str(data.get("type")) != TREE_NODE_LEAF:
        return
    leaf_id = str(data.get("id", "") or "").strip()
    if not leaf_id:
        return
    leaf = (getattr(self, "_official_docs_leaves", {}) or {}).get(leaf_id)
    if not isinstance(leaf, dict):
        return
    leaf["checked"] = bool(item.checkState(0) == Qt.Checked)
    _sync_official_docs_bundle_item_text(self, item)
    _sync_official_docs_start_button_enabled(self)

def on_official_docs_item_expanded(self, item: QTreeWidgetItem) -> None:
    data = item.data(0, TREE_DATA_ROLE)
    if not isinstance(data, dict):
        return
    if str(data.get("type")) != TREE_NODE_BUNDLE:
        return
    key = str(data.get("key", "") or "").strip()
    if key:
        self._official_docs_bundle_expanded[key] = True
    self._refresh_official_docs_tree_column_width()

def on_official_docs_item_collapsed(self, item: QTreeWidgetItem) -> None:
    data = item.data(0, TREE_DATA_ROLE)
    if not isinstance(data, dict):
        return
    if str(data.get("type")) != TREE_NODE_BUNDLE:
        return
    key = str(data.get("key", "") or "").strip()
    if key:
        self._official_docs_bundle_expanded[key] = False
    self._refresh_official_docs_tree_column_width()

def on_official_docs_selection_changed(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None) -> None:
    self._init_official_docs_state()
    if bool(getattr(self, "_official_docs_tree_rebuilding", False)):
        return
    next_leaf_id = ""
    if current is not None:
        try:
            data = current.data(0, TREE_DATA_ROLE)
        except RuntimeError:
            data = None
        if isinstance(data, dict):
            node_type = str(data.get("type", "") or "")
            if node_type == TREE_NODE_LEAF:
                next_leaf_id = str(data.get("id", "") or "")
            elif node_type == TREE_NODE_BUNDLE:
                try:
                    child = current.child(0) if current.childCount() > 0 else None
                except RuntimeError:
                    child = None
                if child is not None:
                    try:
                        child_data = child.data(0, TREE_DATA_ROLE)
                    except RuntimeError:
                        child_data = None
                    if isinstance(child_data, dict):
                        next_leaf_id = str(child_data.get("id", "") or "")
    self._official_docs_selected_leaf_id = next_leaf_id
    self._refresh_official_docs_detail()

def _iter_leaf_ids_in_order(self) -> Iterable[str]:
    nodes = list(getattr(self, "_official_docs_nodes", []) or [])
    for node in nodes:
        if bool(node.get("is_bundle", False)):
            for child_id in list(node.get("children", []) or []):
                leaf_id = str(child_id or "").strip()
                if leaf_id:
                    yield leaf_id
            continue
        leaf_id = str(node.get("key", "") or "").strip()
        if leaf_id:
            yield leaf_id

def _iter_checked_leaf_ids(self) -> Iterable[str]:
    leaves = getattr(self, "_official_docs_leaves", {})
    for leaf_id in self._iter_leaf_ids_in_order():
        leaf = leaves.get(leaf_id) if isinstance(leaves, dict) else None
        if not isinstance(leaf, dict):
            continue
        if bool(leaf.get("checked", True)):
            yield leaf_id

def _build_official_docs_options(self, *, use_saved: bool) -> ProcessOptions:
    self._init_official_docs_state()
    source = self._official_docs_saved_settings if use_saved else self._get_official_docs_settings_snapshot(sync_current_type=True)
    type_configs = source.get("type_configs", {})
    if not isinstance(type_configs, dict):
        type_configs = {}
    raw_groups = source.get("naming_groups", [])
    raw_membership = source.get("type_group_membership", {})
    normalized_groups, normalized_membership = self._normalize_naming_groups_payload(raw_groups, raw_membership)

    option_type_cfgs: dict[str, NoticeTypeNamingConfig] = {}
    for raw_kind, raw_cfg in type_configs.items():
        kind = normalize_notice_type(str(raw_kind or "").strip())
        if not kind:
            continue
        option_type_cfgs[kind] = normalize_type_naming_config(raw_cfg, kind)
    if not option_type_cfgs:
        for kind in OFFICIAL_DOC_BASE_TYPES:
            norm_kind = normalize_notice_type(kind)
            option_type_cfgs[norm_kind] = normalize_type_naming_config(None, norm_kind)

    option_groups: dict[str, NamingGroupConfig] = {}
    for raw_group in normalized_groups:
        if not isinstance(raw_group, dict):
            continue
        group_id = str(raw_group.get("id", "") or "").strip()
        group_name = str(raw_group.get("name", "") or "").strip()
        if not group_id or not group_name:
            continue
        member_type_keys = [
            normalize_notice_type(str(raw_key or "").strip())
            for raw_key in list(raw_group.get("member_type_keys", []) or [])
            if normalize_notice_type(str(raw_key or "").strip())
        ]
        notice_type_hint = _group_config_notice_type_hint(group_id, member_type_keys, "exam_opinion")
        option_groups[group_id] = NamingGroupConfig(
            id=group_id,
            name=group_name,
            member_type_keys=member_type_keys,
            group_config=normalize_type_naming_config(raw_group.get("group_config"), notice_type_hint),
        )

    raw_pdf_flags = source.get("pdf_parse_field_flags", {})
    if not isinstance(raw_pdf_flags, dict):
        raw_pdf_flags = {}

    return ProcessOptions(
        summary_root_dir=str(source.get("summary_root_dir", "") or ""),
        archive_root_dir=str(source.get("archive_root_dir", "") or ""),
        write_summary=bool(source.get("write_summary", True)),
        write_archive=bool(source.get("write_archive", False)),
        confirm_each=bool(source.get("confirm_each", False)),
        enable_exam_pdf_parse=bool(source.get("enable_exam_pdf_parse", False)),
        pdf_parse_field_flags=dict(raw_pdf_flags),
        no_list_multi_pdf_mode=str(source.get("no_list_multi_pdf_mode", "split_each_pdf") or "split_each_pdf"),
        filename_separator=str(source.get("filename_separator", "+")),
        type_naming_configs=option_type_cfgs,
        naming_groups=option_groups,
        type_group_membership=dict(normalized_membership),
    )

