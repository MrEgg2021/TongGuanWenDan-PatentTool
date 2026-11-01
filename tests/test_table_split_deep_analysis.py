"""
深度分析测试脚本：验证跨页长表格拆分问题的所有根因

基于 conversion.log 中的真实数据，逐步追踪整个数据流，
验证每个环节的数值，精确定位问题所在。

只读分析模式 - 不修改任何项目文件。
"""

import os
from pathlib import Path
from PIL import Image

# ============================================================
# 从日志中提取的真实数据点
# ============================================================

# 原始表格参数
TABLE_IDX = 184
TABLE_ROWS = 89
TABLE_COLS = 2
TABLE_RANGE = (10377, 12212)

# 配置参数
MAX_HEIGHT_CM = 24.0
MAX_HEIGHT_MM = MAX_HEIGHT_CM * 10.0  # 240mm
TARGET_SLICE_PT = MAX_HEIGHT_CM * 72.0 / 2.54  # 680.31 pt
WIDTH_FACTOR = 0.3528  # point → mm 换算因子
MAX_WIDTH_MM = 165.0

# 拆分决策
CUT_ROW = 50
SAFE_ROW = 50
COEFF_K = 1.0  # 系数采样全部失败，回退默认值

# Fragment 1 (rows 1-49, 即 sms_11.jpg)
FRAG1 = {
    "name": "tbl_5e383e10.jpg → sms_11.jpg",
    "rows": 49,
    "pdf_pages": 2,
    "page1_trim": {"top": 600, "bottom": 6314, "orig_h": 7015, "new_h": 5715},
    "page2_trim": {"top": 600, "bottom": 4302, "orig_h": 7015, "new_h": 3703},
    "merged_px": (4960, 9422),  # IMG_PIPELINE 输出
    "crop_margin_bbox": (1241, 0, 3718, 9417),  # CROP_MARGIN_PAD
    "crop_margin_img_wh": (4960, 9418),  # 合并后、padding 前
    "trimmed_px": (2486, 9422),  # TABLE_TRIM 后
    "wp_for_xml": 296.85,
    "w_mm_before_center": 104.73,
    "h_mm_before_center": 396.92,
    # EQ_PAD 居中补白参数
    "eq_pad": {
        "w_px": 2486, "h_px": 9422,
        "cw_mm": 104.73, "target_width_mm": 165.0,
        "px_per_mm_raw": 23.74, "px_per_mm_clamped": 23.74,
        "canvas_width_px": 3917,
        "left_pad_px": 865, "right_pad_px": 566,
    },
    "xml_wi": 165.00,
    "xml_he": 396.89,
}

# Fragment 2 (rows 50-89, 即 sms_12.jpg)
FRAG2 = {
    "name": "tbl_156fe576.jpg → sms_12.jpg",
    "rows": 40,
    "pdf_pages": 2,
    "page1_trim": {"top": 600, "bottom": 6319, "orig_h": 7015, "new_h": 5720},
    "page2_trim": {"top": 600, "bottom": 2316, "orig_h": 7015, "new_h": 1717},
    "merged_px": (4960, 7441),
    "crop_margin_bbox": (1241, 0, 3718, 7436),
    "crop_margin_img_wh": (4960, 7437),
    "trimmed_px": (2486, 7441),
    "wp_for_xml": 296.85,
    "w_mm_before_center": 104.73,
    "h_mm_before_center": 313.47,
    "eq_pad": {
        "w_px": 2486, "h_px": 7441,
        "cw_mm": 104.73, "target_width_mm": 165.0,
        "px_per_mm_raw": 23.74, "px_per_mm_clamped": 23.74,
        "canvas_width_px": 3917,
        "left_pad_px": 865, "right_pad_px": 566,
    },
    "xml_wi": 165.00,
    "xml_he": 313.45,
}


