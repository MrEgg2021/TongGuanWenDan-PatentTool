from __future__ import annotations

from core.user_messages import user_error_text

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.formal_review.wordlists import (
    DEFAULT_WORDLISTS_V2,
    FULL_PRESET_PROFILE_NAME,
    FULL_PRESET_WORDLISTS_V2,
    SLIM_DEFAULT_PROFILE_NAME,
    normalize_wordlists,
)


class WordlistTabMixin:
    @staticmethod
    def _normalize_profile_name(name: str) -> str:
        return str(name or "").strip()

    @staticmethod
    def _dedupe_profile_name(name: str, existing: dict[str, object]) -> str:
        base = str(name or "").strip() or "未命名"
        if base not in existing:
            return base
        idx = 1
        while True:
            candidate = f"{base} ({idx})"
            if candidate not in existing:
                return candidate
            idx += 1

    def _refresh_profile_combo(self, *, select_name: str | None = None) -> None:
        combo = getattr(self, "_profile_combo", None)
        if combo is None:
            return
        current = str(select_name or "") or str(getattr(self, "_active_profile", "") or "")
        names = list((getattr(self, "_profiles", {}) or {}).keys())
        combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItems(names)
            idx = combo.findText(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        finally:
            combo.blockSignals(False)

    def _collect_wordlists_from_edits(self) -> dict[str, dict[str, list[str]]]:
        claims_forbidden = self._normalize_text_rows(self._claims_forbidden_edit.toPlainText())
        claims_sensitive = self._normalize_text_rows(self._claims_sensitive_edit.toPlainText())
        description_forbidden = self._normalize_text_rows(self._description_forbidden_edit.toPlainText())
        description_sensitive = self._normalize_text_rows(self._description_sensitive_edit.toPlainText())
        return {
            "claims": {"forbidden": claims_forbidden, "sensitive": claims_sensitive},
            "description": {"forbidden": description_forbidden, "sensitive": description_sensitive},
        }

    def _apply_wordlists_to_edits(self, wordlists: dict[str, dict[str, list[str]]]) -> None:
        wordlists = normalize_wordlists(wordlists)
        claims_bucket = dict(wordlists.get("claims") or {})
        description_bucket = dict(wordlists.get("description") or {})
        self._claims_forbidden_edit.setPlainText("\n".join(list(claims_bucket.get("forbidden") or [])))
        self._claims_sensitive_edit.setPlainText("\n".join(list(claims_bucket.get("sensitive") or [])))
        self._description_forbidden_edit.setPlainText("\n".join(list(description_bucket.get("forbidden") or [])))
        self._description_sensitive_edit.setPlainText("\n".join(list(description_bucket.get("sensitive") or [])))
        self._refresh_wordlist_count_labels()

    def _refresh_wordlist_count_labels(self) -> None:
        labels = getattr(self, "_wordlist_count_labels", {})
        if not isinstance(labels, dict):
            return
        for attr_name, payload in labels.items():
            if not isinstance(payload, tuple) or len(payload) != 2:
                continue
            label, hint = payload
            editor = getattr(self, str(attr_name), None)
            if label is None or editor is None:
                continue
            count = len(self._normalize_text_rows(editor.toPlainText()))
            label.setText(f"{hint}（每行一个，当前 {count} 个）")

    def _store_current_profile_edits(self) -> None:
        name = str(getattr(self, "_active_profile", "") or "").strip()
        if not name:
            return
        profiles = getattr(self, "_profiles", {})
        if not isinstance(profiles, dict) or name not in profiles:
            return
        profiles[name] = normalize_wordlists(self._collect_wordlists_from_edits())
        self._profiles = profiles

    def _switch_to_profile(self, name: str) -> None:
        profiles = getattr(self, "_profiles", {})
        if not isinstance(profiles, dict):
            profiles = {}
        target = self._normalize_profile_name(name)
        if not target or target not in profiles:
            return
        self._store_current_profile_edits()
        self._active_profile = target
        self._apply_wordlists_to_edits(dict(profiles.get(target) or {}))

    def _on_profile_combo_changed(self, name: str) -> None:
        self._switch_to_profile(name)

    def _on_use_builtin_profile(self, name: str, wordlists: dict[str, dict[str, list[str]]]) -> None:
        self._store_current_profile_edits()
        profiles = dict(getattr(self, "_profiles", {}) or {})
        target = self._normalize_profile_name(name)
        if not target:
            return
        if target not in profiles:
            profiles[target] = normalize_wordlists(wordlists)
            self._profiles = profiles
        self._refresh_profile_combo(select_name=target)
        self._switch_to_profile(target)

    def _on_new_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "新建词库方案", "请输入方案名称：")
        if not ok:
            return
        base = self._normalize_profile_name(name)
        if not base:
            QMessageBox.information(self, "词库方案", "方案名称不能为空。")
            return
        self._store_current_profile_edits()
        profiles = dict(getattr(self, "_profiles", {}) or {})
        new_name = self._dedupe_profile_name(base, profiles)
        current_payload = dict(profiles.get(str(getattr(self, "_active_profile", "") or "")) or {})
        profiles[new_name] = normalize_wordlists(current_payload)
        self._profiles = profiles
        self._active_profile = new_name
        self._refresh_profile_combo(select_name=new_name)
        self._apply_wordlists_to_edits(dict(profiles.get(new_name) or {}))

    def _on_rename_profile(self) -> None:
        current = str(getattr(self, "_active_profile", "") or "").strip()
        if not current:
            return
        name, ok = QInputDialog.getText(self, "重命名词库方案", "请输入新的方案名称：", text=current)
        if not ok:
            return
        new_name = self._normalize_profile_name(name)
        if not new_name:
            QMessageBox.information(self, "词库方案", "方案名称不能为空。")
            return
        profiles = dict(getattr(self, "_profiles", {}) or {})
        if new_name in profiles and new_name != current:
            QMessageBox.information(self, "词库方案", f"方案名已存在：{new_name}")
            return
        if new_name == current:
            return
        self._store_current_profile_edits()
        payload = profiles.pop(current, {})
        profiles[new_name] = payload
        self._profiles = profiles
        self._active_profile = new_name
        self._refresh_profile_combo(select_name=new_name)

    def _on_delete_profile(self) -> None:
        current = str(getattr(self, "_active_profile", "") or "").strip()
        profiles = dict(getattr(self, "_profiles", {}) or {})
        if not current or current not in profiles:
            return
        if len(list(profiles.keys())) <= 1:
            QMessageBox.information(self, "词库方案", "至少需要保留一个词库方案。")
            return
        answer = QMessageBox.question(
            self,
            "删除词库方案",
            f"确定删除方案“{current}”？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._store_current_profile_edits()
        profiles.pop(current, None)
        next_name = next(iter(profiles.keys()))
        self._profiles = profiles
        self._active_profile = next_name
        self._refresh_profile_combo(select_name=next_name)
        self._apply_wordlists_to_edits(dict(profiles.get(next_name) or {}))

    def _load_json_file(self, path: str) -> object:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_json_file(self, path: str, payload: object) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")

    def _import_profiles_from_json(self, path: str, payload: object) -> list[str]:
        imported_names: list[str] = []
        profiles = dict(getattr(self, "_profiles", {}) or {})
        stem = Path(path).stem
        if isinstance(payload, dict) and str(payload.get("schema") or "") == "formal_review.wordlist_profile.v1":
            name = self._normalize_profile_name(str(payload.get("name") or stem))
            wordlists = payload.get("wordlists")
            final_name = self._dedupe_profile_name(name, profiles)
            profiles[final_name] = normalize_wordlists(wordlists)
            imported_names.append(final_name)
        elif isinstance(payload, dict) and str(payload.get("schema") or "") == "formal_review.wordlist_profiles.v1":
            raw_profiles = payload.get("profiles")
            if isinstance(raw_profiles, dict):
                for name, wordlists in raw_profiles.items():
                    if not isinstance(name, str):
                        continue
                    base = self._normalize_profile_name(name)
                    if not base:
                        continue
                    final_name = self._dedupe_profile_name(base, profiles)
                    profiles[final_name] = normalize_wordlists(wordlists)
                    imported_names.append(final_name)
        else:
            final_name = self._dedupe_profile_name(self._normalize_profile_name(stem), profiles)
            profiles[final_name] = normalize_wordlists(payload)
            imported_names.append(final_name)
        self._profiles = profiles
        return imported_names

    def _on_import_profiles(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入词库方案", "", "JSON (*.json)")
        if not path:
            return
        self._store_current_profile_edits()
        try:
            payload = self._load_json_file(path)
            imported = self._import_profiles_from_json(path, payload)
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", user_error_text(f"读取/解析 JSON 失败：\n{exc}"))
            return
        if not imported:
            QMessageBox.information(self, "导入词库方案", "未导入任何方案。")
            return
        select_name = imported[0] if len(imported) == 1 else str(getattr(self, "_active_profile", "") or "")
        self._refresh_profile_combo(select_name=select_name)
        if select_name:
            self._switch_to_profile(select_name)
        QMessageBox.information(self, "导入词库方案", f"导入成功：{', '.join(imported)}")

    def _on_export_current_profile(self) -> None:
        self._store_current_profile_edits()
        current = str(getattr(self, "_active_profile", "") or "").strip() or "默认"
        path, _ = QFileDialog.getSaveFileName(self, "导出当前词库方案", f"{current}.json", "JSON (*.json)")
        if not path:
            return
        profiles = dict(getattr(self, "_profiles", {}) or {})
        payload = {
            "schema": "formal_review.wordlist_profile.v1",
            "name": current,
            "wordlists": dict(profiles.get(current) or {}),
        }
        try:
            self._write_json_file(path, payload)
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", user_error_text(f"写入文件失败：\n{exc}"))
            return
        QMessageBox.information(self, "导出成功", f"已导出到：\n{path}")

    def _on_export_all_profiles(self) -> None:
        self._store_current_profile_edits()
        path, _ = QFileDialog.getSaveFileName(self, "导出全部词库方案", "formal_review_wordlists.json", "JSON (*.json)")
        if not path:
            return
        profiles = dict(getattr(self, "_profiles", {}) or {})
        payload = {
            "schema": "formal_review.wordlist_profiles.v1",
            "active": str(getattr(self, "_active_profile", "") or "").strip() or "默认",
            "profiles": profiles,
        }
        try:
            self._write_json_file(path, payload)
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", user_error_text(f"写入文件失败：\n{exc}"))
            return
        QMessageBox.information(self, "导出成功", f"已导出到：\n{path}")

    def _build_wordlist_tab(
        self,
        wordlist_profiles: dict[str, dict[str, dict[str, list[str]]]],
        active_wordlist_profile: str,
    ) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self._wordlist_count_labels: dict[str, tuple[QLabel, str]] = {}

        profiles: dict[str, dict[str, dict[str, list[str]]]] = {}
        for name, payload in dict(wordlist_profiles or {}).items():
            if not isinstance(name, str):
                continue
            key = self._normalize_profile_name(name)
            if not key:
                continue
            profiles[key] = normalize_wordlists(payload)
        if not profiles:
            profiles[SLIM_DEFAULT_PROFILE_NAME] = normalize_wordlists(DEFAULT_WORDLISTS_V2)
            profiles[FULL_PRESET_PROFILE_NAME] = normalize_wordlists(FULL_PRESET_WORDLISTS_V2)
        active = self._normalize_profile_name(active_wordlist_profile) or SLIM_DEFAULT_PROFILE_NAME
        if active not in profiles:
            active = next(iter(profiles.keys()))

        self._profiles = profiles
        self._active_profile = active

        guidance = QLabel("当前词库会直接影响形式审查命中；精简默认偏低误报，严格预设偏高覆盖，可按业务习惯自行增删。")
        guidance.setWordWrap(True)
        layout.addWidget(guidance)

        toolbar = QFrame()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)
        toolbar_layout.addWidget(QLabel("当前方案："))
        self._profile_combo = QComboBox()
        self._profile_combo.addItems(list(profiles.keys()))
        self._profile_combo.setCurrentText(active)
        self._profile_combo.currentTextChanged.connect(self._on_profile_combo_changed)
        toolbar_layout.addWidget(self._profile_combo, 1)

        btn_new = QPushButton("新建")
        btn_rename = QPushButton("重命名")
        btn_delete = QPushButton("删除")
        btn_import = QPushButton("导入")
        btn_export_one = QPushButton("导出当前")
        btn_export_all = QPushButton("导出全部")
        btn_slim = QPushButton("使用精简默认")
        btn_full = QPushButton("使用严格预设")
        for button in (btn_new, btn_rename, btn_delete, btn_import, btn_export_one, btn_export_all, btn_slim, btn_full):
            toolbar_layout.addWidget(button)
        btn_new.clicked.connect(self._on_new_profile)
        btn_rename.clicked.connect(self._on_rename_profile)
        btn_delete.clicked.connect(self._on_delete_profile)
        btn_import.clicked.connect(self._on_import_profiles)
        btn_export_one.clicked.connect(self._on_export_current_profile)
        btn_export_all.clicked.connect(self._on_export_all_profiles)
        btn_slim.clicked.connect(lambda _=False: self._on_use_builtin_profile(SLIM_DEFAULT_PROFILE_NAME, DEFAULT_WORDLISTS_V2))
        btn_full.clicked.connect(lambda _=False: self._on_use_builtin_profile(FULL_PRESET_PROFILE_NAME, FULL_PRESET_WORDLISTS_V2))
        layout.addWidget(toolbar)

        def _build_wordlist_column(title: str, hint: str, attr_name: str) -> QGroupBox:
            box = QGroupBox(title)
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(8, 8, 8, 8)
            box_layout.setSpacing(6)
            hint_label = QLabel()
            box_layout.addWidget(hint_label)
            editor = QPlainTextEdit()
            setattr(self, attr_name, editor)
            self._wordlist_count_labels[attr_name] = (hint_label, hint)
            editor.textChanged.connect(self._refresh_wordlist_count_labels)
            box_layout.addWidget(editor, 1)
            return box

        top_splitter = QSplitter(Qt.Horizontal)
        top_splitter.setChildrenCollapsible(False)
        top_splitter.addWidget(_build_wordlist_column("权利要求禁用词库", "禁用词", "_claims_forbidden_edit"))
        top_splitter.addWidget(_build_wordlist_column("权利要求敏感词库", "敏感词", "_claims_sensitive_edit"))
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 1)
        top_splitter.setSizes([420, 420])

        bottom_splitter = QSplitter(Qt.Horizontal)
        bottom_splitter.setChildrenCollapsible(False)
        bottom_splitter.addWidget(_build_wordlist_column("说明书禁用词库", "禁用词", "_description_forbidden_edit"))
        bottom_splitter.addWidget(_build_wordlist_column("说明书敏感词库", "敏感词", "_description_sensitive_edit"))
        bottom_splitter.setStretchFactor(0, 1)
        bottom_splitter.setStretchFactor(1, 1)
        bottom_splitter.setSizes([420, 420])

        wordlist_splitter = QSplitter(Qt.Vertical)
        wordlist_splitter.setChildrenCollapsible(False)
        wordlist_splitter.addWidget(top_splitter)
        wordlist_splitter.addWidget(bottom_splitter)
        wordlist_splitter.setStretchFactor(0, 1)
        wordlist_splitter.setStretchFactor(1, 1)
        wordlist_splitter.setSizes([260, 260])
        layout.addWidget(wordlist_splitter, 1)

        self._apply_wordlists_to_edits(dict(profiles.get(active) or {}))
        return tab
