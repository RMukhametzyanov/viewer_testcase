"""
Утилита для определения пути к файлу настроек приложения.
Поддерживает как режим разработки, так и собранное приложение.
"""

import sys
import os
import shutil
from pathlib import Path


def get_settings_path() -> Path:
    """
    Получить путь к файлу настроек приложения.
    
    В режиме разработки возвращает путь рядом с run_app.py.
    В собранном приложении возвращает путь в стандартной директории macOS:
    ~/Library/Application Support/Test Case Editor/settings.json
    
    Returns:
        Path: Путь к файлу настроек
    """
    # Проверяем, запущено ли приложение из PyInstaller
    if hasattr(sys, '_MEIPASS'):
        # Собранное приложение - используем стандартную директорию macOS
        app_support_dir = Path.home() / "Library" / "Application Support" / "Test Case Editor"
        # Создаем директорию, если её нет
        app_support_dir.mkdir(parents=True, exist_ok=True)
        settings_path = app_support_dir / "settings.json"
        
        # Миграция: если файл настроек не существует в новом месте,
        # но существует в старом месте (рядом с .app), копируем его
        if not settings_path.exists():
            # Пытаемся найти settings.json рядом с .app bundle
            # sys.executable в PyInstaller указывает на исполняемый файл внутри .app
            if sys.executable:
                app_bundle_path = Path(sys.executable).parent.parent.parent.parent
                old_settings = app_bundle_path / "settings.json"
                if old_settings.exists():
                    try:
                        shutil.copy2(old_settings, settings_path)
                        print(f"Настройки мигрированы из {old_settings} в {settings_path}")
                    except Exception as e:
                        print(f"Ошибка миграции настроек: {e}")
        
        return settings_path
    else:
        # Режим разработки - используем путь рядом с run_app.py
        # Определяем корень проекта (где находится run_app.py)
        # Если мы в test_case_editor/utils/settings_path.py, то корень на 3 уровня выше
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        return project_root / "settings.json"


def get_app_data_dir() -> Path:
    """
    Получить директорию для хранения данных приложения.
    
    Returns:
        Path: Путь к директории данных приложения
    """
    if hasattr(sys, '_MEIPASS'):
        # Собранное приложение
        app_support_dir = Path.home() / "Library" / "Application Support" / "Test Case Editor"
        app_support_dir.mkdir(parents=True, exist_ok=True)
        return app_support_dir
    else:
        # Режим разработки - корень проекта
        current_file = Path(__file__).resolve()
        return current_file.parent.parent.parent

