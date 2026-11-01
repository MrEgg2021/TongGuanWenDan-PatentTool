from lxml import etree
import os
import logging
import re
import math

class XMLBuilder:
    """
    XML 生成引擎
    负责：构建符合 DTD 的 XML 树、ID 生成
    """
    def __init__(self, config):
        self.config = config
        self._logger = logging.getLogger(__name__)
        self.root = None
        self.id_counters = {
            'p': 0,
            'img_desc': 0, # 说明书图片
            'img_draw': 0, # 附图
            'claim': 0
        }

    def init_xml(self, root_tag="cn-application-body"):
        """初始化 XML 树"""
        # 命名空间映射 (如果有的话，但 CPC DTD 好像没有强命名空间，直接用 Default)
        self.root = etree.Element(root_tag, lang="zh", country="CN")
        self.tree = etree.ElementTree(self.root)
        self._logger.info(f"🌳 XML 树初始化: <{root_tag}>")
        return self.root

    def get_next_id(self, type_key):
        """获取下一个 ID"""
        # 统一图片 ID：img_desc / img_draw 共用一套计数，全部生成为 idf_****
        # 未来附图 <figure> 节点的 ID (f****) 将由单独的计数器负责
        if type_key in ('img_desc', 'img_draw'):
            base_key = 'img_desc'
            self.id_counters[base_key] = self.id_counters.get(base_key, 0) + 1
            # 保持 img_draw 计数与 img_desc 同步，便于调试查看
            self.id_counters['img_draw'] = self.id_counters[base_key]
            count = self.id_counters[base_key]
        else:
            self.id_counters[type_key] = self.id_counters.get(type_key, 0) + 1
            count = self.id_counters[type_key]

        if type_key == 'p':
            return f"p{count:04d}"
        elif type_key in ('img_desc', 'img_draw'):
            return f"idf_{count:04d}"
        elif type_key == 'claim':
            # PRD 2.4.2: c1_cl001
            # 注意：权利要求的 ID 格式可能比较特殊，通常是 cl+数字 或者 c1_cl+数字
            # 这里遵循 PRD: c1_cl + 3位流水
            return f"c1_cl{count:03d}"
        return str(count)

    def create_section(self, parent, tag_name, **attrs):
        """创建章节节点 (如 cn-claims, description)"""
        section = etree.SubElement(parent, tag_name, **attrs)
        return section

    def create_paragraph(self, parent, text=None, num=None, is_claim=False):
        """
        创建段落节点
        is_claim=True: 生成 <claim> 结构 (需特殊处理)
        is_claim=False: 生成 <p> 结构
        """
        if is_claim:
            # 权利要求: <claim id="c1_cl001" num="1"><claim-text>...</claim-text></claim>
            claim_id = self.get_next_id('claim')
            if num is None:
                num = str(self.id_counters['claim'])
                
            claim_node = etree.SubElement(parent, "claim", id=claim_id, num=num)
            text_node = etree.SubElement(claim_node, "claim-text")
            if text:
                text_node.text = text
            return text_node # 返回存放内容的节点
            
        else:
            # 普通段落: <p id="p0001" num="0001" Italic="0">text</p>
            p_id = self.get_next_id('p')
            if num is None:
                # 说明书段落号 4位
                # 注意：说明书段落号通常是连续的，但在 description 下可能会有多个子节
                # 这里假设调用者负责传递正确的 num 或者我们维护全局 num
                # 简单起见，我们维护一个全局 description 段落计数? 
                # PRD 说：说明书 num: 4位数字 (0001), 全文连续
                current_num = int(p_id[1:]) # 从 p0001 中提取 1
                num = f"{current_num:04d}"
            
            p_node = etree.SubElement(parent, "p", id=p_id, num=num, Italic="0")
            if text:
                p_node.text = text
            return p_node

    def _clamp_drawings_image_dimensions(self, width_mm, height_mm):
        """
        仅用于说明书附图(img_type="draw")：
        - wi/he 必须同时不超过配置上限
        - 仅在超限时按同一缩放系数等比缩小（不放大）
        - 通过等比缩放避免官方 PDF 预览拉伸畸变
        """
        try:
            w = float(width_mm)
            h = float(height_mm)
        except Exception:
            return width_mm, height_mm

        if w <= 0 or h <= 0:
            return w, h

        try:
            max_w = float(self.config.get("drawings_img_max_wi_mm", 164.0))
        except Exception:
            max_w = 164.0
        try:
            max_h = float(self.config.get("drawings_img_max_he_mm", 230.0))
        except Exception:
            max_h = 230.0

        if max_w <= 0 or max_h <= 0:
            return w, h

        # 不超限则原样返回（不强行放大到上限）
        if w <= max_w and h <= max_h:
            return w, h

        scale = min(max_w / w, max_h / h, 1.0)
        if scale <= 0:
            return w, h

        ratio = h / w
        w2 = w * scale
        # 为确保“严格不超过”，对 2 位小数做向下截断（不会放大）
        w2 = math.floor(w2 * 100.0) / 100.0
        h2 = w2 * ratio
        h2 = math.floor(h2 * 100.0) / 100.0

        return w2, h2

    def create_image_node(self, parent, img_filename, width_mm, height_mm, img_type='desc', inline=True):
        """
        创建图片节点
        img_type: 'desc' (说明书/摘要), 'draw' (附图)
        """
        if img_type == "draw":
            width_mm, height_mm = self._clamp_drawings_image_dimensions(width_mm, height_mm)

        img_id = self.get_next_id('img_desc' if img_type == 'desc' else 'img_draw')

        fmt = "jpg"
        try:
            ext = os.path.splitext(str(img_filename or ""))[1].lower()
        except Exception:
            ext = ""
        if ext in (".tif", ".tiff"):
            fmt = "tif"
        elif ext in (".jpg", ".jpeg"):
            fmt = "jpg"
        
        # <img id="idf_0001" file="xxx.jpg" img-format="jpg" wi="100.00" he="50.00" inline="yes"/>
        attrs = {
            "id": img_id,
            "file": img_filename,
            "img-format": fmt,
            "wi": f"{width_mm:.2f}",
            "he": f"{height_mm:.2f}",
            "inline": "yes" if inline else "no"
        }
        
        img_node = etree.SubElement(parent, "img", **attrs)
        return img_node

    def save(self, output_path):
        """保存 XML 文件"""
        # 序列化业务根节点本身（不带 XML 声明 / DOCTYPE）
        body = etree.tostring(
            self.root,
            encoding="unicode",
            pretty_print=False
        )

        try:
            body = re.sub(r"(</(?:p|heading|claim)>)<", r"\1\n<", body)
        except Exception:
            pass

        header_lines = [
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
            "<?xml-stylesheet type=\"text/xsl\" href=\"/dtdandxsl/showxml.xsl\"?>",
            "<!DOCTYPE cn-application-body SYSTEM \"/dtdandxsl/cn-application-body-20080416.dtd\">",
        ]

        xml_text = "\n".join(header_lines) + "\n" + body

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_text)

        self._logger.info(f"💾 XML 已保存: {output_path}")
