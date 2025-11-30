# -*- mode: python ; coding: utf-8 -*-
"""
Файл конфигурации PyInstaller для сборки Test Case Editor
"""

import sys
from pathlib import Path

block_cipher = None

# Определяем пути
project_root = Path(SPECPATH)
icons_dir = project_root / 'icons'

a = Analysis(
    ['run_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('icons', 'icons'),  # Включаем всю папку icons в сборку
        ('settings.json', '.'),  # Включаем settings.json если существует
    ],
    hiddenimports=[
        'PyQt5.QtSvg',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtPrintSupport',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Test Case Editor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Не показывать консольное окно
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='Test Case Editor.app',
    icon=None,  # Можно указать путь к .icns файлу если есть
    bundle_identifier='com.testcase.editor',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'CFBundleName': 'Test Case Editor',
        'CFBundleDisplayName': 'Test Case Editor',
        'CFBundleVersion': '2.0.0',
        'CFBundleShortVersionString': '2.0.0',
        'NSHumanReadableCopyright': 'Copyright © 2025',
    },
)

