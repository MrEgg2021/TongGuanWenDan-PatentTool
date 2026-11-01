"""
测试脚本：验证表格拆分和高度计算的逻辑

目的：
1. 验证表格拆分时使用的高度估算方式（Word Row.Height 累加）
2. 验证最终生成的图片尺寸与估算值的差异
3. 验证居中补白后是否检查了高度限制
"""


# 测试数据（从日志中提取）
TEST_DATA = {
    "sms_11": {
        "word_table_width_pt": 296.85,  # wp_for_xml
        "original_img_px": (4960, 9422),  # 裁剪前
        "cropped_img_px": (2486, 9422),  # 裁剪后
        "xml_w_mm": 165.00,  # 最终 XML 中的宽度
        "xml_h_mm": 396.89,  # 最终 XML 中的高度
    },
    "sms_12": {
        "word_table_width_pt": 296.85,
        "original_img_px": (4960, 7441),
        "cropped_img_px": (2486, 7441),
        "xml_w_mm": 165.00,
        "xml_h_mm": 313.45,
    }
}

# 配置参数
WIDTH_FACTOR = 0.3528  # point -> mm
MAX_HEIGHT_CM = 24.0
MAX_HEIGHT_MM = MAX_HEIGHT_CM * 10.0  # 240mm


def calculate_xml_dimensions(original_width_point, processed_img_size):
    """模拟 calculate_xml_dimensions 函数"""
    w_px, h_px = processed_img_size

    # 基础换算
    width_mm = original_width_point * WIDTH_FACTOR

    # 根据裁剪后的宽高比计算高度
    if w_px > 0:
        height_mm = width_mm * (h_px / w_px)
    else:
        height_mm = 0

    # 最大宽度限制
    max_width = 165.00
    if width_mm > max_width:
        ratio = max_width / width_mm
        width_mm = max_width
        height_mm = height_mm * ratio

    return round(width_mm, 2), round(height_mm, 2)


def simulate_centering(current_width_mm, current_height_mm, target_width_mm, cropped_img_px):
    """模拟居中补白后的尺寸计算"""
    w_px, h_px = cropped_img_px

    # 计算 px/mm
    px_per_mm = w_px / current_width_mm

    # 目标画布宽度（像素）
    canvas_width_px = int(target_width_mm * px_per_mm)

    # 居中补白后的新尺寸
    new_width_mm = target_width_mm
    new_height_mm = target_width_mm * (h_px / canvas_width_px)

    return new_width_mm, new_height_mm, canvas_width_px


def main():
    print("=" * 80)
    print("表格拆分和高度计算逻辑验证")
    print("=" * 80)

    print("\n【配置参数】")
    print(f"  - 宽度因子 (width_factor): {WIDTH_FACTOR}")
    print(f"  - 最大高度限制: {MAX_HEIGHT_CM}cm = {MAX_HEIGHT_MM}mm")

    print("\n【步骤1：计算原始 XML 尺寸（居中补白前）】")
    for name, data in TEST_DATA.items():
        w_mm, h_mm = calculate_xml_dimensions(
            data["word_table_width_pt"],
            data["cropped_img_px"]
        )
        print(f"  {name}:")
        print(f"    - 输入: word_table_width_pt={data['word_table_width_pt']}, cropped_img_px={data['cropped_img_px']}")
        print(f"    - 计算: width_mm = {data['word_table_width_pt']} * {WIDTH_FACTOR} = {w_mm:.2f}mm")
        print(f"    - 计算: height_mm = {w_mm:.2f} * ({data['cropped_img_px'][1]} / {data['cropped_img_px'][0]}) = {h_mm:.2f}mm")

    print("\n【步骤2：居中补白后的尺寸】")
    for name, data in TEST_DATA.items():
        # 先计算原始尺寸
        w_mm, h_mm = calculate_xml_dimensions(
            data["word_table_width_pt"],
            data["cropped_img_px"]
        )

        # 模拟居中补白（目标宽度 165mm）
        new_w_mm, new_h_mm, canvas_px = simulate_centering(
            w_mm, h_mm, 165.0, data["cropped_img_px"]
        )

        print(f"  {name}:")
        print(f"    - 居中补白前: {w_mm:.2f}mm x {h_mm:.2f}mm")
        print("    - 目标宽度: 165.0mm")
        print(f"    - 像素密度: {data['cropped_img_px'][0]}px / {w_mm:.2f}mm = {data['cropped_img_px'][0]/w_mm:.2f} px/mm")
        print(f"    - 画布宽度: {canvas_px}px")
        print(f"    - 居中补白后: {new_w_mm:.2f}mm x {new_h_mm:.2f}mm")
        print(f"    - XML 实际输出: {data['xml_w_mm']}mm x {data['xml_h_mm']}mm")
        print(f"    - 高度检查: {new_h_mm:.2f}mm > {MAX_HEIGHT_MM}mm? {new_h_mm > MAX_HEIGHT_MM}")

    print("\n【问题分析】")
    print("  1. 居中补白函数返回的宽度固定为 165mm（或 145mm）")
    print("  2. 高度按比例计算，但【没有检查】是否超过 max_height_mm (240mm)")
    print("  3. 这导致最终输出的 he 值远超 24cm 限制")

    print("\n【核心问题】")
    print("  1. 表格拆分时使用 Word Row.Height 累加值判断")
    print("     - 这与最终图片高度不是 1:1 的关系")
    print("     - 导致拆分后的片段仍然超高")
    print("  2. 居中补白后没有高度限制检查")
    print("     - 直接输出到 XML，没有截断或预警")

    print("\n【建议修复方案】")
    print("  方案1: 在居中补白函数返回前添加高度检查")
    print("    - 如果 height_mm > max_height_mm:")
    print("      - 调整目标宽度使高度不超过限制")
    print("      - 或者返回警告/错误")
    print("  方案2: 在表格拆分时使用真实图片高度作为判断依据")
    print("    - 截取一小部分估算真实高度")
    print("    - 根据真实高度决定拆分位置")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
