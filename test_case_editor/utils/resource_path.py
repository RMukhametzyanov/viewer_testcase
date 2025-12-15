"""
Утилита для определения пути к ресурсам приложения.
Работает как в исходном коде, так и в собранном EXE через PyInstaller.
"""

import sys
from pathlib import Path


def get_resource_path(relative_path: str) -> Path:
    """
    Получить абсолютный путь к ресурсу.
    
    В собранном приложении (PyInstaller) ресурсы находятся в sys._MEIPASS.
    В исходном коде - относительно корня проекта.
    
    Args:
        relative_path: Относительный путь к ресурсу (например, "icons/info.svg")
    
    Returns:
        Path: Абсолютный путь к ресурсу
    """
    # Проверяем, запущено ли приложение из собранного EXE
    if hasattr(sys, '_MEIPASS'):
        # В собранном приложении ресурсы находятся в sys._MEIPASS
        base_path = Path(sys._MEIPASS)
    else:
        # В исходном коде определяем корень проекта
        # Ищем корень проекта (где находится run_app.py)
        current_file = Path(__file__).resolve()
        # test_case_editor/utils/resource_path.py -> test_case_editor/utils -> test_case_editor -> корень проекта
        base_path = current_file.parent.parent.parent
    
    return base_path / relative_path


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
        Path: Полный путь к иконке
    """
    return get_icons_dir() / icon_name





