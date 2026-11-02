# 开发与发布

## 本地主线

本项目从 V1.0.0 开始，在 main 上维护。修改前检查工作区；提交前检查暂存区，只处理目标文件。创建分支、远端、提交、推送和发布按当次授权执行。

## 版本控制边界

- 各级 `AGENTS.md` 与 `openspec/` 是维护者本地资料，由 `.gitignore` 忽略，不随 Git 分发。公开的模块导航、规则与流程维护在 README 与 `docs/` 中。
- 需要结构化的规格记录时，在保留 `openspec/` 的本地工作区执行校验；公开仓库以 README、`docs/` 和测试为准。
- `CPCXMLGui.spec` 是主程序的 PyInstaller 构建配置，保留并跟踪；`build/`、`dist/` 等构建产物继续忽略。
- 根目录 `LICENSE` 是项目源码许可证，`resources/LICENSE` 用于源码运行时展示，打包配置从根目录收集许可证。两份内容保持一致；第三方声明与组件许可继续保留，应随源码和发行文件保留。

## 版本基线

首版使用 `1.0.0`。修改版本时同步 `resources/config.yaml`、`resources/version_info_gui.txt`、用户手册和 `用户使用手册+更新日志/更新日志/v<版本>.md`，并检查版本契约测试。GUI 与 CLI 从配置读取版本，Windows 文件版本使用四段数字。

## 构建

按 README 建立独立 Python 环境并安装依赖。构建工具另需 PyInstaller、Nuitka 及其所需编译工具。先通过编译、静态检查、单元测试、资源和文本编码检查、OpenSpec 校验，再明确执行 `python tools/build_release_exes.py`。该入口先调用 `tools/build_nuitka_pyd.py --profile full_core` 编译核心模块，再按 `CPCXMLGui.spec` 打包，默认禁用 UPX；本地没有 `openspec/` 时跳过 OpenSpec 校验并输出提示。源码验证不能替代实际 EXE 验证。

- 没有 Visual Studio 的机器执行 `python tools/build_release_exes.py --compiler mingw64`，由 Nuitka 自动下载 MinGW。
- 构建前把 `TMP`、`TEMP`、`TMPDIR` 指向不含空格的目录（如 `D:\tgdtmp`）；指向带空格的目录会让 MinGW 的 LTO 链接报 `lto1.exe: fatal error: could not open symbol resolution file`。

## 公开前检查

- 核查模板、图标、字形图片、DTD、代码表及其他素材的来源与再分发权；项目源码许可不代表这些素材已获再分发授权。
- 检查待提交文件、截图及文本是否含真实客户信息、密钥、内部链接或本地绑定。
- 对实际构建环境重新整理依赖版本和第三方许可，保留原声明及要求的许可证文本。
- 核对实际打包环境的 PyMuPDF、PySide6 等关键依赖版本，同步根目录与 `resources/` 下的 `THIRD_PARTY_NOTICES.md`，两份内容保持一致。
- 确认 README 展示素材（logo、图标、截图）与当前产品名称一致；含旧名称文字的图片应在公开推送前替换。
- 确认 README 中的 `USERNAME` 占位符已全部替换为实际账号，下载页链接可正常打开。
- 完成 GUI、实际 Word 转换和预览验证，记录通过与跳过数量。

## 发布 AGPL 程序

发布前确定公开仓库地址，为每个 EXE 提供该版本完整对应源码及必要构建脚本的清晰入口；不能只链接持续变化的 main。保留 LICENSE、第三方声明和组件许可，确认 EXE 资源均打包。创建发布记录并核对源码 ref、产品版本、标签和实际附件；用户更新日志只描述可感知变化。

对外发版前先生成 release manifest 与内部证据，再根据 manifest + internal evidence + Git diff 手工维护用户更新日志；脚本不得直接覆盖最终用户更新日志文件。用户更新日志不得直接暴露 commit hash、OpenSpec id、测试命令和打包细节。

公开仓库、提交、推送、打包和发布按当次授权执行。产品为离线便携软件，没有安装升级或 OTA 流程。
