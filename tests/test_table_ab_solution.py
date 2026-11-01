"""
A+B 方案完整分析验证脚本

A 方案: 使用 Information(6) 获取实际行位置（替代 Row.Height 累加）
B 方案: 修复并使用 K 系数进行校验/校准

本脚本用真实数据验证 A+B 分析结论
"""


# ==================== 真实日志数据 ====================
LOG_DATA = {
    "table_info": {
        "total_rows": 89,
        "total_cols": 2,
    },
    "split_decision": {
        "loop": 1,
        "cut_row": 50,
        "safe_row": 50,
    },
    "target": {
        "max_height_cm": 24.0,
        "max_height_mm": 240.0,
        "target_slice_pt": 680.31,  # 24cm * 72 / 2.54
    },
    "fragment_1": {
        "name": "sms_11.jpg",
        "original_px": (4960, 9422),
        "cropped_px": (2486, 9422),
        "word_width_pt": 296.85,
        "xml_w_mm": 165.00,
        "xml_h_mm": 396.89,
    },
    "fragment_2": {
        "name": "sms_12.jpg",
        "original_px": (4960, 7441),
        "cropped_px": (2486, 7441),
        "word_width_pt": 296.85,
        "xml_w_mm": 165.00,
        "xml_h_mm": 313.45,
    },
}

# ==================== 常量 ====================
WIDTH_FACTOR = 0.3528  # point -> mm
DEFAULT_ROW_HEIGHT_PT = 20.0  # 默认行高（当 Row.Height 不可用时）


def analyze_current_logic():
    """分析当前逻辑的问题"""
    print("=" * 80)
    print("【分析1】当前拆分逻辑的问题")
    print("=" * 80)

    # 当前逻辑：累加 Row.Height
    total_rows = LOG_DATA["table_info"]["total_rows"]
    target_pt = LOG_DATA["target"]["target_slice_pt"]

    # 假设平均行高 14pt (Word 默认)
    avg_row_height = 14.0
    estimated_total_pt = total_rows * avg_row_height

    print("\n当前 Row.Height 累加逻辑:")
    print(f"  - 表格总行数: {total_rows}")
    print(f"  - 假设平均行高: {avg_row_height}pt")
    print(f"  - 估算总高度: {estimated_total_pt}pt")
    print(f"  - 目标切分高度: {target_pt}pt (24cm)")
    print(f"  - 切分点: 第 {int(target_pt / avg_row_height)} 行")

    # 实际结果
    cut_row = LOG_DATA["split_decision"]["cut_row"]
    print(f"\n实际切分点: 第 {cut_row} 行")
    print(f"  - 估算 Row.Height 累加: {cut_row * avg_row_height}pt")

    # 但实际渲染高度远超目标
    print("\n问题:")
    print(f"  - 估算应切在第 {int(target_pt / avg_row_height)} 行")
    print(f"  - 实际切在第 {cut_row} 行")
    print(f"  - 偏差: {cut_row - int(target_pt / avg_row_height)} 行")
    print(f"  - 实际渲染高度: {LOG_DATA['fragment_1']['xml_h_mm']}mm")
    print(f"  - 目标高度: {LOG_DATA['target']['max_height_mm']}mm")
    print(f"  - 超限比例: {LOG_DATA['fragment_1']['xml_h_mm'] / LOG_DATA['target']['max_height_mm']:.2f}x")


def analyze_information6():
    """分析 A 方案: Information(6)"""
    print("\n" + "=" * 80)
    print("【分析2】A 方案 - Information(6) 获取实际位置")
    print("=" * 80)

    print("""
A 方案原理:
  - Row.Height 返回的是"最小行高声明"（HeightRule=wdRowHeightAtLeast）
  - Information(6) 返回的是"实际渲染位置"（wdVerticalPositionRelativeToPage）
  - 使用 Information(6) 可以获取每行的真实 top 坐标

当前代码状态 (split_flow.py):
  - 第 272-284 行: 优先使用 Row.Height 累加 ← PRIMARY
  - 第 288-459 行: Information(6) 作为 FALLBACK ← 仅当 Row.Height 失败时

问题:
  - Information(6) 应该作为 PRIMARY 方法
  - 当前是 FALLBACK，只有 Row.Height 异常时才触发

A 方案实现建议:
  1. 将 Information(6) 逻辑提升为 PRIMARY 路径
  2. 保留 Row.Height 作为快速估算（用于初次判断是否需要拆分）
  3. 真正执行拆分时使用 Information(6) 的精确位置
""")


