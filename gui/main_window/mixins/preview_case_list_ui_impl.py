from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from gui.widgets import ClickableFrame, ElideLabel

from gui.main_window.mixins.preview_cases import iter_preview_leaf_cases


def _get_scroll_value(scroll):
    old_scroll_val = None
    try:
        if scroll is not None:
            old_scroll_val = scroll.verticalScrollBar().value()
    except Exception:
        old_scroll_val = None
    return old_scroll_val


def _clear_layout(layout) -> None:
    if not layout:
        return
    try:
        while layout.count():
            it = layout.takeAt(0)
            if it is None:
                continue
            w = it.widget()
            if w is not None:
                try:
                    w.setParent(None)
                    w.deleteLater()
                except Exception:
                    pass
            else:
                try:
                    sub = it.layout()
                    if sub is not None:
                        while sub.count():
                            sit = sub.takeAt(0)
                            sw = sit.widget() if sit else None
                            if sw is not None:
                                sw.setParent(None)
                                sw.deleteLater()
                except Exception:
                    pass
    except Exception:
        pass


def _get_filter_text(window) -> str:
    filter_text = ""
    try:
        filter_text = str(getattr(window, "_preview_case_filter_text", "") or "").strip()
    except Exception:
        filter_text = ""
    return filter_text


def _match_filter_text(ft: str, name: str) -> bool:
    if not ft:
        return True
    try:
        return ft in str(name or "").lower()
    except Exception:
        return False


def _count_total_leaf_cases(window) -> int:
    total_leaf = 0
    try:
        for _p, _l in iter_preview_leaf_cases(window):
            total_leaf += 1
    except Exception:
        total_leaf = 0
    return total_leaf


def _bundle_key_from_top(top: dict, bundle_name: str) -> str:
    bundle_key = str(top.get("source_path") or bundle_name or "")
    if not bundle_key:
        bundle_key = bundle_name
    return bundle_key


def _bundle_children_from_top(top: dict) -> list[dict]:
    try:
        return [c for c in (top.get("children") or []) if isinstance(c, dict)]
    except Exception:
        return []


def _count_children_with_zip(children: list[dict]) -> int:
    try:
        return len([c for c in children if c.get("zip_path")])
    except Exception:
        return 0


def _filter_bundle_children(children: list[dict], ft: str, bundle_match: bool) -> list[dict]:
    matched_children: list[dict] = []
    if ft:
        if bundle_match:
            return children
        for ch in children:
            if _match_filter_text(ft, str(ch.get("name") or "")):
                matched_children.append(ch)
        return matched_children
    return children


def _bundle_contains_selected(children: list[dict], selected_zip: str | None) -> bool:
    if not selected_zip:
        return False
    try:
        for c in children:
            if str(c.get("zip_path") or "") == str(selected_zip):
                return True
    except Exception:
        return False
    return False


def _get_bundle_expanded(window, bundle_key: str) -> bool:
    expanded = True
    try:
        expanded = bool(window._preview_bundle_expanded.get(bundle_key, True))
    except Exception:
        expanded = True
    return expanded


def _ensure_bundle_expanded_default(window, bundle_key: str) -> None:
    try:
        if bundle_key not in window._preview_bundle_expanded:
            window._preview_bundle_expanded[bundle_key] = True
    except Exception:
        pass


def _set_bundle_expanded(window, bundle_key: str, expanded: bool) -> None:
    try:
        window._preview_bundle_expanded[bundle_key] = bool(expanded)
    except Exception:
        pass


