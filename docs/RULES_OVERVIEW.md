# 通官文旦-专利工具规则总览

> 本文档汇总并固化本项目当前阶段已确认的 **结构 / 命名 / 图片与公式处理规则**，
> 用于查找当前实现中的结构规则。规则以代码与测试为准；本文是维护摘要，不替代这些来源。

## 0. 开发者快速导航

### 0.1 本文档定位与优先级

- 本文件用于为开发与测试提供“**可操作的规则总表**”（尤其是 XML 结构、ID/命名、图片/公式的 wi/he/inline 口径）。
- 官文处理规则以 `core/official_docs/` 与对应测试为准。

### 0.2 配置文件与加载方式（开发视角）

- 默认配置文件位于：`resources/config.yaml`。
- 代码加载入口：`core/config.py::load_config()`
  - 其中通过 `core/paths_utils.py::get_resource_path("config.yaml")` 解析到运行时资源目录。
- 运行时覆盖：转换流程会对配置做覆盖/合并（例如 GUI/调用方透传的 image_processing_overrides），见 `core/conversion.py`。

### 0.3 关键配置项 ↔ 代码落点（索引）

| 配置键（层级） | 当前默认值（配置值或代码缺省） | 含义（简述） | 主要代码落点 |
|---|---:|---|---|
| `defensive.claim_big_eq_width_mm` | `120.0` | 权利要求中“大公式”阈值（mm），达到阈值则作为块级图片拆段 | `core/document_parser/paragraph_inline_impl/process.py` |
| `equation_display_scale_ratio` | `0.8` | 公式显示缩放倍数（影响 PDF 视觉大小）；居中块公式在 `lossless_canvas` 模式下保留主体像素，通过扩画布实现等效视觉缩放 | `core/conversion.py`、`core/document_parser/paragraph_inline_impl/output_writer.py`、`core/document_parser/paragraph_inline_impl/eq_centering.py`、`core/document_parser/output_mixin.py` |
| `equation_centering.enabled` | `true` | 是否启用高级公式居中补白 | `core/document_parser/paragraph_inline_impl/process.py`、`core/document_parser/output_mixin_impl.py` |
| `equation_centering.precise.line_width_mm` | `165.0` | 行宽（mm），用于居中补白/目标宽度计算 | `core/document_parser/paragraph_inline_impl/eq_centering.py`、`core/document_parser/table_mixin.py`、`core/document_parser/output_mixin_impl.py` |
| `equation_centering.precise.desc_reserved_mm` | `20.0` | 说明书段号/边距预留（mm） | `core/document_parser/paragraph_inline_impl/eq_centering.py`、`core/document_parser/table_mixin.py` |
| `equation_centering.precise.claim_visual_offset_mm` | `0.0` | 权利要求居中视觉偏移（mm） | `core/document_parser/paragraph_inline_impl/eq_centering.py`、`core/document_parser/table_mixin.py`、`core/document_parser/output_mixin_impl.py` |
| `image_processing.equation_center_text_width_mm` | `165.0` | 居中补白目标行宽（mm），用于扩展画布 | `core/image_processing/equation_ops.py::pad_equation_for_centering()` |
| `image_processing.equation_center_scale_mode` | `lossless_canvas` | 居中块公式缩放模式：`resample` / `lossless_canvas`（不缩主体像素，改为扩画布） | `core/image_processing/equation_ops.py::pad_equation_for_centering()` |
| `image_processing.equation_center_lossless_max_canvas_width_px` | `10000` | `lossless_canvas` 模式画布宽度上限（超上限自动回退 `resample` 并记录日志） | `core/image_processing/equation_ops.py::pad_equation_for_centering()` |
| `image_processing.width_factor` | （缺省）`0.3528` | Points→mm 换算系数（wi 计算） | `core/document_parser/image_shape_ops/handle_shape_ops.py` |
| `image_processing.max_width_mm` | （缺省）`165.0` | wi 最大宽度限制（mm） | `core/img_processor.py::calculate_xml_dimensions()`、`core/img_processor.py::calculate_equation_dimensions()` |
| `drawings_fidelity.mode` | `smart` | 说明书附图清晰度策略；`smart` 下 EMF/WMF 按目标 DPI 重新渲染，PNG/JPG 只检测有效 DPI | `core/document_parser/image_shape_mixin.py`、`core/document_parser/image_shape_ops/drawings_extract_ops.py` |
| `drawings_fidelity.target_dpi` | `300` | 附图 EMF/WMF 高保真渲染目标有效 DPI，同时作为源位图低 DPI 告警阈值 | 同上 |
| `drawings_fidelity.output_format` | `jpg` | 说明书附图默认输出格式，当前默认仍为 JPG | 同上、`core/xml_generator.py::create_image_node()` |
| `drawings_fidelity.low_dpi_policy` | `warn` | PNG/JPG 源位图低于目标有效 DPI 时转档继续并在结果中提示 | `core/document_parser/image_shape_mixin.py`、`gui/single_run_impl/postprocess_flow.py` |