def print_header(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")


def print_section(title):
    print(f"\n--- {title} ---")


def verify_split_decision():
    """验证拆分决策"""
    print_header("验证1: 拆分决策逻辑")

    print(f"  表格行数: {TABLE_ROWS}")
    print("  进入拓扑拆分的条件: row_count >= 20 OR estimated_total_pt > target_slice_pt")
    print(f"  row_count={TABLE_ROWS} >= 20 → True → 直接进入拓扑拆分")
    print("  (短表整体截图路径被完全跳过)")

    print_section("系数 K 计算")
    print("  三点采样: top(1-5), mid(42-46), bot(85-89)")
    print(f"  采样结果: 全部失败 → K={COEFF_K}")
    print("  ⚠️  K系数计算全部失败的原因:")
    print("     日志显示系数采样图片已输出，但图片内容无效")
    print("     (coeff_sample_1_5_xxx.jpg, coeff_sample_42_46_xxx.jpg, coeff_sample_85_89_xxx.jpg)")

    print_section("拆分点确定")
    print(f"  target_slice_pt = {MAX_HEIGHT_CM} * 72 / 2.54 = {TARGET_SLICE_PT:.2f} pt")
    print(f"  累加 Row.Height(pt) 到第 {CUT_ROW} 行时超过 {TARGET_SLICE_PT:.2f} pt")
    print(f"  safe_row = {SAFE_ROW} (拓扑扫描未发现纵向合并冲突)")

    print_section("致命问题: K系数是死代码")
    print("  coeff_k 在 split_flow.py:171 计算")
    print("  coeff_k 在 split_flow.py:173 打日志")
    print("  coeff_k 之后 ❌ 从未被使用!")
    print("  拆分循环 (lines 272-284) 直接用 Row.Height 累加 vs target_slice_pt")
    print("  没有乘以 K 做校正 → 拆分位置估算完全依赖 Word 内部行高")


def verify_pdf_rendering():
    """验证 PDF 渲染和多页合并"""
    print_header("验证2: PDF 渲染和多页合并")

    for frag_name, frag in [("Fragment 1 (sms_11)", FRAG1), ("Fragment 2 (sms_12)", FRAG2)]:
        print_section(frag_name)

        p1 = frag["page1_trim"]
        p2 = frag["page2_trim"]

        print(f"  PDF 导出: {frag['pdf_pages']} 页")
        print("  PDF DPI: 600")
        print(f"  PDF 页高: {p1['orig_h']}px")
        print(f"    = {p1['orig_h']}px / (600/72) = {p1['orig_h'] / (600/72):.1f}pt")
        print(f"    = {p1['orig_h'] / (600/72) / 72 * 25.4:.1f}mm (≈ A4 297mm)")

        print("\n  页面裁白:")
        print(f"    Page 1: top={p1['top']} bottom={p1['bottom']} → {p1['new_h']}px")
        print(f"    Page 2: top={p2['top']} bottom={p2['bottom']} → {p2['new_h']}px")
        merged_h = p1['new_h'] + p2['new_h']
        print(f"    合并后高度: {p1['new_h']} + {p2['new_h']} = {merged_h}px")
        print(f"    最终输出: {frag['merged_px'][0]}x{frag['merged_px'][1]}px")
        print(f"    差值: {frag['merged_px'][1] - merged_h}px (CROP_MARGIN_PAD padding)")

        print("\n  ⚠️  缝隙问题分析:")
        print("    日志中无 [TABLE_PDF_BORDER_DEDUPE] → 边框去重未触发")
        print("    _count_trailing_line_rows(page1, max_rows=4): 可能=0")
        print("    _count_leading_line_rows(page2, max_rows=4): 可能=0")
        print("    原因: Word 导出 PDF 时表格跨页，页面断裂处不是表格边框线")
        print("    而是表格内容行的中间，所以检测不到 '65%以上暗像素' 的行")
        print("    → 两页直接拼接，留下微小的缝隙")


def verify_dimension_calculation():
    """验证尺寸计算链路"""
    print_header("验证3: 尺寸计算全链路")

    for frag_name, frag in [("Fragment 1 (sms_11)", FRAG1), ("Fragment 2 (sms_12)", FRAG2)]:
        print_section(frag_name)

        # Step 1: calculate_xml_dimensions
        w_px, h_px = frag["trimmed_px"]
        wp = frag["wp_for_xml"]
        w_mm = wp * WIDTH_FACTOR
        h_mm = w_mm * (h_px / w_px)
        print("  calculate_xml_dimensions:")
        print(f"    width_mm = {wp} * {WIDTH_FACTOR} = {w_mm:.2f}mm")
        print(f"    height_mm = {w_mm:.2f} * ({h_px} / {w_px}) = {h_mm:.2f}mm")
        print(f"    max_width 检查: {w_mm:.2f} < {MAX_WIDTH_MM} → 不触发宽度钳制")
        print(f"    日志值: w_mm={frag['w_mm_before_center']}, h_mm={frag['h_mm_before_center']}")
        print(f"    验证: {'✅ 一致' if abs(h_mm - frag['h_mm_before_center']) < 0.1 else '❌ 不一致'}")

        # Step 2: pad_equation_for_centering
        eq = frag["eq_pad"]
        px_per_mm = eq["w_px"] / eq["cw_mm"]
        canvas_w = int(round(eq["target_width_mm"] * px_per_mm))
        print("\n  pad_equation_for_centering:")
        print(f"    px_per_mm = {eq['w_px']} / {eq['cw_mm']} = {px_per_mm:.2f}")
        print(f"    canvas_width = {eq['target_width_mm']} * {px_per_mm:.2f} = {canvas_w}")
        print(f"    日志值 canvas_width_px={eq['canvas_width_px']}")
        print(f"    验证: {'✅ 一致' if abs(canvas_w - eq['canvas_width_px']) <= 1 else '❌ 不一致'}")

        # 居中后的返回值计算
        # equation_ops.py line 348: new_height_mm = text_width * (final_h_px / final_w_px)
        final_w_px = eq["canvas_width_px"]
        final_h_px = eq["h_px"]  # 高度不变，只补白宽度
        new_h_mm = eq["target_width_mm"] * (final_h_px / final_w_px)
        print("\n  居中补白后返回值:")
        print(f"    wi = {eq['target_width_mm']:.2f}mm (固定为 target_width_mm)")
        print(f"    he = {eq['target_width_mm']} * ({final_h_px} / {final_w_px}) = {new_h_mm:.2f}mm")
        print(f"    XML 实际值: wi={frag['xml_wi']}, he={frag['xml_he']}")
        print(f"    验证: {'✅ 近似一致' if abs(new_h_mm - frag['xml_he']) < 0.5 else '❌ 不一致'}")

        # 关键检查
        print("\n  ⛔ 高度限制检查:")
        print(f"    he={frag['xml_he']}mm vs max_height={MAX_HEIGHT_MM}mm")
        print(f"    超出: {frag['xml_he'] - MAX_HEIGHT_MM:.2f}mm ({frag['xml_he']/MAX_HEIGHT_MM:.2f}x)")
        print("    ❌ 此处没有任何代码检查 he 是否超过 max_height_mm!")


def verify_height_ratio():
    """验证 Word Row.Height 估算与实际渲染高度的比例"""
    print_header("验证4: Row.Height 估算 vs 实际高度的比例差异")

    # 89行表格在row 50切分，意味着rows 1-49的Row.Height累加≈680pt
    est_49rows_pt = TARGET_SLICE_PT  # 近似值，因为cut发生在row 50
    actual_49rows_mm = FRAG1["h_mm_before_center"]  # 396.92mm
    actual_49rows_pt = actual_49rows_mm / 25.4 * 72  # mm → pt

    print("  Fragment 1 (49 rows):")
    print(f"    Word Row.Height 累加 ≈ {est_49rows_pt:.2f} pt (因为在row 50才超过阈值)")
    print(f"    实际渲染高度 = {actual_49rows_mm:.2f} mm = {actual_49rows_pt:.2f} pt")
    print(f"    比例 K_actual = {actual_49rows_pt:.2f} / {est_49rows_pt:.2f} = {actual_49rows_pt/est_49rows_pt:.4f}")
    print(f"    即实际高度是 Word 估算的 {actual_49rows_pt/est_49rows_pt:.2f} 倍!")

    # 计算如果 K 被正确使用，cut_row 应该是多少
    corrected_target_pt = TARGET_SLICE_PT / (actual_49rows_pt / est_49rows_pt)
    print("\n  如果 K 系数被正确应用:")
    print(f"    校正后的 target_slice_pt = {TARGET_SLICE_PT:.2f} / {actual_49rows_pt/est_49rows_pt:.4f} = {corrected_target_pt:.2f} pt")
    print(f"    大约在第 {int(50 / (actual_49rows_pt/est_49rows_pt))} 行就应该切分")
    print(f"    这将产生约 {50 / (actual_49rows_pt/est_49rows_pt):.0f} 个更小的片段")

    # 验证 PDF 页面结构
    print("\n  PDF 页面结构验证:")
    dpi = 600
    px_per_pt = dpi / 72.0  # 8.333
    print(f"    DPI={dpi}, px/pt = {px_per_pt:.3f}")

    for name, frag in [("Fragment 1", FRAG1), ("Fragment 2", FRAG2)]:
        p1 = frag["page1_trim"]
        p2 = frag["page2_trim"]
        content_px = p1["new_h"] + p2["new_h"]
        content_pt = content_px / px_per_pt
        content_mm = content_pt / 72.0 * 25.4
        print(f"    {name}: {p1['new_h']}+{p2['new_h']}={content_px}px = {content_pt:.1f}pt = {content_mm:.1f}mm")


def verify_real_images():
    """检查真实输出图片的尺寸"""
    print_header("验证5: 真实输出图片尺寸")

    img_paths = {
        "sms_11.jpg": Path(__file__).resolve().parents[1] / "output/example/100002/sms_11.jpg",
        "sms_12.jpg": Path(__file__).resolve().parents[1] / "output/example/100002/sms_12.jpg",
    }

    for name, path in img_paths.items():
        if os.path.exists(path):
            with Image.open(path) as img:
                w, h = img.size
                # 反推 wi/he
                # 居中后: wi = 165.00, he = 165.0 * (h/w)
                calc_he = 165.0 * (h / w)
                print(f"  {name}:")
                print(f"    像素尺寸: {w} x {h}")
                print(f"    宽高比: {h/w:.4f}")
                print(f"    反推 he = 165.0 * ({h}/{w}) = {calc_he:.2f}mm")
                print(f"    XML he 值: {'396.89' if '11' in name else '313.45'}mm")
                print(f"    超出限制: {calc_he - MAX_HEIGHT_MM:.2f}mm ({calc_he/MAX_HEIGHT_MM*100:.1f}%)")
        else:
            print(f"  {name}: 文件不存在 ({path})")


def verify_seam_issue():
    """分析 PDF 多页拼接缝隙"""
    print_header("验证6: PDF 多页拼接缝隙分析")

    for name, frag in [("Fragment 1 (sms_11)", FRAG1), ("Fragment 2 (sms_12)", FRAG2)]:
        print_section(name)

        p1 = frag["page1_trim"]
        p2 = frag["page2_trim"]

        print("  PDF 页面裁白后:")
        print(f"    Page 1: 保留 [{p1['top']}, {p1['bottom']}] → 高度 {p1['new_h']}px")
        print(f"    Page 2: 保留 [{p2['top']}, {p2['bottom']}] → 高度 {p2['new_h']}px")

        print("\n  缝隙产生机制:")
        print("    1. Word 导出 PDF: 表格连续内容被 A4 页面强制分页")
        print("    2. 页面断裂位置: 在表格某行的 **中间**（不是在行与行的边框线处）")
        print("    3. 裁白: _find_vertical_bounds 找到每页的内容上下界")
        print("    4. 去重检查: _count_trailing_line_rows / _count_leading_line_rows")
        print("       - 只检查边缘 4px 内是否有 ≥65% 暗像素的行")
        print("       - 页面断裂处是内容区域，不是表格边框线 → 检测失败")
        print("    5. 拼接: 两页直接垂直拼接")
        print("    6. 缝隙来源: 断裂处 Page1 底部和 Page2 顶部各有少量白色间隙")
        print("       (Word 在页面分裂时在内容行之间添加的微小空白)")


def summarize_findings():
    """汇总所有发现"""
    print_header("汇总: 三个根因 + 数据流全图")

    print("""
  ┌──────────────────────────────────────────────────────────────────┐
  │                    完整数据流追踪图                               │
  ├──────────────────────────────────────────────────────────────────┤
  │                                                                  │
  │  Word 表格 (89行2列)                                             │
  │       │                                                          │
  │       ▼                                                          │
  │  row_count=89 ≥ 20 → 直接进入拓扑拆分                           │
  │       │                                                          │
  │       ▼                                                          │
  │  K系数计算: 3个采样全失败 → K=1.0                                │
  │  ⛔ 问题1: K 即使算出来也是死代码，从未被使用!                    │
  │       │                                                          │
  │       ▼                                                          │
  │  累加 Row.Height(pt) vs target_slice_pt=680.31pt                 │
  │  ⛔ 问题2: Row.Height 是最小行高，实际渲染高度≈1.65x             │
  │       │                                                          │
  │       ▼                                                          │
  │  cut_row=50 → 拆为 [1-49] 和 [50-89]                            │
  │       │                                                          │
  │       ├─── Fragment 1 (49 rows) ──┐                              │
  │       │                           │                              │
  │       │    PDF 导出 (2页)         │                              │
  │       │    ⛔ 问题3: 多页合并      │                              │
  │       │    边框去重未触发→缝隙     │                              │
  │       │         │                 │                              │
  │       │    合并: 4960×9422px      │                              │
  │       │    裁白: 2486×9422px      │                              │
  │       │         │                 │                              │
  │       │    calculate_xml_dimensions                              │
  │       │    w=104.73mm h=396.92mm  │                              │
  │       │         │                 │                              │
  │       │    pad_equation_for_centering                            │
  │       │    居中补白到 165mm        │                              │
  │       │    ⛔ 问题4: 无高度限制检查│                              │
  │       │    → wi=165.00 he=396.89  │                              │
  │       │                           │                              │
  │       └─── Fragment 2 (40 rows) ──┘                              │
  │            (同样流程)                                             │
  │            → wi=165.00 he=313.45                                 │
  │                                                                  │
  │       ▼                                                          │
  │  输出到 XML: he 远超 24cm 限制                                   │
  │  PDF 预览: 图片底部被截断显示不全                                │
  └──────────────────────────────────────────────────────────────────┘
""")

    print("  ⛔ 根因 #1 (主因): Row.Height 估算严重失准 + K系数是死代码")
    print("     • Row.Height 是 Word 的最小行高声明，不含文字换行后的实际扩展")
    print("     • 实际渲染高度 ≈ 1.65x Row.Height 累加值")
    print("     • K系数被设计来校正这个差异，但:")
    print("       a) 三个采样全部失败 → K=1.0 (无校正)")
    print("       b) 即使 K≠1.0，split_flow.py 中也从未使用 coeff_k 变量")
    print("     • 结果: 切在 row 50 时，片段实际高度≈39.7cm (目标24cm)")
    print()
    print("  ⛔ 根因 #2 (加重因): 全链路无高度后验检查")
    print("     • _capture_table_in_canvas 返回 h_mm 后无检查")
    print("     • _emit_fragments → _apply_table_centering_if_enabled 后无检查")
    print("     • pad_equation_for_centering 返回时无检查")
    print("     • 最终 he 值直接写入 XML，无任何上限保护")
    print()
    print("  ⛔ 根因 #3 (缝隙): PDF 多页合并的边框去重机制失效")
    print("     • Word 导出 PDF 时表格跨页，断裂在内容行中间")
    print("     • 去重算法只检测 4px 范围内 65% 暗像素的 '线条行'")
    print("     • 内容行不满足线条检测条件 → 去重不触发")
    print("     • 两页直接拼接，断裂处的微小白色间隙形成可见缝隙")

    print()
    print("  ⚙️  建议修复优先级:")
    print("     P0: 在 split_flow.py 中实际使用 K 系数校正 target_slice_pt")
    print("         或: 在片段截图后检查实际 h_mm，若超限则二次拆分")
    print("     P0: 在写入 XML 前添加 he ≤ max_height_mm 的强制检查")
    print("     P1: 修复 K 系数采样失败的问题 (检查 _sample_region_coefficient)")
    print("     P1: 改进 PDF 多页合并的缝隙检测算法:")
    print("         - 扩大检测窗口 (4px → 8-12px)")
    print("         - 降低暗像素阈值 (200 → 220) 和比例 (65% → 50%)")
    print("         - 或: 直接检测拼接处的窄白带并移除")
    print("     P2: 避免表格片段仍跨 PDF 页面 (动态设置 PDF 页高)")


def main():
    print("🔬 跨页长表格拆分问题 - 深度分析验证脚本")
    print(f"   分析对象: 表格 idx={TABLE_IDX}, {TABLE_ROWS}行{TABLE_COLS}列")
    print("   输出文件: sms_11.jpg (he=396.89mm), sms_12.jpg (he=313.45mm)")
    print(f"   限制: max_height = {MAX_HEIGHT_CM}cm = {MAX_HEIGHT_MM}mm")

    verify_split_decision()
    verify_pdf_rendering()
    verify_dimension_calculation()
    verify_height_ratio()
    verify_real_images()
    verify_seam_issue()
    summarize_findings()


if __name__ == "__main__":
    main()
