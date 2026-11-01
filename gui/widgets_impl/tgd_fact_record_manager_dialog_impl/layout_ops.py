from __future__ import annotations

import json
import os
import shutil

from PySide6.QtWidgets import QHeaderView, QTableWidget

from core.paths_utils import get_user_data_dir
from core.tgd_data_management_impl.infra import get_db_path
from gui.widgets_impl.tgd_fact_record_manager_layout_ops import load_layout_state
from gui.widgets_impl.tgd_fact_record_manager_utils import _norm_text


class _LayoutOpsMixin:
    def _ensure_fact_tables_last_visible_stretch(self) -> None:
        def _apply(tbl: QTableWidget | None) -> None:
            if tbl is None:
                return
            try:
                h = tbl.horizontalHeader()
                try:
                    h.setStretchLastSection(False)
                except Exception:
                    pass

                last_visible_logical: int | None = None
                for v in range(int(h.count()) - 1, -1, -1):
                    li = int(h.logicalIndex(v))
                    if li >= 0 and not bool(h.isSectionHidden(li)):
                        last_visible_logical = li
                        break
                if last_visible_logical is None:
                    return

                try:
                    h.setSectionResizeMode(0, QHeaderView.Fixed)
                except Exception:
                    pass

                if int(last_visible_logical) == 0:
                    return

                try:
                    h.setSectionResizeMode(int(last_visible_logical), QHeaderView.Stretch)
                except Exception:
                    pass

                for li in range(int(h.count())):
                    if li == 0 or li == int(last_visible_logical):
                        continue
                    try:
                        if int(h.sectionResizeMode(li)) == int(QHeaderView.Stretch):
                            h.setSectionResizeMode(li, QHeaderView.Interactive)
                    except Exception:
                        pass
            except Exception:
                pass

        _apply(self.fact_table_left)
        _apply(self.fact_table_right)

    def _enable_layout_save(self) -> None:
        try:
            self._layout_save_enabled = True
        except Exception:
            pass

    def _get_layout_config_path(self) -> str:
        base = get_user_data_dir()
        try:
            os.makedirs(base, exist_ok=True)
        except Exception:
            pass
        new_path = os.path.join(base, "fact_manager_layout.json")

        try:
            if not os.path.exists(new_path):
                db_path = get_db_path()
                old_path = os.path.join(os.path.dirname(db_path), "fact_manager_layout.json")
                if os.path.exists(old_path):
                    try:
                        shutil.copy2(old_path, new_path)
                    except Exception:
                        pass
        except Exception:
            pass

        return new_path

    def _get_table_layout_signature(self, tbl: QTableWidget) -> dict:
        try:
            h = tbl.horizontalHeader()
            labels: list[str] = []
            for i in range(h.count()):
                it = tbl.horizontalHeaderItem(i)
                labels.append(_norm_text(it.text()) if it else "")
            return {"count": int(h.count()), "labels": labels}
        except Exception:
            return {"count": 0, "labels": []}

    def _save_layout_state(self, *, force: bool = False) -> None:
        if (not bool(force)) and (not bool(getattr(self, "_layout_save_enabled", True))):
            return
        if (not bool(force)) and bool(getattr(self, "_embedded", False)):
            try:
                if not bool(self.isVisible()):
                    return
            except Exception:
                return
        try:
            config = {}
            for name, tbl in [("fact_left", self.fact_table_left), ("fact_right", self.fact_table_right), ("agency", self.agency_table)]:
                if tbl:
                    h = tbl.horizontalHeader()
                    order = []
                    widths = []
                    try:
                        order = [int(h.logicalIndex(v)) for v in range(int(h.count()))]
                        widths = [int(h.sectionSize(i)) for i in range(int(h.count()))]
                    except Exception:
                        order = []
                        widths = []
                    config[name] = {
                        "state": h.saveState().toHex().data().decode(),
                        "hidden": [h.isSectionHidden(i) for i in range(h.count())],
                        "signature": self._get_table_layout_signature(tbl),
                        "order": order,
                        "widths": widths,
                    }
            if hasattr(self, "splitter") and self.splitter:
                config["splitter"] = self.splitter.sizes()

            path = self._get_layout_config_path()
            try:
                parent = os.path.dirname(path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
            except Exception:
                pass

            with open(path, "w", encoding="utf-8") as f:
                json.dump(config, f)
        except Exception:
            pass

    def _load_layout_state(self) -> tuple[bool, bool]:
        return load_layout_state(self)
