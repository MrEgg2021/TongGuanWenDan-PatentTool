from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class HighlightTabMixin:
    @classmethod
    def _infer_ui_domain(cls, rule_id: str) -> str:
        rid = str(rule_id or "")
        if rid.startswith("wordlist.claims.") or rid.startswith("claim.ref.") or rid.startswith("claim1.") or rid.startswith("claim.punctuation."):
            return "claims"
        if rid == "abstract.word_count.exceeded":
            return "abstract"
        if rid.startswith("wordlist.description.") or rid.startswith("description."):
            return "description"
        if rid.startswith("drawings."):
            return "drawings"
        return "general"

    @classmethod
    def _infer_ui_level(cls, rule_id: str) -> str:
        rid = str(rule_id or "")
        if rid.endswith(".forbidden"):
            return "forbid"
        if rid.endswith(".sensitive"):
            return "warn"
        if rid.startswith("description.") and ("missing" in rid or "exceeded" in rid):
            return "forbid"
        if rid in {"claim.ref.missing_target", "claim.ref.marker_basis.missing", "claim.ref.term_basis.missing"}:
            return "forbid"
        if rid.startswith("claim1.") and rid.endswith(".exceeded"):
            return "forbid"
        if rid == "abstract.word_count.exceeded":
            return "forbid"
        if rid in {
            "claim.ref.self",
            "claim.ref.future",
            "claim.ref.choice_word_missing",
            "claim.ref.multi_to_multi.recursive",
            "drawings.figure.ref.missing_in_impl",
            "text.repeated_word",
        }:
            return "warn"
        if rid.startswith("claim.punctuation.") or rid.startswith("punctuation."):
            return "warn"
        if rid.startswith("theme."):
            return "remind"
        return "warn"

    @classmethod
    def _normalize_rule_options(
        cls,
        options: list[dict[str, object] | tuple[str, str, str, str, bool]],
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for raw in list(options or []):
            if isinstance(raw, dict):
                rule_id = str(raw.get("rule_id") or "").strip()
                if not rule_id:
                    continue
                ui_level = str(raw.get("ui_level") or "").strip() or cls._infer_ui_level(rule_id)
                if ui_level not in cls._LEVEL_KEY_MAP:
                    ui_level = "warn"
                ui_domain = str(raw.get("ui_domain") or "").strip() or cls._infer_ui_domain(rule_id)
                if ui_domain not in cls._DOMAIN_LABELS:
                    ui_domain = "general"
                level_key = cls._LEVEL_KEY_MAP.get(ui_level, "level.warn")
                rows.append(
                    {
                        "rule_id": rule_id,
                        "label": str(raw.get("label") or rule_id),
                        "color_key": str(raw.get("color_key") or level_key),
                        "default_color": str(raw.get("default_color") or cls._LEVEL_DEFAULT_COLORS.get(ui_level, "#FFE082")),
                        "default_enabled": bool(raw.get("default_enabled", True)),
                        "ui_domain": ui_domain,
                        "ui_level": ui_level,
                    }
                )
                continue
            if not isinstance(raw, tuple) or len(raw) < 5:
                continue
            rule_id, label, color_key, default_color, default_enabled = raw[:5]
            rid = str(rule_id or "").strip()
            if not rid:
                continue
            ui_level = cls._infer_ui_level(rid)
            ui_domain = cls._infer_ui_domain(rid)
            level_key = cls._LEVEL_KEY_MAP.get(ui_level, "level.warn")
            rows.append(
                {
                    "rule_id": rid,
                    "label": str(label or rid),
                    "color_key": str(color_key or level_key),
                    "default_color": str(default_color or cls._LEVEL_DEFAULT_COLORS.get(ui_level, "#FFE082")),
                    "default_enabled": bool(default_enabled),
                    "ui_domain": ui_domain,
                    "ui_level": ui_level,
                }
            )
        return rows

    @classmethod
    def _level_label(cls, level: str) -> str:
        return cls._LEVEL_LABELS.get(str(level or ""), cls._LEVEL_LABELS["warn"])

    @classmethod
    def _level_color_key(cls, level: str) -> str:
        return cls._LEVEL_KEY_MAP.get(str(level or ""), cls._LEVEL_KEY_MAP["warn"])

    def _toggle_domain_section(self, domain: str, expanded: bool) -> None:
        button = self._domain_toggle_buttons.get(str(domain or ""))
        body = self._domain_bodies.get(str(domain or ""))
        if button is None or body is None:
            return
        body.setVisible(bool(expanded))
        arrow = "▼" if expanded else "▶"
        title = self._DOMAIN_LABELS.get(str(domain or ""), str(domain or "通用"))
        button.setText(f"{arrow} {title}")

    def _pick_level_color(self, level: str) -> None:
        edit = self._level_color_inputs.get(str(level or ""))
        if edit is None:
            return
        color = QColorDialog.getColor(QColor(edit.text() or "#FFE082"), self, "选择级别颜色")
        if not color.isValid():
            return
        edit.setText(color.name().upper())

    def _on_level_color_input_changed(self, level: str) -> None:
        key = str(level or "")
        edit = self._level_color_inputs.get(key)
        preview = self._level_color_preview_labels.get(key)
        if edit is None or preview is None:
            return
        fallback = self._LEVEL_DEFAULT_COLORS.get(key, "#FFE082")
        normalized = self._normalize_color(edit.text(), fallback)
        self._set_preview_color(preview, normalized)

    def _sync_rule_colors_from_levels(self) -> None:
        for rule_id, edit in self._color_inputs.items():
            level = str(self._rule_levels.get(rule_id, "warn") or "warn")
            level_edit = self._level_color_inputs.get(level)
            if level_edit is None:
                continue
            fallback = self._LEVEL_DEFAULT_COLORS.get(level, "#FFE082")
            normalized = self._normalize_color(level_edit.text(), fallback)
            edit.blockSignals(True)
            edit.setText(normalized)
            edit.blockSignals(False)
            preview = self._color_preview_labels.get(rule_id)
            if preview is not None:
                self._set_preview_color(preview, normalized)

    def _on_toggle_advanced_color_mode(self, checked: bool) -> None:
        panel = self._advanced_color_editor_panel
        if panel is not None:
            panel.setVisible(bool(checked))
        if checked:
            self._sync_rule_colors_from_levels()

    def _build_highlight_tab(
        self,
        highlight_colors: dict[str, str],
        rule_enabled: dict[str, bool],
        options: list[dict[str, object]],
    ) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        hint = QLabel("默认仅配置三级颜色。规则按分类折叠展示；可开启高级模式逐规则配色。")
        layout.addWidget(hint)

        card = QFrame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(10)

        level_box = QGroupBox("高亮颜色级别")
        level_grid = QGridLayout(level_box)
        level_grid.setContentsMargins(8, 8, 8, 8)
        level_grid.setHorizontalSpacing(8)
        level_grid.setVerticalSpacing(6)
        for row_idx, level in enumerate(("forbid", "warn", "remind")):
            level_label = QLabel(self._level_label(level))
            level_key = self._level_color_key(level)
            fallback = self._LEVEL_DEFAULT_COLORS.get(level, "#FFE082")
            current = self._normalize_color((highlight_colors or {}).get(level_key, fallback), fallback)
            value_input = QLineEdit(current)
            value_input.setPlaceholderText("#RRGGBB")
            pick_button = QPushButton("选择")
            preview = QLabel("    ")
            preview.setAutoFillBackground(True)
            self._set_preview_color(preview, current)

            pick_button.clicked.connect(lambda _=False, _level=level: self._pick_level_color(_level))
            value_input.textChanged.connect(lambda _=None, _level=level: self._on_level_color_input_changed(_level))

            self._level_color_inputs[level] = value_input
            self._level_color_preview_labels[level] = preview

            level_grid.addWidget(level_label, row_idx, 0)
            level_grid.addWidget(value_input, row_idx, 1)
            level_grid.addWidget(pick_button, row_idx, 2)
            level_grid.addWidget(preview, row_idx, 3)
        card_layout.addWidget(level_box)

        domain_groups: dict[str, list[dict[str, object]]] = {key: [] for key in self._DOMAIN_ORDER}
        for option in list(options or []):
            domain = str(option.get("ui_domain") or "general")
            if domain not in domain_groups:
                domain = "general"
            domain_groups[domain].append(option)

        rules_box = QGroupBox("规则开关（按分类折叠）")
        rules_layout = QVBoxLayout(rules_box)
        rules_layout.setContentsMargins(8, 8, 8, 8)
        rules_layout.setSpacing(6)
        for domain in self._DOMAIN_ORDER:
            rows = list(domain_groups.get(domain) or [])
            if not rows:
                continue
            section = QFrame()
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(4)

            toggle_button = QPushButton()
            toggle_button.setCheckable(True)
            toggle_button.setChecked(True)
            section_layout.addWidget(toggle_button)
            self._domain_toggle_buttons[domain] = toggle_button

            body = QFrame()
            body_layout = QVBoxLayout(body)
            body_layout.setContentsMargins(12, 0, 0, 0)
            body_layout.setSpacing(4)
            self._domain_bodies[domain] = body

            for option in rows:
                rule_id = str(option.get("rule_id") or "")
                color_key = str(option.get("color_key") or "default")
                ui_level = str(option.get("ui_level") or "warn")
                default_color = str(option.get("default_color") or self._LEVEL_DEFAULT_COLORS.get(ui_level, "#FFE082"))
                default_enabled = bool(option.get("default_enabled", True))
                current_color = self._normalize_color(
                    (highlight_colors or {}).get(rule_id, (highlight_colors or {}).get(color_key, default_color)),
                    default_color,
                )

                self._rule_levels[rule_id] = ui_level
                self._rule_color_keys[rule_id] = color_key
                self._rule_defaults[rule_id] = default_color

                row_widget = QFrame()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(6)

                enabled_check = QCheckBox("启用")
                enabled_check.setChecked(bool((rule_enabled or {}).get(rule_id, default_enabled)))
                self._rule_enabled_checks[rule_id] = enabled_check
                row_layout.addWidget(enabled_check)

                name_label = QLabel(str(option.get("label") or rule_id))
                row_layout.addWidget(name_label, 1)

                level_label = QLabel(f"级别：{self._level_label(ui_level)}")
                level_label.setStyleSheet("QLabel { color: #64748B; }")
                row_layout.addWidget(level_label)

                value_input = QLineEdit(current_color)
                value_input.setPlaceholderText("#RRGGBB")
                preview = QLabel("    ")
                preview.setAutoFillBackground(True)
                self._set_preview_color(preview, current_color)
                value_input.textChanged.connect(lambda _=None, _rule_id=rule_id: self._on_color_input_changed(_rule_id))
                self._color_inputs[rule_id] = value_input
                self._color_preview_labels[rule_id] = preview

                body_layout.addWidget(row_widget)

            section_layout.addWidget(body)
            rules_layout.addWidget(section)

            toggle_button.toggled.connect(lambda checked, _domain=domain: self._toggle_domain_section(_domain, checked))
            self._toggle_domain_section(domain, True)
        card_layout.addWidget(rules_box)

        self._advanced_color_mode_check = QCheckBox("显示高级逐规则配色")
        self._advanced_color_mode_check.setChecked(False)
        self._advanced_color_mode_check.toggled.connect(self._on_toggle_advanced_color_mode)
        card_layout.addWidget(self._advanced_color_mode_check)

        advanced_box = QGroupBox("高级逐规则配色")
        advanced_grid = QGridLayout(advanced_box)
        advanced_grid.setContentsMargins(8, 8, 8, 8)
        advanced_grid.setHorizontalSpacing(8)
        advanced_grid.setVerticalSpacing(6)
        for row_idx, option in enumerate(list(options or [])):
            rule_id = str(option.get("rule_id") or "")
            advanced_grid.addWidget(QLabel(str(option.get("label") or rule_id)), row_idx, 0)
            advanced_grid.addWidget(self._color_inputs[rule_id], row_idx, 1)
            pick_btn = QPushButton("选择")
            pick_btn.clicked.connect(lambda _=False, _rule_id=rule_id: self._pick_color(_rule_id))
            advanced_grid.addWidget(pick_btn, row_idx, 2)
            advanced_grid.addWidget(self._color_preview_labels[rule_id], row_idx, 3)
        advanced_box.setVisible(False)
        self._advanced_color_editor_panel = advanced_box
        card_layout.addWidget(advanced_box)
        card_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(card)
        layout.addWidget(scroll, 1)
        return tab


    @staticmethod
    def _normalize_color(value: str, fallback: str) -> str:
        text = str(value or "").strip()
        if not text.startswith("#"):
            text = f"#{text}"
        if QColor(text).isValid():
            return text.upper()
        return str(fallback or "#FFF59D")

    def _set_preview_color(self, label: QLabel, color_text: str) -> None:
        color = self._normalize_color(color_text, "#FFF59D")
        label.setStyleSheet(
            f"QLabel {{ border: 1px solid #CBD5E1; border-radius: 4px; background-color: {color}; }}"
        )

    def _on_color_input_changed(self, rule_id: str) -> None:
        edit = self._color_inputs.get(rule_id)
        preview = self._color_preview_labels.get(rule_id)
        if edit is None or preview is None:
            return
        fallback = self._rule_defaults.get(rule_id, "#FFE082")
        normalized = self._normalize_color(edit.text(), fallback)
        self._set_preview_color(preview, normalized)

    def _pick_color(self, rule_id: str) -> None:
        edit = self._color_inputs.get(rule_id)
        if edit is None:
            return
        fallback = self._rule_defaults.get(rule_id, "#FFE082")
        color = QColorDialog.getColor(QColor(edit.text() or fallback), self, "选择高亮颜色")
        if not color.isValid():
            return
        edit.setText(color.name().upper())

    def _reset_colors_to_default(self) -> None:
        for level, edit in self._level_color_inputs.items():
            fallback = self._LEVEL_DEFAULT_COLORS.get(level, "#FFE082")
            edit.setText(str(fallback).upper())
        for rule_id, edit in self._color_inputs.items():
            fallback = self._rule_defaults.get(rule_id, "#FFE082")
            edit.setText(str(fallback).upper())
        advanced_mode = bool(self._advanced_color_mode_check is not None and self._advanced_color_mode_check.isChecked())
        if not advanced_mode:
            self._sync_rule_colors_from_levels()
