# -*- mode: python ; coding: utf-8 -*-


import os
import re
from pathlib import Path


def _load_app_version():
    config_text = Path("resources/config.yaml").read_text(encoding="utf-8")
    match = re.search(r"(?m)^\s*version:\s*[\"']?([0-9]+(?:\.[0-9]+){1,3})[\"']?\s*$", config_text)
    if not match:
        raise RuntimeError("resources/config.yaml is missing app.version for EXE naming")
    return match.group(1)


def _versioned_exe_name(base_name):
    return f"{base_name}_v{_load_app_version()}"


_nuitka_pyd_root = Path("build") / "nuitka_pyd"
_nuitka_pyd_binaries = []
_nuitka_pyd_module_names = set()
if _nuitka_pyd_root.exists():
    for _pyd in _nuitka_pyd_root.rglob("*.pyd"):
        _rel = _pyd.relative_to(_nuitka_pyd_root)
        _dest = str(_rel.parent)
        if _dest == ".":
            _dest = ""
        _nuitka_pyd_binaries.append((str(_pyd), _dest))

        _base = _pyd.name.split(".", 1)[0]
        _mod = ".".join(list(_rel.parent.parts) + [_base]) if _rel.parent.parts else _base
        _nuitka_pyd_module_names.add(_mod)


a = Analysis(
    ['gui_app.py'],
    pathex=[],
    binaries=_nuitka_pyd_binaries,
    datas=[
        ('LICENSE', 'resources'),
        ('THIRD_PARTY_NOTICES.md', 'resources'),
        ('resources\\OPEN_SOURCE_LICENSE.zh-CN.md', 'resources'),
        ('resources\\third_party_licenses', 'resources\\third_party_licenses'),
        ('resources\\config.yaml', 'resources'),
        ('resources\\dtd\\cn-application-body-20080416.dtd', 'resources\\dtd'),
        ('resources\\templates\\invention_cn_template.docx', 'resources\\templates'),
        ('resources\\assets\\app_icon.ico', 'resources\\assets'),
        ('resources\\assets\\Word.png', 'resources\\assets'),
        ('resources\\assets\\logo.png', 'resources\\assets'),
        ('resources\\assets\\logo_round.png', 'resources\\assets'),
        ('resources\\assets\\github.svg', 'resources\\assets'),
        ('resources\\official_doc_field_policy.json', 'resources'),
        ('resources\\official_doc_supported_types.json', 'resources'),
        ('resources\\official_doc_pdf_field_matrix.json', 'resources'),
        ('resources\\codeset_local_guobie.json', 'resources'),
        ('用户使用手册+更新日志\\更新日志', 'resources\\更新日志'),
        ('gui\\ui_layout_impl\\theme.qss', 'gui\\ui_layout_impl'),
        ('gui\\ui_layout_impl\\assets\\check_dark.svg', 'gui\\ui_layout_impl\\assets'),
        ('gui\\ui_layout_impl\\assets\\chevron_down.svg', 'gui\\ui_layout_impl\\assets'),
        ('gui\\ui_layout_impl\\assets\\chevron_right.svg', 'gui\\ui_layout_impl\\assets'),
    ],
    hiddenimports=[
        'cryptography',
        'yaml',
        'lxml',
        'lxml.etree',
        'fitz',
        'cv2',
        'numpy',
        'PIL',
        'psutil',
        'win32com',
        'win32com.client',
        'pythoncom',
        'pywintypes',
        'win32clipboard',
        'win32ui',
        'win32gui',
        'win32con',
        'win32api',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'scipy',
        'numpy.f2py',
        'pandas',
        'PySide6.QtQuick',
        'PySide6.QtQml',
        'PySide6.QtQuickWidgets',
        'PySide6.QtPositioning',
        'PySide6.QtOpenGL',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngine',
        'PySide6.QtWebEngineQuick',
        'PySide6.QtWebView',
        'PySide6.QtWebChannel',
    ],
    noarchive=False,
    optimize=0,
)
if _nuitka_pyd_module_names:
    a.pure = [m for m in a.pure if m[0] not in _nuitka_pyd_module_names]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=_versioned_exe_name('通官文旦-专利工具'),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='resources/version_info_gui.txt',
    icon=['resources/assets/app_icon.ico'],
)
