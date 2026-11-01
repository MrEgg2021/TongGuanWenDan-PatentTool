import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "tools" / "全国行政区编码表-utf-8.csv"
OUT_PATH = ROOT / "core" / "regions_cn.py"


def build_data():
    provinces = []
    cities_by_province: dict[str, list[dict[str, str]]] = {}

    with CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        # 跳过表头
        next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            code = (row[0] or "").strip()
            name = (row[1] or "").strip()
            if not code or not name:
                continue
            parts = [p.strip() for p in name.split(",") if p.strip()]
            if not parts:
                continue

            # 一级：省/直辖市/自治区/特别行政区
            if len(parts) == 1:
                provinces.append({"code": code, "name": parts[0]})
                cities_by_province.setdefault(code, [])
                continue

            # 其他：根据名称段和代码推导所属省，以及是否视作二级单位
            # 普通二级：省,地级市
            if len(parts) == 2:
                prov_code = code[:2] + "0000"
                city_name = parts[1]
                bucket = cities_by_province.setdefault(prov_code, [])
                bucket.append({"code": code, "name": city_name})
                continue

            # 三级：省,市,县/区
            # 特殊情况：如 139001,"河北省,定州市,定州市"，第二段与第三段相同，可视作直管市（当作二级）
            if len(parts) == 3 and parts[1] == parts[2]:
                prov_code = code[:2] + "0000"
                city_name = parts[1]
                bucket = cities_by_province.setdefault(prov_code, [])
                bucket.append({"code": code, "name": city_name})
                continue

            # 其他三级行政单位（普通区县）忽略，由用户在详细地址中填写

    # 排序，保证代码从小到大，体验更好
    provinces.sort(key=lambda x: x["code"])
    for prov_code in list(cities_by_province.keys()):
        cities_by_province[prov_code].sort(key=lambda x: x["code"])

    return provinces, cities_by_province


def main() -> None:
    provinces, cities_by_province = build_data()

    lines: list[str] = []
    lines.append("# -*- coding: utf-8 -*-")
    lines.append(
        "# 中国行政区划（省/市）常量，由 tools/gen_regions_cn.py 从全国行政区编码表生成。"
    )
    lines.append("# 运行时不再读取 CSV。")
    lines.append("")
    lines.append("PROVINCES = " + repr(provinces))
    lines.append("")
    lines.append("CITIES_BY_PROVINCE = " + repr(cities_by_province))

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
