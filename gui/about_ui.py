from html import escape
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QTextBrowser, QVBoxLayout,
)

from core.config import get_app_display_title
from core.paths_utils import get_resource_path
from gui.update_log_dialog import show_update_log_dialog


def _show_license_dialog(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle("开源许可与第三方声明")
    dialog.resize(760, 560)
    layout = QVBoxLayout(dialog)
    tabs = QTabWidget()
    for label, filename in (
        ("开源许可（中文说明）", "OPEN_SOURCE_LICENSE.zh-CN.md"),
        ("第三方声明", "THIRD_PARTY_NOTICES.md"),
        ("AGPL 英文原文", "LICENSE"),
    ):
        browser = QTextBrowser()
        text = Path(get_resource_path(filename)).read_text(encoding="utf-8")
        if filename.endswith(".md"):
            browser.setMarkdown(text)
        else:
            browser.setPlainText(text)
        tabs.addTab(browser, label)
    layout.addWidget(tabs, 1)
    buttons = QDialogButtonBox(QDialogButtonBox.Close)
    buttons.button(QDialogButtonBox.Close).setText("关闭")
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()
    dialog.deleteLater()


def build_about_page(window):
    page = QFrame()
    page.setObjectName("aboutPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)
    heading = QLabel("关于")
    heading.setProperty("role", "h1")
    layout.addWidget(heading)
    card = QFrame()
    card.setObjectName("Card")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(24, 24, 24, 24)
    card_layout.setSpacing(16)
    title = QLabel(get_app_display_title())
    title.setProperty("role", "h2")
    title.setWordWrap(True)
    card_layout.addWidget(title)
    info = QLabel(
        "专利文档转换与官文处理工具\n"
        "全部功能免费使用 · AGPL-3.0-only"
    )
    info.setProperty("role", "body")
    info.setWordWrap(True)
    card_layout.addWidget(info)
    github_icon = escape(Path(get_resource_path("assets/github.svg")).as_posix())
    contact = QLabel(
        f'作者：<img src="{github_icon}" width="16" height="16" alt="GitHub"> MrEgg2021<br>'
        "邮箱：1649251313@qq.com<br>微信：MrEgg208"
    )
    contact.setProperty("role", "body")
    contact.setWordWrap(True)
    contact.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
    card_layout.addWidget(contact)
    repo_link = QLabel(
        '开源仓库：<a href="https://github.com/MrEgg2021/TongGuanWenDan-PatentTool">GitHub</a>'
        ' ｜ 国内镜像：<a href="https://gitee.com/mregg2021/TongGuanWenDan-PatentTool">Gitee</a>'
    )
    repo_link.setProperty("role", "body")
    repo_link.setOpenExternalLinks(True)
    repo_link.setTextInteractionFlags(Qt.TextBrowserInteraction)
    card_layout.addWidget(repo_link)
    download_link = QLabel(
        '软件下载：<a href="https://github.com/MrEgg2021/TongGuanWenDan-PatentTool/releases/latest">GitHub Releases</a>'
        ' ｜ <a href="https://tcnss0u1hgy9.feishu.cn/docx/O5f5d9AWHop5OjxkhakcP3Jkntb">飞书文档（国内直连）</a>'
        "<br>本程序为免安装的便携版 EXE；Gitee 受单文件大小限制不含此文件。访问 GitHub 不便时可从飞书文档下载附件（无需登录），仍无法获取可加作者微信 MrEgg208。"
    )
    download_link.setProperty("role", "body")
    download_link.setWordWrap(True)
    download_link.setOpenExternalLinks(True)
    download_link.setTextInteractionFlags(Qt.TextBrowserInteraction)
    card_layout.addWidget(download_link)
    actions = QHBoxLayout()
    changelog = QPushButton("查看更新日志")
    changelog.setObjectName("Primary")
    changelog.clicked.connect(lambda: show_update_log_dialog(window))
    actions.addWidget(changelog)
    license_button = QPushButton("开源许可与第三方声明")
    license_button.setObjectName("Secondary")
    license_button.clicked.connect(lambda: _show_license_dialog(window))
    actions.addWidget(license_button)
    actions.addStretch(1)
    card_layout.addLayout(actions)
    copyright_label = QLabel("Copyright © 2026 MrEgg2021 and contributors")
    copyright_label.setProperty("role", "caption")
    copyright_label.setWordWrap(True)
    card_layout.addWidget(copyright_label)
    layout.addWidget(card)
    layout.addStretch(1)
    window.about_page = page
    return page
