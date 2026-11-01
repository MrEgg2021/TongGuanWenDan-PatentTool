# UI 开发规范：复选框

> 状态：当前实现约定（2026-10-22 按代码核对）。
> 样式来源以 `gui/ui_layout_impl/theme.qss` 为准；控件实现见 `gui/widgets_impl/graphic_checkbox.py`。

## 0. 适用范围

- 适用于复选框/单选框视觉控件。
- 不适用于 `QComboBox` 下拉 delegate、表格单元格自定义渲染、以及与复选框无关的容器样式问题；遇到这些场景先定位对应控件链路。

## 1. 当前实现约定

- 统一使用 `gui/widgets_impl/graphic_checkbox.py` 中的 `GraphicCheckBox`，它是 **`QCheckBox` 的子类**，只负责光标、`WA_StyledBackground` 和旧 `emphasis` 属性的兼容。
- **不要**重写 `paintEvent`、`sizeHint` 做自绘；**不要**在控件内部调用 `setStyleSheet` 硬编码颜色。外观全部由 `theme.qss` 决定。
- 指示器样式集中在 `theme.qss` 的 `QCheckBox` / `QCheckBox::indicator` 规则中：18×18、1px 边框（`#94A3B8`）、4px 圆角，选中态使用 `assets/check_dark.svg`。
- 变体通过动态属性 `class` 区分，例如 `QCheckBox[class="OfficialDocsCheck"]`、`QCheckBox[class="TableRowCheck"]`；高密度页面使用 `QWidget#formalReviewPage[dense="true"] QCheckBox`。

## 2. 使用方式

```python
from gui.widgets_impl.graphic_checkbox import GraphicCheckBox

chk = GraphicCheckBox("选项")
chk.setProperty("class", "TableRowCheck")  # 仅在需要既有变体样式时设置
```

- **单选**：加入 `QButtonGroup` 并 `setExclusive(True)`；项目统一使用方形复选框外观表示单选，不额外维护圆形图标。
- **列表/表格 item widget**：必须用布局包裹并设置合适的 `ContentsMargins`，避免指示器被裁剪。
- **强调语义**：设置 `emphasis` 属性，由 QSS 决定表现，不在代码里写颜色。

## 3. 历史教训

早期版本曾用 `QAbstractButton` + Base64 PNG 自绘复选框，因下列问题已整体回退为原生 `QCheckBox` + QSS，不要再恢复自绘方案：

- 自绘与样式表混用时互相覆盖，边框丢失、状态不一致。
- 在 `paintEvent` 中调用 `self.style().drawItemText` 并同时应用样式表，易触发渲染死循环或白屏。
- Base64 内嵌图标无法跟随主题切换；现已改用 `assets/check_dark.svg` 配合 `gui/ui_layout_impl/stylesheet.py` 的主题目录替换。

结论：优先用 QSS 表达状态；只有 Qt 无法表达时才考虑自绘，且必须先确认不存在样式表冲突。

---
*文档最后更新时间：2026-10-22*