def analyze_k_coefficient():
    """分析 B 方案: K 系数"""
    print("\n" + "=" * 80)
    print("【分析3】B 方案 - K 系数采样与使用")
    print("=" * 80)

    # 反推 K 系数
    fragment1 = LOG_DATA["fragment_1"]

    # 从 XML 尺寸反推
    xml_w = fragment1["xml_w_mm"]
    xml_h = fragment1["xml_h_mm"]
    cropped_px = fragment1["cropped_px"]

    # 计算像素密度
    px_per_mm_xml = cropped_px[0] / xml_w  # 2486 / 165 = 15.07 px/mm
    print("\n从实际输出反推:")
    print(f"  - XML 尺寸: {xml_w}mm x {xml_h}mm")
    print(f"  - 裁剪后像素: {cropped_px[0]}px x {cropped_px[1]}px")
    print(f"  - 像素密度 (XML 空间): {px_per_mm_xml:.2f} px/mm")

    # 计算 K = 实际像素高度 / Word Point 高度
    # Word 24cm = 680.31pt
    # 实际渲染 396.89mm = ? pt (假设 1mm = 2.834645669pt)
    pt_per_mm = 72 / 25.4
    actual_pt = xml_h * pt_per_mm  # 396.89 * 2.8346 = 1125.1 pt
    K = actual_pt / LOG_DATA["target"]["target_slice_pt"]

    print("\nK 系数反推:")
    print(f"  - 实际渲染高度: {xml_h}mm = {actual_pt:.2f}pt")
    print(f"  - 目标高度: {LOG_DATA['target']['target_slice_pt']:.2f}pt")
    print(f"  - 反推 K 系数: {K:.4f}")
    print(f"  - 接近 120/72 = {120/72:.4f} (显示 DPI 缩放)")

    print("""
当前代码状态 (split_flow.py + table_topology_impl.py):
  - 第 171 行: coeff_k = scanner.calculate_height_coefficient()  ← 计算了
  - 第 173 行: logger.debug(f"[TABLE_COEFF] K={coeff_k:.4f}")     ← 只打日志
  - 之后没有任何地方使用 coeff_k 变量！

B 方案实现建议:
  1. 修复 K 系数采样（当前采样失败返回 None）
  2. 将 K 系数用于:
     a) 调整目标切分高度: target_adjusted = target_slice_pt * K
     b) 验证切分后实际高度: if actual_h > max_height_mm / K → 再拆分
""")


def analyze_ab_combined():
    """分析 A+B 组合方案"""
    print("\n" + "=" * 80)
    print("【分析4】A+B 组合方案")
    print("=" * 80)

    print("""
A+B 组合原理:
  ┌─────────────────────────────────────────────────────────────┐
  │  Step 1: 计算 K 系数 (B)                                    │
  │    - 三点采样 (top/mid/bot)                                  │
  │    - K = 真实像素高度 / Word Point 高度                      │
  │    - 例如: K = 1.65                                         │
  └─────────────────────────────────────────────────────────────┘
                              ↓
  ┌─────────────────────────────────────────────────────────────┐
  │  Step 2: 使用 Information(6) 确定切分点 (A)                 │
  │    - 获取每行的实际 top 坐标                                  │
  │    - 考虑页码偏移（跨页表格）                                  │
  │    - 找到 position > target_slice_pt * K 的行               │
  └─────────────────────────────────────────────────────────────┘
                              ↓
  ┌─────────────────────────────────────────────────────────────┐
  │  Step 3: 验证与调整                                          │
  │    - 截图后计算实际 h_mm                                     │
  │    - 如果 h_mm > max_height_mm:                             │
  │      - 使用 K 调整: 下一轮切分更靠前                          │
  │      - 或直接对图片进行像素级二次拆分                          │
  └─────────────────────────────────────────────────────────────┘

为什么需要 A+B:
  - A (Information): 获取 Word 内部的精确位置，但这是"Word 坐标空间"
  - B (K): 校准 Word 坐标空间 → 实际渲染坐标空间
  - 两者结合才能准确预测最终渲染高度

当前问题:
  - A 是 FALLBACK（只在 Row.Height 失败时用）
  - B 计算了但完全没使用
  - 结果: 估算高度 << 实际高度，导致切分点太靠后
""")


def analyze_seam_problem():
    """分析缝隙问题"""
    print("\n" + "=" * 80)
    print("【分析5】缝隙问题分析")
    print("=" * 80)

    print("""
缝隙产生的原因:

1. Canvas Surgery 拆分位置 vs PDF 页面边界不对齐
   - Canvas Surgery 在第 50 行拆分表格
   - 但 PDF 渲染的页面边界取决于 Word 的分页
   - 这两个位置不一定重合

2. PDF 多页合并的去重逻辑 (render_pdf_ops.py:301-322)
   - 当前页末尾有表格线 (trailing)
   - 下一页开头有表格线 (leading)
   - 裁剪 leading 部分避免重复

3. 去重逻辑可能失效的情况:
   - 表格线太细/颜色太浅 → _row_is_line() 检测失败
   - 拆分位置恰好在两页之间 → 没有边框重复
   - 拆分位置在内容中间 → 裁剪掉有效内容

从日志看:
  [TABLE_SPLIT_DECISION] loop=1 rows=89 cut_row=50
  [TABLE_PDF_PAGE_TRIM] page=1 top=600 bottom=6314 new_h=5715
  [TABLE_PDF_PAGE_TRIM] page=2 top=600 bottom=4302 new_h=3703

  第一个片段 (rows 1-50) 渲染成 2 页 PDF
  - 第 1 页裁剪后高度: 5715px
  - 第 2 页裁剪后高度: 3703px
  - 合并后: 9422px

可能的缝隙位置:
  - sms_11 (top) 和 sms_12 (bottom) 之间的边界
  - 第 50 行拆分，但 PDF 页面边界在别处
  - 去重逻辑对边界处理不当
""")


