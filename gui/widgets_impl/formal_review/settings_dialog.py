from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.formal_review.wordlists import normalize_wordlists
from gui.widgets_impl.formal_review.settings_dialog_parts import HighlightTabMixin, WordlistTabMixin


class FormalReviewSettingsDialog(WordlistTabMixin, HighlightTabMixin, QDialog):
    _LEVEL_KEY_MAP = {
        "forbid": "level.forbid",
        "warn": "level.warn",
        "remind": "level.remind",
    }
    _LEVEL_LABELS = {
        "forbid": "禁止级别",
        "warn": "警告级别",
        "remind": "提醒级别",
    }
    _LEVEL_DEFAULT_COLORS = {
        "forbid": "#FFCDD2",
        "warn": "#FFE082",
        "remind": "#C8E6C9",
    }
    _DOMAIN_ORDER = ("claims", "abstract", "description", "drawings", "general")
    _DOMAIN_LABELS = {
        "claims": "与权利要求书相关的",
        "abstract": "与说明书摘要相关的",
        "description": "与说明书相关的",
        "drawings": "与说明书附图相关的",
        "general": "通用",
    }

    def __init__(
        self,
        parent=None,
        *,
        wordlist_profiles: dict[str, dict[str, dict[str, list[str]]]],
        active_wordlist_profile: str,
        rule_params: dict[str, object],
        comment_author: str,
        highlight_colors: dict[str, str],
        rule_enabled: dict[str, bool],
        rule_options: Iterable[dict[str, object] | tuple[str, str, str, str, bool]],
    ):
        super().__init__(parent)
        self.setWindowTitle("形式审查设置")
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setSizeGripEnabled(True)
        self.setMinimumSize(860, 620)
        self.resize(980, 700)

        self._level_color_inputs: dict[str, QLineEdit] = {}
        self._level_color_preview_labels: dict[str, QLabel] = {}
        self._rule_defaults: dict[str, str] = {}
        self._rule_levels: dict[str, str] = {}
        self._rule_color_keys: dict[str, str] = {}
        self._color_inputs: dict[str, QLineEdit] = {}
        self._color_preview_labels: dict[str, QLabel] = {}
        self._rule_enabled_checks: dict[str, QCheckBox] = {}
        self._domain_toggle_buttons: dict[str, QPushButton] = {}
        self._domain_bodies: dict[str, QWidget] = {}
        self._advanced_color_mode_check: QCheckBox | None = None
        self._advanced_color_editor_panel: QWidget | None = None
        self._rule_options = self._normalize_rule_options(list(rule_options))

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        tabs = QTabWidget()
        tabs.setDocumentMode(False)
        try:
            tabs.tabBar().setExpanding(False)
            tabs.tabBar().setUsesScrollButtons(True)
        except Exception:
            pass
        tabs.addTab(self._build_wordlist_tab(wordlist_profiles, active_wordlist_profile), "词库管理")
        tabs.addTab(self._build_rule_params_tab(rule_params), "高级规则")
        tabs.addTab(self._build_comment_tab(comment_author), "批注与导出")
        tabs.addTab(self._build_highlight_tab(highlight_colors, rule_enabled, self._rule_options), "高亮颜色")
        root.addWidget(tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        reset_button = QPushButton("恢复默认颜色")
        buttons.addButton(reset_button, QDialogButtonBox.ActionRole)
        save_button = buttons.button(QDialogButtonBox.Save)
        cancel_button = buttons.button(QDialogButtonBox.Cancel)
        if save_button is not None:
            save_button.setText("保存")
        if cancel_button is not None:
            cancel_button.setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        reset_button.clicked.connect(self._reset_colors_to_default)
        root.addWidget(buttons)

    def _build_comment_tab(self, comment_author: str) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        card = QFrame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(6)

        card_layout.addWidget(QLabel("批注作者（伴侣模式写入批注时使用）"))
        self._comment_author_edit = QLineEdit()
        self._comment_author_edit.setPlaceholderText("例如：Dandan")
        self._comment_author_edit.setText(str(comment_author or "").strip())
        self._comment_author_edit.setMaximumWidth(420)
        card_layout.addWidget(self._comment_author_edit)

        card_layout.addWidget(QLabel("说明：批注同步仅在 Word 伴侣模式生效，纯文本模式不写入 Word。"))
        card_layout.addWidget(QLabel("伴侣审查会自动同步工具批注（只覆盖工具批注，不影响人工批注）。"))
        card_layout.addWidget(QLabel("伴侣模式“开始审查”前必须先删除全部批注、接受所有修订并关闭修订模式，然后保存。否则工具会阻断。"))
        card_layout.addWidget(QLabel("修改前会核对原文；无法安全修改的项目会提示，结果可能部分完成。"))

        layout.addWidget(card)
        layout.addStretch(1)
        return tab

    @staticmethod
    def _coerce_positive_int(value: str, *, fallback: int) -> int:
        try:
            parsed = int(str(value or "").strip())
        except Exception:
            return int(fallback)
        if parsed <= 0:
            return int(fallback)
        return int(parsed)

    def _build_rule_params_tab(self, rule_params: dict[str, object]) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        params = dict(rule_params or {})
        claim1_word_limit = self._coerce_positive_int(str(params.get("claim1_word_limit", 500)), fallback=500)
        claim1_marker_limit = self._coerce_positive_int(str(params.get("claim1_marker_limit", 20)), fallback=20)
        refer_words_extra = list(params.get("refer_words_extra") or [])

        card = QFrame()
        card_layout = QGridLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setHorizontalSpacing(8)
        card_layout.setVerticalSpacing(8)

        card_layout.addWidget(QLabel("权利要求1字数上限"), 0, 0)
        self._claim1_word_limit_edit = QLineEdit(str(claim1_word_limit))
        self._claim1_word_limit_edit.setPlaceholderText("例如：500")
        self._claim1_word_limit_edit.setMaximumWidth(240)
        card_layout.addWidget(self._claim1_word_limit_edit, 0, 1)

        card_layout.addWidget(QLabel("权利要求1去重附图标记数上限"), 1, 0)
        self._claim1_marker_limit_edit = QLineEdit(str(claim1_marker_limit))
        self._claim1_marker_limit_edit.setPlaceholderText("例如：20")
        self._claim1_marker_limit_edit.setMaximumWidth(240)
        card_layout.addWidget(self._claim1_marker_limit_edit, 1, 1)

        card_layout.addWidget(QLabel("“所述类词语”扩展词表（每行一个）"), 2, 0, 1, 2)
        self._refer_words_extra_edit = QPlainTextEdit()
        self._refer_words_extra_edit.setPlaceholderText("例如：本发明所述")
        self._refer_words_extra_edit.setPlainText("\n".join([str(item) for item in refer_words_extra if str(item).strip()]))
        card_layout.addWidget(self._refer_words_extra_edit, 3, 0, 1, 2)

        layout.addWidget(card, 1)
        layout.addWidget(QLabel("提示：是否启用对应规则，请在“高亮颜色”页勾选规则开关。"))
        layout.addStretch(1)
        return tab

    @staticmethod
    def _normalize_text_rows(text: str) -> list[str]:
        rows: list[str] = []
        seen: set[str] = set()
        for line in (text or "").splitlines():
            value = str(line or "").strip()
            if not value:
                continue
            key = value.casefold()
            if key in seen:
                continue
            rows.append(value)
            seen.add(key)
        return rows

    def data(self) -> dict[str, object]:
        self._store_current_profile_edits()
        profiles = dict(getattr(self, "_profiles", {}) or {})
        active_profile = str(getattr(self, "_active_profile", "") or "").strip() or "默认"
        current_wordlists = normalize_wordlists(profiles.get(active_profile))

        level_colors: dict[str, str] = {}
        for level, key in self._LEVEL_KEY_MAP.items():
            edit = self._level_color_inputs.get(level)
            fallback = self._LEVEL_DEFAULT_COLORS.get(level, "#FFE082")
            current = edit.text() if edit is not None else fallback
            level_colors[level] = self._normalize_color(current, fallback)

        colors: dict[str, str] = {
            "default": "#E0E0E0",
            "selected": "#90CAF9",
        }
        for level, key in self._LEVEL_KEY_MAP.items():
            colors[key] = level_colors[level]

        advanced_mode = bool(self._advanced_color_mode_check is not None and self._advanced_color_mode_check.isChecked())
        enabled: dict[str, bool] = {}
        for rule_id, input_edit in self._color_inputs.items():
            level = str(self._rule_levels.get(rule_id, "warn") or "warn")
            level_fallback = self._LEVEL_DEFAULT_COLORS.get(level, "#FFE082")
            level_color = level_colors.get(level, level_fallback)
            color_key = str(self._rule_color_keys.get(rule_id, "default") or "default")
            fallback = str(self._rule_defaults.get(rule_id, level_color) or level_color)
            if advanced_mode:
                normalized = self._normalize_color(input_edit.text(), fallback)
            else:
                normalized = self._normalize_color(level_color, fallback)
            colors[rule_id] = normalized
            if color_key not in colors:
                colors[color_key] = normalized
            enabled[rule_id] = bool(self._rule_enabled_checks.get(rule_id).isChecked()) if rule_id in self._rule_enabled_checks else True

        claim1_word_limit_edit = getattr(self, "_claim1_word_limit_edit", None)
        claim1_marker_limit_edit = getattr(self, "_claim1_marker_limit_edit", None)
        refer_words_extra_edit = getattr(self, "_refer_words_extra_edit", None)

        claim1_word_limit_text = str(claim1_word_limit_edit.text() if claim1_word_limit_edit is not None else "")
        claim1_marker_limit_text = str(claim1_marker_limit_edit.text() if claim1_marker_limit_edit is not None else "")
        refer_words_extra_text = str(refer_words_extra_edit.toPlainText() if refer_words_extra_edit is not None else "")

        return {
            "active_wordlist_profile": active_profile,
            "wordlist_profiles": profiles,
            "wordlists": current_wordlists,
            "rule_params": {
                "claim1_word_limit": self._coerce_positive_int(
                    claim1_word_limit_text,
                    fallback=500,
                ),
                "claim1_marker_limit": self._coerce_positive_int(
                    claim1_marker_limit_text,
                    fallback=20,
                ),
                "refer_words_extra": self._normalize_text_rows(refer_words_extra_text),
            },
            "comment_author": str(self._comment_author_edit.text() or "").strip(),
            "highlight_colors": colors,
            "rule_enabled": enabled,
        }

    def get_settings_payload(self) -> dict[str, object]:
        return self.data()