def _build_bundle_header(window, bundle_name: str, bundle_key: str, expanded: bool, child_total: int, is_searching: bool):
    header = ClickableFrame()
    header.setObjectName("PreviewBundleHeader")
    try:
        header.setAttribute(Qt.WA_StyledBackground, True)
    except Exception:
        pass
    hl = QHBoxLayout(header)
    hl.setContentsMargins(10, 8, 10, 8)
    hl.setSpacing(8)

    arrow = QLabel("▼" if expanded else "▶")
    arrow.setObjectName("PreviewBundleArrow")
    hl.addWidget(arrow, 0, Qt.AlignVCenter)

    name_label = ElideLabel(bundle_name, elide_mode=Qt.ElideRight)
    name_label.setProperty("role", "label")
    hl.addWidget(name_label, 1)

    cnt = QLabel(f"{child_total} 项")
    cnt.setProperty("role", "caption")
    cnt.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    hl.addWidget(cnt, 0)

    if not is_searching:
        try:
            header.clicked.connect(lambda _=None, k=bundle_key: toggle_preview_bundle_expanded(window, k))
        except Exception:
            pass

    return header


def _add_case_item(
    layout,
    window,
    *,
    zip_path: str,
    name: str,
    tooltip: str,
    wrap_left_margin: int,
    wrap_right_margin: int,
) -> None:
    wrap = QFrame()
    wrap.setObjectName("PreviewCaseChildWrap")
    try:
        wrap.setAttribute(Qt.WA_StyledBackground, True)
    except Exception:
        pass
    wl = QHBoxLayout(wrap)
    wl.setContentsMargins(int(wrap_left_margin), 0, int(wrap_right_margin), 0)
    wl.setSpacing(0)

    row = ClickableFrame()
    row.setObjectName("PreviewCaseItem")
    try:
        row.setAttribute(Qt.WA_StyledBackground, True)
    except Exception:
        pass

    is_selected = False
    try:
        is_selected = bool(getattr(window, "_preview_selected_zip_path", None) == zip_path)
    except Exception:
        is_selected = False
    try:
        row.setProperty("selected", is_selected)
    except Exception:
        pass

    rl = QHBoxLayout(row)
    rl.setContentsMargins(10, 8, 10, 8)
    rl.setSpacing(8)
    lbl = ElideLabel(name, elide_mode=Qt.ElideRight)
    lbl.setProperty("role", "label")
    rl.addWidget(lbl, 1)
    try:
        row.setToolTip(str(tooltip or ""))
    except Exception:
        pass

    try:
        row.clicked.connect(lambda _=None, zp=zip_path: set_preview_selected_zip_path(window, zp))
    except Exception:
        pass

    try:
        window._preview_case_item_widgets[zip_path] = row
    except Exception:
        pass

    wl.addWidget(row, 1)
    layout.addWidget(wrap)


def _add_bundle_group(
    layout,
    window,
    *,
    top: dict,
    ft: str,
    is_searching: bool,
    selected_zip: str | None,
    visible_zip_paths: set[str],
    first_visible_zip: str | None,
) -> tuple[int, str | None]:
    bundle_name = str(top.get("name") or "")
    bundle_key = _bundle_key_from_top(top, bundle_name)
    children = _bundle_children_from_top(top)
    child_total = _count_children_with_zip(children)

    bundle_match = _match_filter_text(ft, bundle_name)
    matched_children = _filter_bundle_children(children, ft, bundle_match)

    if ft and (not bundle_match) and (not matched_children):
        return 0, first_visible_zip

    _ensure_bundle_expanded_default(window, bundle_key)
    contains_selected = _bundle_contains_selected(children, selected_zip)
    expanded = _get_bundle_expanded(window, bundle_key)

    if contains_selected:
        _set_bundle_expanded(window, bundle_key, True)

    if is_searching:
        expanded = True

    header = _build_bundle_header(window, bundle_name, bundle_key, expanded, child_total, is_searching)
    layout.addWidget(header)

    if not expanded:
        return 0, first_visible_zip

    added = 0
    for ch in matched_children:
        zip_path = str(ch.get("zip_path") or "")
        if not zip_path:
            continue
        child_name = str(ch.get("name") or "")

        _add_case_item(
            layout,
            window,
            zip_path=zip_path,
            name=child_name,
            tooltip=f"{bundle_name} / {child_name}".strip(" /"),
            wrap_left_margin=18,
            wrap_right_margin=0,
        )
        added += 1
        visible_zip_paths.add(zip_path)
        if first_visible_zip is None:
            first_visible_zip = zip_path

    return added, first_visible_zip


