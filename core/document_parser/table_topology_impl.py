from __future__ import annotations
from typing import Tuple, Optional

from core.logging_utils import logger

# Word Constants
wdLineStyleNone = 0
wdLineStyleSingle = 1
# Word Border Constants (WdBorderType enumeration)
# 本模块实际只使用 Top/Bottom；Word 的 Left(-2)/Right(-4) 未使用，故不定义
wdBorderTop = -1
wdBorderBottom = -3
CUT_BORDER_POLICY_OPEN = "open"
CUT_BORDER_POLICY_CLOSED = "closed"

class TableTopologyScanner:
    """
    负责分析表格的拓扑结构（合并单元格、行高系数），并计算最佳切分点。
    不直接操作 Word 界面，只进行数据分析和计算。
    """

    def __init__(self, table):
        self.table = table
        self._col_count = 0
        try:
            self._col_count = int(table.Columns.Count)
        except Exception:
            pass

    def find_safe_cut_row(self, target_row_idx: int, search_radius: int = 5, working_table=None) -> int:
        """
        在 target_row_idx 附近寻找最近的安全切割行。
        优先向上找，再向下找。
        
        Args:
            target_row_idx: 目标切割行号
            search_radius: 搜索半径
            working_table: 可选，画布中的工作表格。如果提供，则使用它代替 self.table
        """
        table_to_check = working_table if working_table is not None else self.table
        
        # 1. 检查 target_row_idx 本身是否安全
        if self._is_row_safe(target_row_idx, table_to_check):
            return target_row_idx
            
        # 2. 向上找
        for offset in range(1, search_radius + 1):
            r = target_row_idx - offset
            if r > 0 and self._is_row_safe(r, table_to_check):
                return r
                
        # 3. 向下找 (慎用，会导致本页超高)
        # for offset in range(1, search_radius + 1): ...
        
        # 4. 如果都找不到，说明遇到了"楼梯"或"大合并"，必须强切
        return -1  # 表示需要强切

    def _is_row_safe(self, row_idx: int, table=None) -> bool:
        inspection = self.inspect_cut_boundary(row_idx, table=table)
        return bool(inspection.get("safe"))

    def inspect_cut_boundary(self, row_idx: int, table=None, *, max_items: int = 8) -> dict:
        table_to_check = table if table is not None else self.table
        payload = {
            "row_idx": int(row_idx),
            "safe": False,
            "blocked_by_continue": False,
            "ambiguous_access": False,
            "merge_origins": [],
            "access_errors": [],
        }
        if row_idx <= 0 or table_to_check is None:
            return payload

        try:
            cols_count = int(table_to_check.Columns.Count)
        except Exception:
            cols_count = int(getattr(self, "_col_count", 0) or 0)
        if cols_count <= 0:
            payload["ambiguous_access"] = True
            payload["access_errors"].append({"col": None, "reason": "missing_columns"})
            return payload

        access_errors: list[dict] = []
        blocked_by_continue = False
        ambiguous_access = False
        for col in range(1, cols_count + 1):
            try:
                cell = table_to_check.Cell(int(row_idx), int(col))
            except Exception as exc:
                ambiguous_access = True
                access_errors.append(
                    {
                        "col": int(col),
                        "reason": "cell_access_failed",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                continue

            try:
                row_index = int(getattr(cell, "RowIndex", row_idx) or row_idx)
            except Exception:
                row_index = int(row_idx)
            if row_index != int(row_idx):
                ambiguous_access = True
                access_errors.append(
                    {
                        "col": int(col),
                        "reason": "row_index_mismatch",
                        "expected_row": int(row_idx),
                        "actual_row": int(row_index),
                    }
                )

            try:
                vm = int(getattr(cell, "VerticalMerge", 0) or 0)
            except Exception:
                vm = 0
            if vm == 1:
                blocked_by_continue = True

        payload["blocked_by_continue"] = bool(blocked_by_continue)
        payload["ambiguous_access"] = bool(ambiguous_access)
        payload["access_errors"] = access_errors[: int(max_items)]
        if blocked_by_continue or ambiguous_access:
            try:
                payload["merge_origins"] = list(
                    self.describe_boundary_merge_origins(int(row_idx), table=table_to_check, max_items=int(max_items)) or []
                )
            except Exception:
                payload["merge_origins"] = []
        payload["safe"] = not bool(blocked_by_continue) and not bool(ambiguous_access)
        return payload

class CanvasSplitter:
    """
    负责在画布中执行物理切分。
    """
    def __init__(self, engine):
        self.engine = engine

    def split_row_at(self, table, row_idx) -> Tuple[Optional[object], Optional[object]]:
        """
        在指定行进行物理切分 (SplitTable)。
        返回: (upper_table, lower_table)
        """
        try:
            # 获取画布文档，确保我们操作的是画布里的表
            doc = table.Range.Document
            
            # 定位切割行
            # 注意：SplitTable 会在 Selection 的上方切开。
            # 如果我们要让 row_idx 成为下半表的第一行，就选 row_idx。
            
            # 防御：如果 row_idx 是第1行，无法切分
            if row_idx <= 1:
                return None, table
            
            # 防御：如果 row_idx > Rows.Count，也无法切分
            try:
                rc = table.Rows.Count
                if row_idx > rc:
                    return table, None
            except Exception:
                pass

            # 注意：当表格存在“纵向合并”时，Word COM 可能不允许通过 table.Rows(row_idx) 访问单行，
            # 会抛出“无法访问此集合中单独的行，因为表格有纵向合并的单元格”。
            # 这里改为选中该行的任意一个单元格的 Range 来定位，再执行 SplitTable。
            selected = False
            try:
                cols_count = int(table.Columns.Count)
            except Exception:
                cols_count = 0
            if cols_count > 0:
                for c in range(1, cols_count + 1):
                    try:
                        cell = table.Cell(row_idx, c)
                        # 选一个真正属于该行的单元格（避免 VerticalMerge Continue 导致 RowIndex 不匹配）
                        ri = getattr(cell, "RowIndex", row_idx)
                        vm = getattr(cell, "VerticalMerge", 0)
                        if int(ri) != int(row_idx) or int(vm) == 1:
                            continue
                        cell.Range.Select()
                        selected = True
                        break
                    except Exception:
                        continue
            if not selected:
                return None, None
            self.engine.app.Selection.SplitTable()
            
            # 切分后，Selection 依然在原来的位置（现在的下半表第1行）。
            # 此时，Selection.Tables(1) 应该就是下半表。
            lower_table = self.engine.app.Selection.Tables(1)
            
            # 上半表应该是 lower_table 的前一个表格？
            # 我们可以通过 Range 位置来找。
            # 或者：原 table 变量指向的是哪个？
            # 通常 table 变量会指向“原来的那个对象”，而在 Word 内部，SplitTable 可能是把后半截移出去，
            # 所以 table 可能指向的是上半表。
            # 为了保险，我们通过 Selection.Range.Previous(wdTable) 来找上半表?
            # 不，Range.Previous 很难用。
            
            # 简单方法：
            # 假设 doc 只有这两个表（如果画布清空过）。
            # 那么 Tables(1) 是上，Tables(2) 是下。
            
            # 但为了更鲁棒，我们利用 Range 位置。
            
            # 搜索 Start < start_pos 的最近表格
            # 实际上，在画布模式下，我们可以假设 Tables(1) 和 Tables(2) 就是这一对。
            # 因为每次处理前我们都清空画布了。
            
            upper_table = doc.Tables(1)
            # 再次确认 lower_table
            if doc.Tables.Count >= 2:
                lower_table = doc.Tables(2)
            else:
                lower_table = None
                
            return upper_table, lower_table
            
        except Exception as e:
            logger.warning(f"[SPLIT_FAIL] {e}")
            return None, None

    def _normalize_cut_border_strategy(self, strategy: str | None) -> str:
        strategy_text = str(strategy or CUT_BORDER_POLICY_CLOSED).strip().lower()
        if strategy_text == CUT_BORDER_POLICY_OPEN:
            return CUT_BORDER_POLICY_OPEN
        return CUT_BORDER_POLICY_CLOSED

    @staticmethod
    def _read_line_style(border_obj) -> int | None:
        try:
            return int(getattr(border_obj, "LineStyle", wdLineStyleNone))
        except Exception:
            return None

    def _pick_visible_line_style(self, border_accessor, fallback_types: tuple[int, ...]) -> int:
        for border_type in fallback_types:
            try:
                border_obj = border_accessor(border_type)
            except Exception:
                continue
            style = self._read_line_style(border_obj)
            if style not in (None, wdLineStyleNone):
                return int(style)
        return wdLineStyleSingle

    def _ensure_border_visible(self, border_accessor, border_type: int, fallback_types: tuple[int, ...]) -> bool:
        try:
            border_obj = border_accessor(border_type)
        except Exception:
            return False

        current_style = self._read_line_style(border_obj)
        if current_style not in (None, wdLineStyleNone):
            return True

        target_style = self._pick_visible_line_style(border_accessor, fallback_types)
        try:
            border_obj.LineStyle = int(target_style)
            return True
        except Exception:
            return False

    def apply_cut_border_policy(
        self,
        upper_table,
        lower_table,
        *,
        strategy: str = CUT_BORDER_POLICY_CLOSED,
        stage: str = "apply",
    ) -> None:
        strategy_name = self._normalize_cut_border_strategy(strategy)

        if strategy_name == CUT_BORDER_POLICY_OPEN:
            try:
                try:
                    upper_table.Rows.Last.Borders(wdBorderBottom).LineStyle = wdLineStyleNone
                except Exception:
                    pass
                try:
                    lower_table.Rows.First.Borders(wdBorderTop).LineStyle = wdLineStyleNone
                except Exception:
                    pass
            except Exception:
                pass
            return

        upper_restored = False
        lower_restored = False
        try:
            upper_restored = self._ensure_border_visible(
                upper_table.Rows.Last.Borders,
                wdBorderBottom,
                (wdBorderBottom, wdBorderTop),
            )
        except Exception:
            upper_restored = False
        try:
            lower_restored = self._ensure_border_visible(
                lower_table.Rows.First.Borders,
                wdBorderTop,
                (wdBorderTop, wdBorderBottom),
            )
        except Exception:
            lower_restored = False

        if logger.isEnabledFor(10):
            logger.debug(
                "[TABLE_BORDER_POLICY] stage=%s strategy=%s upper_bottom=%s lower_top=%s",
                str(stage),
                str(strategy_name),
                bool(upper_restored),
                bool(lower_restored),
            )

    def force_split_cells_at_row(self, table, row_idx: int) -> bool:
        """
        [Strategy 4.2] 强制切分单元格：在指定行位置，将所有跨越该行的合并单元格一分为二。
        
        场景：当表格出现"楼梯状"合并（第1列合并5-10行，第2列合并8-12行），
        导致无法找到安全切割点时，必须强行切开所有挡在切割线上的单元格。
        
        Args:
            table: Word 表格对象（画布中的副本）
            row_idx: 目标切割行号
            
        Returns:
            bool: 是否成功执行了单元格切分
        """
        if row_idx <= 1:
            return False
            
        try:
            cols_count = table.Columns.Count
        except Exception:
            return False
            
        any_split = False
        
        for col in range(1, cols_count + 1):
            try:
                cell = table.Cell(row_idx, col)
                
                # 检查该单元格是否处于垂直合并的"中间"位置
                # Word VerticalMerge values:
                # wdCellMergeNone = 0 (未合并的单独单元格)
                # wdCellMergeContinue = 1 (合并区域的后续单元格，被上方覆盖)
                try:
                    vm = getattr(cell, 'VerticalMerge', 0)
                except Exception:
                    vm = 0
                
                # 如果 VerticalMerge == 1 (wdCellMergeContinue)，说明该位置是被上方单元格覆盖的
                # 需要找到该合并区域的"头"单元格并切分它
                if vm == 1:  # wdCellMergeContinue - 处于合并区域中间
                    # 向上查找合并区域的起始行
                    start_row = self._find_merge_start_row(table, row_idx, col)
                    if start_row > 0 and start_row < row_idx:
                        # 计算需要切分的行数
                        # 从 start_row 到 row_idx-1 属于上半部分
                        # 从 row_idx 往下属于下半部分
                        rows_in_upper = row_idx - start_row
                        
                        try:
                            head_cell = table.Cell(start_row, col)
                            # Cell.Split(NumRows, NumCols)
                            # 我们只做垂直切分，不改变列数
                            # 但 Cell.Split 的语义是"将单元格切成 NxM 的小格"
                            # 这里我们需要把一个跨越多行的单元格，在 row_idx 位置切开
                            
                            # 获取当前单元格跨越的总行数
                            try:
                                # 方法1：通过 RowSpan 属性（如果存在）
                                total_rows = 1
                                try:
                                    # Word 并没有直接的 RowSpan 属性，需要手动计算
                                    # 向下遍历直到遇到不是 Continue 的行
                                    for check_row in range(start_row + 1, table.Rows.Count + 1):
                                        try:
                                            check_cell = table.Cell(check_row, col)
                                            check_vm = getattr(check_cell, 'VerticalMerge', 0)
                                            if check_vm == 1:  # Continue
                                                total_rows += 1
                                            else:
                                                break
                                        except Exception:
                                            break
                                except Exception:
                                    total_rows = rows_in_upper + 1  # 保守估计
                                
                                # 执行切分：将单元格切成 2 行 x 1 列
                                # 第一部分占据 rows_in_upper 行，第二部分占据剩余行
                                # Word 的 Cell.Split 会平均分配，所以我们需要先切成 2 份
                                head_cell.Split(NumRows=2, NumColumns=1)
                                any_split = True
                                
                                if logger.isEnabledFor(10):
                                    logger.debug(
                                        f"[CELL_SPLIT] col={col} merged_start={start_row} "
                                        f"cut_at={row_idx} total_rows={total_rows}"
                                    )
                                    
                            except Exception as split_err:
                                if logger.isEnabledFor(10):
                                    logger.debug(f"[CELL_SPLIT_ERROR] col={col}: {split_err}")
                                    
                        except Exception:
                            pass
                            
            except Exception:
                # Cell(row_idx, col) 访问失败，可能是横向合并导致的，跳过
                pass
        
        # 切分后需要修复边框
        if any_split:
            self._repair_split_borders(table, row_idx, strategy=CUT_BORDER_POLICY_CLOSED)
            
        return any_split
    
    def _find_merge_start_row(self, table, current_row: int, col: int) -> int:
        """
        向上查找合并区域的起始行。
        """
        for check_row in range(current_row - 1, 0, -1):
            try:
                cell = table.Cell(check_row, col)
                vm = getattr(cell, 'VerticalMerge', 0)
                # wdCellSpanFirst = 0 或不存在合并时，该行就是起始行
                # wdCellSpanContinue = 1 表示仍在合并区域中
                if vm != 1:  # 不是 Continue，说明找到了起始行
                    return check_row
            except Exception:
                return check_row
        return 1  # 默认第一行
    
    def _find_merge_end_row(self, table, start_row: int, col: int, total_rows: int | None = None) -> int:
        if start_row <= 0:
            return 0
        try:
            rows_count = int(total_rows or table.Rows.Count)
        except Exception:
            rows_count = int(start_row)
        end_row = int(start_row)
        for check_row in range(int(start_row) + 1, rows_count + 1):
            try:
                cell = table.Cell(check_row, col)
                vm = getattr(cell, 'VerticalMerge', 0)
                if int(vm) == 1:
                    end_row = int(check_row)
                    continue
            except Exception:
                break
            break
        return int(end_row)

    def describe_boundary_merge_origins(self, row_idx: int, table=None, *, max_items: int = 8) -> list[dict]:
        table_to_check = table if table is not None else self.table
        if row_idx <= 1 or table_to_check is None:
            return []

        try:
            cols_count = int(table_to_check.Columns.Count)
        except Exception:
            cols_count = int(getattr(self, "_col_count", 0) or 0)
        if cols_count <= 0:
            return []

        try:
            rows_count = int(table_to_check.Rows.Count)
        except Exception:
            rows_count = int(row_idx)

        results: list[dict] = []
        seen: set[tuple[int, int, int]] = set()
        for col in range(1, cols_count + 1):
            try:
                cell = table_to_check.Cell(row_idx, col)
                vm = getattr(cell, 'VerticalMerge', 0)
            except Exception:
                continue
            if int(vm) != 1:
                continue

            start_row = self._find_merge_start_row(table_to_check, int(row_idx), int(col))
            end_row = self._find_merge_end_row(table_to_check, int(start_row), int(col), total_rows=rows_count)
            signature = (int(col), int(start_row), int(end_row))
            if signature in seen:
                continue
            seen.add(signature)

            payload = {
                "cut_row": int(row_idx),
                "col": int(col),
                "start_row": int(start_row),
                "end_row": int(end_row),
                "row_span": int(end_row - start_row + 1) if int(end_row) >= int(start_row) else None,
            }
            try:
                origin_cell = table_to_check.Cell(int(start_row), int(col))
                payload["origin_range_start"] = int(origin_cell.Range.Start)
                payload["origin_range_end"] = int(origin_cell.Range.End)
            except Exception:
                pass
            results.append(payload)
            if len(results) >= int(max_items):
                break
        return results

    def _repair_split_borders(self, table, row_idx: int, strategy: str = CUT_BORDER_POLICY_CLOSED):
        """
        [Strategy 4.6] 边框修复：强制切单元格后重建切口处边框策略。
        """
        strategy_name = self._normalize_cut_border_strategy(strategy)
        try:
            cols_count = table.Columns.Count
        except Exception:
            return
            
        for col in range(1, cols_count + 1):
            try:
                # 上一行（切分后的上半截底边框）
                if row_idx > 1:
                    try:
                        upper_cell = table.Cell(row_idx - 1, col)
                        if strategy_name == CUT_BORDER_POLICY_OPEN:
                            upper_cell.Borders(wdBorderBottom).LineStyle = wdLineStyleNone
                        else:
                            self._ensure_border_visible(
                                upper_cell.Borders,
                                wdBorderBottom,
                                (wdBorderBottom, wdBorderTop),
                            )
                    except Exception:
                        pass
                
                # 当前行（切分后的下半截顶边框）
                try:
                    lower_cell = table.Cell(row_idx, col)
                    if strategy_name == CUT_BORDER_POLICY_OPEN:
                        lower_cell.Borders(wdBorderTop).LineStyle = wdLineStyleNone
                    else:
                        self._ensure_border_visible(
                            lower_cell.Borders,
                            wdBorderTop,
                            (wdBorderTop, wdBorderBottom),
                        )
                except Exception:
                    pass
                    
            except Exception:
                pass

        if logger.isEnabledFor(10):
            logger.debug(
                "[TABLE_BORDER_REPAIR] strategy=%s row_idx=%s cols=%s",
                str(strategy_name),
                int(row_idx),
                int(cols_count),
            )