---

## 1. XML 文件与章节映射

- **100001/100001.xml**：权利要求书，对应根节点 `<cn-claims>`。
- **100002/100002.xml**：说明书，对应根节点 `<description>`。
- **100003/100003.xml**：说明书附图，对应根节点 `<cn-drawings>`。
- **100004/100004.xml**：说明书摘要，对应根节点 `<cn-abstract>`。
- **110101/110101.xml**：发明专利请求书；结构以 `core/request_form_xml_impl/`、对应测试和 OpenSpec 为准。

> 章节归属由 **页眉识别** 决定：
> - `权利要求书` → claims → 100001
> - `说明书` → description → 100002
> - `说明书附图` / `摘要附图` → drawings → 100003
> - `说明书摘要` → abstract → 100004

---

## 2. ID 与编号规则总表

### 2.1 段落与标题

- **说明书段落 `p`**：
  - `id = "p" + 4 位流水`，如 `p0001`、`p0002`。
  - `num = 4 位数字`，如 `0001`、`0002`，在说明书内部连续。
- **摘要段落 `p`**：
  - 与说明书共用 `p` + 4 位流水（如 `p0001`），代码未定义独立前缀；
  - `num = 4 位数字`，如 `0001`。
- **标题/小节 heading**：
  - `id = "h" + 4 位流水`，如 `h0001`；
  - `level` 根据标题层次取值（样本中常见为 `level="2"`）。
- **发明名称标题**：
  - `<invention-title id="t0001">`。

### 2.2 权利要求

- `<cn-claims>` 下为若干 `<claim>`：
  - `id = "c1_cl" + 3 位流水`，如 `c1_cl001`；
  - `num = 整数`，如 `1`、`2`、`3`。
- 每个 `<claim>` 内部：
  - **至少**包含一个 `<claim-text>` 作为内容承载节点，
    允许根据需要拆分为多个 `<claim-text>`（例如将大公式或“公式+编号”单独成段）；
  - 文本、图片、公式截图全部放在这些 `<claim-text>` 中；
  - 不在 `<claim>` 下直接挂 `<p>` 段落。

### 2.3 图片与 figure ID

- **图片 `img` 元素 ID**：
  - 正文图片（权利要求 / 说明书 / 附图）统一使用
    `id="idf_" + 4 位流水`，如 `idf_0001`、`idf_0002`；
  - 同一案卷中共用一套 `idf_****` 序列。
- **附图 `figure` ID**：
  - `id="f" + 4 位流水`，如 `f0001`；
  - `num="0001"`、`figure-labels="图 1"` 等属性按样本生成；
  - `figure` 内部只包含一个 `<img>`（`id="idf_****"`，`file="ft_n.jpg"`）。

---

## 3. 图片文件命名规则（按文种前缀）

### 3.1 前缀与含义

- **权利要求书（100001）**：
  - 文件名：`qlyqs_{n}.jpg`；
  - 前缀含义：`qlyqs` = QuanLiYaoQiuShu（权利要求书）。
- **说明书（100002）**：
  - 文件名：`sms_{n}.jpg`；
  - 前缀含义：`sms` = ShuoMingShu（说明书）。
- **说明书附图（100003）**：
  - 文件名：`ft_{n}.jpg`；
  - 前缀含义：`ft` = FuTu（附图）。

### 3.2 统一约束

- 各文种内部的 `{n}` 从 1 开始独立递增，不跨文种复用。
- **所有图片**（包括：
  - 公式截图；
  - 表格截图；
  - 附图插图等）
  都必须使用所属文种对应的前缀。