def _add_single_case(
    layout,
    window,
    *,
    top: dict,
    ft: str,
    visible_zip_paths: set[str],
    first_visible_zip: str | None,
) -> tuple[int, str | None]:
    zip_path = str(top.get("zip_path") or "")
    name = str(top.get("name") or "")
    if ft and (not _match_filter_text(ft, name)):
        return 0, first_visible_zip
    if not zip_path:
        return 0, first_visible_zip

    _add_case_item(
        layout,
        window,
        zip_path=zip_path,
        name=name,
        tooltip=str(name or ""),
        wrap_left_margin=0,
        wrap_right_margin=18,
    )
    visible_zip_paths.add(zip_path)
    if first_visible_zip is None:
        first_visible_zip = zip_path
    return 1, first_visible_zip


def _build_preview_case_list_items(
    window,
    layout,
    *,
    ft: str,
    is_searching: bool,
    selected_zip: str | None,
) -> tuple[int, set[str], str | None]:
    visible_leaf = 0
    visible_zip_paths: set[str] = set()
    first_visible_zip: str | None = None

    try:
        for top in getattr(window, "_preview_cases", []) or []:
            if not isinstance(top, dict):
                continue
            kind = str(top.get("kind") or "")
            if kind == "bundle":
                added, first_visible_zip = _add_bundle_group(
                    layout,
                    window,
                    top=top,
                    ft=ft,
                    is_searching=is_searching,
                    selected_zip=selected_zip,
                    visible_zip_paths=visible_zip_paths,
                    first_visible_zip=first_visible_zip,
                )
                visible_leaf += int(added)
            else:
                added, first_visible_zip = _add_single_case(
                    layout,
                    window,
                    top=top,
                    ft=ft,
                    visible_zip_paths=visible_zip_paths,
                    first_visible_zip=first_visible_zip,
                )
                visible_leaf += int(added)
    except Exception:
        pass

    return visible_leaf, visible_zip_paths, first_visible_zip


def _add_preview_case_list_empty_state(layout, total_leaf: int, visible_leaf: int) -> None:
    if total_leaf <= 0:
        empty = QLabel("请先导入案卷 ZIP")
        empty.setObjectName("PreviewCaseEmpty")
        empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(empty)
        return
    if visible_leaf <= 0:
        empty = QLabel("无匹配结果")
        empty.setObjectName("PreviewCaseEmpty")
        empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(empty)


def _update_preview_case_count_label(window, *, ft: str, visible_leaf: int, total_leaf: int) -> None:
    try:
        if hasattr(window, "preview_case_count_label"):
            if ft:
                window.preview_case_count_label.setText(f"{visible_leaf}/{total_leaf} 项")
            else:
                window.preview_case_count_label.setText(f"{total_leaf} 项")
    except Exception:
        pass


def _fixup_preview_selected_zip_after_refresh(window, *, ft: str, is_searching: bool, visible_zip_paths: set[str], first_visible_zip: str | None) -> None:
    try:
        cur_sel = getattr(window, "_preview_selected_zip_path", None)
        if cur_sel and str(cur_sel) not in visible_zip_paths and ft:
            window._preview_selected_zip_path = None
    except Exception:
        pass

    if (not is_searching) and (not getattr(window, "_preview_selected_zip_path", None)) and first_visible_zip:
        try:
            window._preview_selected_zip_path = str(first_visible_zip)
        except Exception:
            window._preview_selected_zip_path = None
        try:
            update_preview_case_item_selected_style(window, str(first_visible_zip), True)
        except Exception:
            pass


