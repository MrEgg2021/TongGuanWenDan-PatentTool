# 第三方声明

版权所有 © 2026 MrEgg2021 及贡献者。

项目自有代码采用 **AGPL-3.0-only**。第三方代码、模板、图像、数据和工具保留各自的版权及许可条件，项目根目录的 `LICENSE` 不改变这些条件。程序不提供担保，具体范围以适用的许可证原文为准。

本文件是第三方组件与资源的中文说明，不替代各组件的许可证原文。许可证标识、组件名和原始版权归属保留原文。

## 运行依赖清单

下表保留本地核验环境的版本记录，不是依赖锁定文件，也不代表每次构建都使用相同版本。已安装发行包提供的完整许可证文本保存在 `resources/third_party_licenses/`。发布 EXE 前应核对实际分发的组件，包括 Qt 插件与本地库。

| 组件 | 已核验环境的版本记录 | 组件声明的许可 |
| --- | --- | --- |
| certifi | 2025.11.12 | MPL-2.0 |
| cffi | 2.0.0 | MIT |
| charset-normalizer | 3.4.4 | MIT |
| cryptography | 42.0.8 | Apache-2.0 OR BSD-3-Clause |
| et_xmlfile | 2.0.0 | MIT |
| idna | 3.11 | BSD-3-Clause |
| lxml | 6.0.2 | BSD-3-Clause |
| numpy | 2.2.6 | 见附带的许可证文本及组件元数据 |
| opencv-python | 4.12.0.88 | Apache 2.0 |
| openpyxl | 3.1.5 | MIT |
| pillow | 12.0.0 | MIT-CMU |
| psutil | 7.1.3 | BSD-3-Clause |
| pycparser | 3.0 | BSD-3-Clause |
| PyMuPDF | 1.26.6 | 双重许可：AGPL 第 3 版或 Artifex 商业许可 |
| pypinyin | 0.55.0 | MIT |
| PySide6 | 6.9.1 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySide6_Addons | 6.9.1 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySide6_Essentials | 6.9.1 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| python-docx | 1.2.0 | MIT |
| pywin32 | 305 | PSF |
| PyYAML | 6.0.3 | MIT |
| reportlab | 4.4.5 | BSD 许可（详见 license.txt）；Copyright (c) 2000-2025, ReportLab Inc. |
| requests | 2.32.5 | Apache-2.0 |
| shiboken6 | 6.9.1 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| typing_extensions | 4.15.0 | PSF-2.0 |
| urllib3 | 2.5.0 | MIT |

PyMuPDF/MuPDF 采用 AGPL 或另行取得的 Artifex 商业许可，说明见：
https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright

Qt for Python/PySide6 及 Qt 原生组件保留各自适用的 LGPL、GPL 或其他许可，说明见：
https://doc.qt.io/qtforpython-6/licenses.html

## 外部软件

Microsoft Word、WPS 和 CNIPAClient 不包含在本项目源码分发中，用户应按相应条款自行取得和使用。CNIPA 预览组件仅在本机使用，对官方安装目录保持只读。本项目不授予重新分发官方 JAR、运行环境、字体、商标或 Microsoft 软件的权利。

## 发布前需要核查权属的资源

项目标志与图标、Word 插图、`resources/assets/rarelyWord/` 字形图片、DOCX 模板、DTD 及代码表数据用于相应本地功能，其来源与再分发权尚未全部核实。

项目代码的开源许可不代表这些第三方资源可以自由再分发。公开发布前，应确认相关权利；无法确认的资源应替换或取得授权。

## 分发材料

发布时保留 `LICENSE`、本声明和各组件许可证，并提供该发布版本完整对应源码及必要构建脚本的获取方式。源码入口应在实际发行说明中明确列出。

## 对应源码获取

分发 EXE 时，按 AGPL 第 6 条需要能够提供该版本的完整对应源码。版本对应关系与源码来源如下；表中版本为本仓库核验环境的记录，实际以构建记录为准。

| 对象 | 版本对应方式 | 源码来源 |
| --- | --- | --- |
| 本项目自有代码 | 与 EXE 文件名中的版本号一致 | 同一 Git 发布标记的源码归档，含依赖清单、`CPCXMLGui.spec` 与 `tools/build_nuitka_pyd.py` 等构建脚本 |
| PyMuPDF | 与打包环境安装版本一致（核验记录 1.26.6） | PyPI 源码分发包，或 https://github.com/pymupdf/PyMuPDF 对应 tag |
| MuPDF | 随所用 PyMuPDF 捆绑，版本以其发行说明为准 | https://github.com/ArtifexSoftware/mupdf 对应 tag |
| PySide6 / Qt | 与打包环境安装版本一致（核验记录 6.9.1） | https://download.qt.io/official_releases/qt/ 对应版本源码 |

PyMuPDF 与 MuPDF 以未修改形式随程序分发，可直接使用上游发布的对应版本源码；如对这些组件做过本地修改，应改为提供修改后的源码。以上来源只说明源码位置，不改变各组件的许可条件。

## 名称与图标

本项目名称“通官文旦-专利工具”、项目图标与发行标识仅用于标识官方发行版本。AGPL-3.0-only 授予的是著作权许可，不包含商标或名称使用许可。

任何人都可以基于本项目修改并对外分发，这是许可证明确允许的行为；但分发修改版时应使用自己的名称与图标，并说明修改内容，避免使用者误认为官方发行版。

## GitHub 图标

关于页使用的 `resources/assets/github.svg` 来自 GitHub Octicons 的 `mark-github-16` 图标，采用 MIT 许可。

版权声明：Copyright (c) 2026 GitHub Inc.

来源：https://github.com/primer/octicons/blob/main/icons/mark-github-16.svg

完整许可原文保存在 `resources/third_party_licenses/Octicons-MIT.txt`。