- XML 中：
  - `img` 的 `file` 属性必须等于上述文件名（如 `file="sms_20.jpg"`）；
  - `img` 的 `id` 使用 `idf_****`，与文件名无直接对应关系。

---

## 4. 权利要求内容结构规则

- `cn-application-body` → `<cn-claims>` → 多个 `<claim>`。
- 每个 `<claim>`：
  - **至少**包含一个 `<claim-text>`；
  - 允许根据需要拆分为多个 `<claim-text>`，以便让大公式或“公式+编号整行”单独成段；
  - 文本、行内 `<img>` 和块级 `<img>` 均放在这些 `<claim-text>` 中。
- 示例结构：

```xml
<cn-claims>
  <claim id="c1_cl001" num="1">
    <!-- 普通行内公式：与文本同段、inline="yes" -->
    <claim-text>
      一种基于……的方法，其特征在于……
      零运动矢量的权重<img id="idf_0007" file="qlyqs_7.jpg" inline="yes" wi="61.00" he="17.00"/>，其中……
    </claim-text>

    <!-- 大公式或“公式+编号整行”：单独成段、inline="no" -->
    <claim-text>
      <img id="idf_0020" file="qlyqs_20.jpg" inline="no" wi="141.12" he="16.49"/>
    </claim-text>
    <claim-text>
      其中，I_fused 为融合后的最终像素值，w_mean 为均值权重，w_max 为最大值权重……
    </claim-text>
  </claim>
</cn-claims>
```

---

## 5. 公式与图片处理统一规则

### 5.1 公式转图与块级/行内策略

- 复杂公式（包括 Equation Editor / OMML 等）一律 **转图片**，不尝试在 XML 中保留原始公式语义；
- 在不同章节中，根据版式需求区别对待：
  - **说明书 (`<description>`)：**
    - 普通行内小公式：作为 `<img inline="yes" .../>` 嵌入对应 `<p>`；
    - 整段仅包含单个公式时，可在配置开启 `equation_centering`，对图片左右补白为接近版心宽度的画布，并作为块级段落输出（公式图片独占一行）；
    - “公式 + 右侧编号”整行（如 `公式 … （1）`）：对包含公式与编号的整行做联合截图，图片中同时包含公式和编号，作为块级段落输出。
  - **权利要求 (`<cn-claims>`)：**
    - 普通行内小公式：在 `<claim-text>` 中以 `<img inline="yes" .../>` 方式嵌入，保持与文字同一行；
    - “公式 + 右侧编号”整行：
      - 先对“公式 + 编号(1)”做整行截图，图片中带编号，编号不再以纯文本出现在 XML 中；
      - 该图片放在单独的 `<claim-text>` 段落中，作为块级图片独占一行；后续“其中 …”等说明文字放入新的 `<claim-text>` 中；
    - 宽度大于等于阈值 `defensive.claim_big_eq_width_mm`（默认 `120.0` mm）的**大公式**：
      - 统一视为块级公式图片，设置 `inline="no"`，
      - 在 `<claim>` 内拆成多个 `<claim-text>`：前一段承载纯文本，中间一段承载大公式图片，后一段承载后续说明文字，防止前一段最后一行被两端对齐拉伸。

> 说明：`defensive.claim_big_eq_width_mm` 用于控制“多宽的公式视为需要单独成段的大公式”，
> 不同版式下可按需要在 `resources/config.yaml` 中调优该阈值。

### 5.2 `inline`、`img-format` 与尺寸属性

- 公式图片的 `inline` 语义：
  - `inline="yes"`：视为行内图片，紧跟在文字后面，与文字共享同一行的两端对齐行为；
  - `inline="no"`：视为块级图片，通常独占一整行（在权利要求中对应单独的 `<claim-text>` 段落，在说明书中对应单独的 `<p>` 段落）。
- 当前规则：
  - 普通行内小公式统一使用 `inline="yes"`；
  - 说明书中的“整段单公式”、说明书和权利要求中的“公式+编号整行”、以及权利要求中宽度≥`claim_big_eq_width_mm` 的大公式，统一使用 `inline="no"` 作为块级图片；
  - 其它图片/表格等仍按各自场景的既有规则设置 `inline`（例如表格截图通常为块级）。