def _clear_selected_zip_if_in_bundle(window, key: str) -> None:
    selected_zip = None
    try:
        selected_zip = getattr(window, "_preview_selected_zip_path", None)
    except Exception:
        selected_zip = None
    if not selected_zip:
        return

    try:
        for top in getattr(window, "_preview_cases", []) or []:
            if not isinstance(top, dict):
                continue
            if str(top.get("kind") or "") != "bundle":
                continue
            bundle_key = _bundle_key_from_top(top, str(top.get("name") or ""))
            if bundle_key != key:
                continue
            for ch in _bundle_children_from_top(top):
                if str(ch.get("zip_path") or "") == str(selected_zip):
                    window._preview_selected_zip_path = None
                    return
    except Exception:
        pass


def toggle_preview_bundle_expanded(window, key: str) -> None:
    if not key:
        return
    try:
        cur = bool((getattr(window, "_preview_bundle_expanded", {}) or {}).get(key, True))
    except Exception:
        cur = True

    new_val = not cur

    if not new_val:
        _clear_selected_zip_if_in_bundle(window, key)

    _set_bundle_expanded(window, key, bool(new_val))
    try:
        window._refresh_preview_case_list_ui(selected_path=getattr(window, "_preview_selected_zip_path", None))
    except Exception:
        pass


def update_preview_case_item_selected_style(window, zip_path: str | None, selected: bool) -> None:
    if not zip_path:
        return
    w = None
    try:
        w = (getattr(window, "_preview_case_item_widgets", {}) or {}).get(str(zip_path))
    except Exception:
        w = None
    if not w:
        return
    try:
        w.setProperty("selected", bool(selected))
        w.style().unpolish(w)
        w.style().polish(w)
        w.update()
    except Exception:
        pass


def set_preview_selected_zip_path(window, zip_path: str | None) -> None:
    prev = None
    try:
        prev = getattr(window, "_preview_selected_zip_path", None)
    except Exception:
        prev = None
    try:
        window._preview_selected_zip_path = str(zip_path) if zip_path else None
    except Exception:
        window._preview_selected_zip_path = None

    try:
        if prev and prev != getattr(window, "_preview_selected_zip_path", None):
            update_preview_case_item_selected_style(window, prev, False)
    except Exception:
        pass
    try:
        if getattr(window, "_preview_selected_zip_path", None):
            update_preview_case_item_selected_style(window, getattr(window, "_preview_selected_zip_path", None), True)
    except Exception:
        pass

    try:
        window.on_preview_case_selection_changed()
    except Exception:
        pass


def refresh_preview_case_list_ui(window, selected_path: str | None = None) -> None:
    layout = getattr(window, "preview_case_list_layout", None)
    if not layout:
        return

    try:
        if selected_path:
            window._preview_selected_zip_path = str(selected_path)
    except Exception:
        pass

    scroll = getattr(window, "preview_case_scroll", None)

    old_scroll_val = _get_scroll_value(scroll)

    try:
        window._preview_case_item_widgets = {}
    except Exception:
        pass

    _clear_layout(layout)

    filter_text = _get_filter_text(window)
    ft = filter_text.lower()
    is_searching = bool(ft)

    selected_zip = None
    try:
        selected_zip = getattr(window, "_preview_selected_zip_path", None)
    except Exception:
        selected_zip = None

    total_leaf = _count_total_leaf_cases(window)

    visible_leaf, visible_zip_paths, first_visible_zip = _build_preview_case_list_items(
        window,
        layout,
        ft=ft,
        is_searching=is_searching,
        selected_zip=selected_zip,
    )

    _add_preview_case_list_empty_state(layout, total_leaf, visible_leaf)

    try:
        layout.addStretch(1)
    except Exception:
        pass

    _update_preview_case_count_label(window, ft=ft, visible_leaf=visible_leaf, total_leaf=total_leaf)

    _fixup_preview_selected_zip_after_refresh(
        window,
        ft=ft,
        is_searching=is_searching,
        visible_zip_paths=visible_zip_paths,
        first_visible_zip=first_visible_zip,
    )

    try:
        window.on_preview_case_selection_changed()
    except Exception:
        pass

    try:
        if scroll is not None and old_scroll_val is not None:
            scroll.verticalScrollBar().setValue(int(old_scroll_val))
    except Exception:
        pass
