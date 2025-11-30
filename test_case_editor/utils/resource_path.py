"""
Утилита для определения пути к ресурсам приложения.
Поддерживает как режим разработки, так и собранное приложение PyInstaller.
"""

import sys
from pathlib import Path


def get_resource_path(relative_path: str = "") -> Path:
    """
    Получить абсолютный путь к ресурсу приложения.
    
    В режиме разработки возвращает путь относительно корня проекта.
    В собранном приложении PyInstaller использует sys._MEIPASS.
    
    Args:
        relative_path: Относительный путь к ресурсу (например, "icons/icon_mapping.json")
    
    Returns:
        Path: Абсолютный путь к ресурсу
    """
    # Проверяем, запущено ли приложение из PyInstaller
    if hasattr(sys, '_MEIPASS'):
        # Собранное приложение - ресурсы находятся в _MEIPASS
        base_path = Path(sys._MEIPASS)
    else:
        # Режим разработки - определяем корень проекта
        # run_app.py находится в корне, поэтому идем на 4 уровня вверх от utils
        # или на 1 уровень вверх от корня проекта
        if Path(__file__).parent.parent.parent.name == "test_case_editor":
            # Мы в test_case_editor/utils/resource_path.py
            base_path = Path(__file__).parent.parent.parent.parent
        else:
            # Альтернативный способ - от run_app.py
            base_path = Path(__file__).parent.parent.parent.parent
    
    if relative_path:
        return base_path / relative_path
    return base_path


def get_icons_dir() -> Path:
    """
    Получить путь к папке с иконками.
    
    Returns:
        Path: Путь к папке icons
    """
    return get_resource_path("icons")


def get_icon_path(icon_name: str) -> Path:
    """
    Получить путь к конкретной иконке.
    
    Args:
        icon_name: Имя файла иконки (например, "info.svg")
    
    Returns:
        Path: Полный путь к файлу иконки
    """
    return get_icons_dir() / icon_name

