"""
Утилита для определения пути к файлу настроек приложения.
Поддерживает как режим разработки, так и собранное приложение.
Кроссплатформенная поддержка: Windows, macOS, Linux.
"""

import sys
import os
import shutil
from pathlib import Path


def get_settings_path() -> Path:
    """
    Получить путь к файлу настроек приложения.
    
    В режиме разработки возвращает путь рядом с run_app.py.
    В собранном приложении возвращает путь в стандартной директории ОС:
    - Windows: %APPDATA%\\Test Case Editor\\settings.json
    - macOS: ~/Library/Application Support/Test Case Editor/settings.json
    - Linux: ~/.local/share/Test Case Editor/settings.json
    
    Returns:
        Path: Путь к файлу настроек
    """
    # Проверяем, запущено ли приложение из PyInstaller
    if hasattr(sys, '_MEIPASS'):
        # Собранное приложение - используем стандартную директорию ОС
        app_support_dir = _get_app_support_dir()
        # Создаем директорию, если её нет
        app_support_dir.mkdir(parents=True, exist_ok=True)
        settings_path = app_support_dir / "settings.json"
        
        # Миграция: если файл настроек не существует в новом месте,
        # но существует в старом месте (рядом с exe/app), копируем его
        if not settings_path.exists():
            # Пытаемся найти settings.json рядом с исполняемым файлом
            if sys.executable:
                try:
                    exe_path = Path(sys.executable)
                    if sys.platform == "darwin":
                        # На macOS exe находится внутри .app bundle
                        # sys.executable -> Contents/MacOS/executable
                        # Нужно подняться на 3 уровня вверх
                        app_bundle_path = exe_path.parent.parent.parent
                        old_settings = app_bundle_path / "settings.json"
                    else:
                        # На Windows/Linux exe находится рядом с settings.json
                        old_settings = exe_path.parent / "settings.json"
                    
                    if old_settings.exists():
                        try:
                            shutil.copy2(old_settings, settings_path)
                            print(f"Настройки мигрированы из {old_settings} в {settings_path}")
                        except Exception as e:
                            print(f"Ошибка миграции настроек: {e}")
                except Exception as e:
                    print(f"Ошибка при попытке миграции настроек: {e}")
        
        return settings_path
    else:
        # Режим разработки - используем путь рядом с run_app.py
        # Определяем корень проекта (где находится run_app.py)
        # Если мы в test_case_editor/utils/settings_path.py, то корень на 3 уровня выше
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        return project_root / "settings.json"


def _get_app_support_dir() -> Path:
    """
    Получить директорию для хранения данных приложения в зависимости от ОС.
    
    Returns:
        Path: Путь к директории данных приложения
    """
    home = Path.home()
    
    if sys.platform == "win32":
        # Windows: %APPDATA%\\Test Case Editor
        app_support_dir = home / "AppData" / "Roaming" / "Test Case Editor"
    elif sys.platform == "darwin":
        # macOS: ~/Library/Application Support/Test Case Editor
        app_support_dir = home / "Library" / "Application Support" / "Test Case Editor"
    else:
        # Linux: ~/.local/share/Test Case Editor
        app_support_dir = home / ".local" / "share" / "Test Case Editor"
    
    return app_support_dir


def get_app_data_dir() -> Path:
    """
    Получить директорию для хранения данных приложения.
    
    Returns:
        Path: Путь к директории данных приложения
    """
    if hasattr(sys, '_MEIPASS'):
        # Собранное приложение
        app_support_dir = _get_app_support_dir()
        app_support_dir.mkdir(parents=True, exist_ok=True)
        return app_support_dir
    else:
        # Режим разработки - корень проекта
        current_file = Path(__file__).resolve()
        return current_file.parent.parent.parent