def verify_with_calculation():
    """用数据验证分析"""
    print("\n" + "=" * 80)
    print("【验证】数据验证")
    print("=" * 80)

    # 验证 K 系数计算
    print("\n1. 验证 K 系数:")

    # 从 XML 输出反推
    f1 = LOG_DATA["fragment_1"]
    pt_per_mm = 72 / 25.4

    # 方法1: 从 XML he 反推
    xml_h_pt = f1["xml_h_mm"] * pt_per_mm
    target_pt = LOG_DATA["target"]["target_slice_pt"]
    K_from_xml = xml_h_pt / target_pt

    print(f"  从 XML he 计算: {f1['xml_h_mm']}mm × {pt_per_mm:.4f} = {xml_h_pt:.2f}pt")
    print(f"  目标高度: {target_pt}pt")
    print(f"  K = {xml_h_pt:.2f} / {target_pt:.2f} = {K_from_xml:.4f}")

    # 方法2: 从行数反推
    cut_row = LOG_DATA["split_decision"]["cut_row"]
    avg_declared_height = target_pt / cut_row
    actual_avg_height = xml_h_pt / cut_row
    K_from_rows = actual_avg_height / avg_declared_height

    print(f"\n  假设在第 {cut_row} 行切分:")
    print(f"  - 声明平均行高: {target_pt}/{cut_row} = {avg_declared_height:.2f}pt")
    print(f"  - 实际平均高度: {xml_h_pt:.2f}/{cut_row} = {actual_avg_height:.2f}pt")
    print(f"  - K = {actual_avg_height:.2f} / {avg_declared_height:.2f} = {K_from_rows:.4f}")

    print(f"\n  结论: K ≈ {K_from_xml:.2f} (约 1.65x)")

    # 验证如果用 A+B 应该切在第几行
    print("\n2. 验证 A+B 方案的切分点:")
    adjusted_target = target_pt * K_from_xml
    correct_cut_row = int(adjusted_target / avg_declared_height)

    print(f"  - 原始目标: {target_pt}pt (24cm)")
    print(f"  - K 系数校准: {target_pt} × {K_from_xml:.4f} = {adjusted_target:.2f}pt")
    print(f"  - 校准后应切在第 {correct_cut_row} 行")
    print(f"  - 实际切在第 {cut_row} 行")
    print(f"  - 差距: {cut_row - correct_cut_row} 行 (多了 {cut_row - correct_cut_row} 行)")

    # 验证最终高度
    estimated_h_mm = (correct_cut_row * avg_declared_height) / pt_per_mm
    print(f"\n  如果在第 {correct_cut_row} 行切分:")
    print(f"  - 预估高度: {correct_cut_row} × {avg_declared_height:.2f}pt = {correct_cut_row * avg_declared_height:.2f}pt")
    print(f"  - 换算mm: {estimated_h_mm:.2f}mm")
    print(f"  - 目标: ≤ {LOG_DATA['target']['max_height_mm']}mm")


def main():
    print("=" * 80)
    print("A+B 方案完整分析验证脚本")
    print("A: Information(6) 获取实际行位置")
    print("B: 修复并使用 K 系数")
    print("=" * 80)

    analyze_current_logic()
    analyze_information6()
    analyze_k_coefficient()
    analyze_ab_combined()
    analyze_seam_problem()
    verify_with_calculation()

    print("\n" + "=" * 80)
    print("【总结】")
    print("=" * 80)
    print("""
当前问题的根本原因:

1. 拆分判断使用 Row.Height 累加 (不准确)
   - Row.Height 是"最小行高声明"，不是实际渲染高度
   - 实际渲染高度通常是声明的 1.5-2x 倍

2. Information(6) 只是 FALLBACK
   - 应该作为 PRIMARY 方法获取精确位置

3. K 系数计算了但没使用
   - 计算 → 打印日志 → 丢弃
   - 应该用于校准目标高度

4. 缝隙问题
   - Canvas Surgery 拆分位置 ≠ PDF 页面边界
   - 多页合并去重逻辑可能失效

A+B 修复方向:

方案1: 提升 Information(6) 为 PRIMARY
  - 第 272-284 行改为先尝试 Information(6)
  - Row.Height 只用于快速预判断

方案2: 将 K 系数用于切分判断
  - target_adjusted = target_slice_pt × K
  - 在 Information(6) 位置判断时使用校准后的目标

方案3: 增加验证循环
  - 截图后检查实际 h_mm
  - 如果超标，用 K 调整后重新拆分
""")


if __name__ == "__main__":
    main()