- 所有公式图片与截图：
  - `img-format="jpg"`；
  - `wi` / `he` 必须存在，单位为 mm，推荐保留 2 位小数；
  - 宽度计算：`W_mm = Width_point × 0.3528`（其中 `0.3528` 为 `image_processing.width_factor` 的默认值）；
  - 高度计算：`H_mm = W_mm × (H_px / W_px)`；
  - 超过版心宽度 165mm 时，强制 `wi=165.00` 并按比例缩放 `he`（对应 `image_processing.max_width_mm` 的默认值）。

### 5.3 截图与裁剪要点

- 截图区域只包含目标对象本体：
  - 行内公式：只截公式，不截前后文字；
  - 独立公式：只截公式本体，避免把整段空白一起打包。
- OpenCV 裁剪规则：
  - 找到非白区域的最小包围盒；
  - 按比例在上下左右增加对称 padding，保留少量留白；
  - 目标是让图片的几何中心与文本行的中线对齐，避免“贴顶/贴底”。

---

## 6. 附图 figure 结构摘要

- `cn-application-body` → `<cn-drawings>` → 多个 `<figure>`。
- 每个 `<figure>`：
  - `id="f0001"`、`num="0001"`、`figure-labels="图 1"`；
  - 内部仅包含一个 `<img id="idf_0001" file="ft_1.jpg" img-format="jpg" inline="yes" wi="165.00" he="131.57"/>`；
  - 不额外用 `<p>` 包裹。

---

## 7. 规则来源与维护约定

- 当前 XML 结构规则以实现代码与对应测试为准；本文件只提供导航与摘要。
- 规则变更时更新对应规格和测试；仅在本摘要仍准确时同步维护本文件。

---

## 8. 生僻字图片资源库（rarelyWord）

- `resources/assets/rarelyWord/` 当前包含 `1.jpg ~ 50.jpg`，作为“生僻字/冷门字符字形图片资源”保留；公开前仍需核查素材权属。
- 当前阶段：
  - 尚未建立“字符/码位 ↔ 图片文件”的映射表；
  - 转换引擎不会自动使用该目录中的图片，只将其视为后续实现“生僻字转图片显示”能力的预备资源库。
- 未来如需启用：
  - 需通过配置文件维护“生僻字字符或 Unicode 码位 ↔ resources/assets/rarelyWord/N.jpg”的映射关系；
  - 在 XML 生成阶段检测到对应生僻字时，将其替换为行内 `<img>`，并仍然遵守统一的图片 ID 与文件命名规则（`idf_****`、`qlyqs_/sms_/ft_` 前缀等）。

---

## 9. 代码架构与模块化约定

- **入口层（tools/cli_main.py / gui_app.py / gui/**）  
  - 只负责参数解析、UI 交互、拉起转换流程。  
  - 不在入口层直接编写 XML 结构或复杂业务规则。
- **文档解析核心（core/document_parser/*.py）**  
  - `DocumentParser` 由多个 mixin 组合而成，各自职责如下：  
    - `SectionsMixin`：章节识别与页眉解析。  
    - `ParagraphTraversalMixin`：段落遍历与内容解析。  
    - `TableProcessingMixin`：表格截图与相关规则。  
    - `ImageEquationMixin`：图片 / 公式截图逻辑。  
    - `ClaimsMixin`：权利要求文本聚合与 `<claim>` 结构规则。  
    - `StructureNormalizationMixin`：说明书/附图结构规范化与段号重排。  
    - `OutputGenerationMixin`：XML 生成与 ZIP 打包。
- **输出与 data-bus**  
  - `core/data_bus_xml.py` 中的 `create_data_bus(...)` 负责 `data-bus.xml` 生成。  
  - 其它模块通过调用该函数接入 data-bus，不在本地私自拼装结构。
- **后续开发约束**  
  - 新增解析 / 结构 / 输出能力时，必须优先在 `core/document_parser/*.py` 或其他 `core/*.py` 模块中实现；  
  - **禁止** 将复杂业务逻辑继续堆积在 `tools/cli_main.py` 或 GUI 代码中；  
  - 涉及 XML 结构或字段的变更，应更新对应测试及本文件中仍适用的摘要。
