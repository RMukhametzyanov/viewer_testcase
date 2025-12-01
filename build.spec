# -*- mode: python ; coding: utf-8 -*-

import sys
import platform
from pathlib import Path

block_cipher = None

# Определяем платформу
is_windows = platform.system() == 'Windows'
is_macos = platform.system() == 'Darwin'
is_linux = platform.system() == 'Linux'

# Определяем пути
# SPECPATH автоматически определяется PyInstaller как путь к директории spec файла
try:
    app_root = Path(SPECPATH)
except NameError:
    # Если SPECPATH не определен, используем текущую директорию
    app_root = Path.cwd()
icons_dir = app_root / 'icons'

# Собираем список всех иконок
icon_files = []
if icons_dir.exists():
    for icon_file in icons_dir.glob('*.svg'):
        icon_files.append((str(icon_file), 'icons'))
    # Добавляем icon_mapping.json
    if (icons_dir / 'icon_mapping.json').exists():
        icon_files.append((str(icons_dir / 'icon_mapping.json'), 'icons'))

# Собираем список всех Python модулей
a = Analysis(
    ['run_app.py'],
    pathex=[],
    binaries=[],
    datas=icon_files,
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtSvg',
        'test_case_editor',
        'test_case_editor.ui',
        'test_case_editor.ui.widgets',
        'test_case_editor.ui.styles',
        'test_case_editor.models',
        'test_case_editor.services',
        'test_case_editor.repositories',
        'test_case_editor.utils',
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

# Настройки в зависимости от платформы
if is_windows:
    # Windows: создаем EXE файл
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='TestCaseEditor',
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
        icon=None,  # Можно добавить иконку приложения здесь
    )
elif is_macos:
    # macOS: создаем APP bundle
    # Сначала создаем исполняемый файл без бинарников (они будут в COLLECT)
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='TestCaseEditor',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,  # Не показывать консольное окно
    )
    
    # Собираем все файлы (бинарники, данные и т.д.)
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='TestCaseEditor',
    )
    
    # Создаем APP bundle для macOS
    app = BUNDLE(
        coll,
        name='TestCaseEditor.app',
        icon=None,
        bundle_identifier='com.testcaseeditor.app',
    )
else:
    # Linux: создаем исполняемый файл
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='TestCaseEditor',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
    )
