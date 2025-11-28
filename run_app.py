"""
Запуск приложения Test Case Editor v2.0
Рефакторинговая версия с применением SOLID принципов
"""

import sys
import json
from pathlib import Path

# Добавляем путь к модулю
sys.path.insert(0, str(Path(__file__).parent))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from pathlib import Path
from test_case_editor.ui import MainWindow
from test_case_editor.ui.styles.app_theme import build_app_style_sheet
from test_case_editor.ui.styles.ui_metrics import UI_METRICS
from test_case_editor.ui.styles.theme_provider import THEME_PROVIDER


def main():
    """
    Главная функция приложения
    
    Архитектура согласно SOLID:
    
    1. Single Responsibility Principle (SRP):
       - TestCase: хранение данных
       - TestCaseRepository: работа с файлами
       - TestCaseService: бизнес-логика
       - MainWindow: координация UI
       - Виджеты: отображение отдельных компонентов
    
    2. Open/Closed Principle (OCP):
       - Можно добавить новые виджеты без изменения существующих
       - Можно создать новый репозиторий (например, для БД) без изменения сервиса
    
    3. Liskov Substitution Principle (LSP):
       - Любая реализация ITestCaseRepository может заменить TestCaseRepository
    
    4. Interface Segregation Principle (ISP):
       - ITestCaseRepository определяет только необходимые методы
       - Клиенты зависят только от нужных им интерфейсов
    
    5. Dependency Inversion Principle (DIP):
       - MainWindow зависит от TestCaseService (абстракция)
       - TestCaseService зависит от ITestCaseRepository (абстракция)
       - Конкретные реализации создаются на верхнем уровне
    
    ПРИМЕЧАНИЕ:
    Это упрощенная версия для демонстрации SOLID принципов.
    Полный функционал из test_case_editor_v1.py может быть портирован
    по тому же принципу - разделение на модули и компоненты.
    
    Преимущества новой архитектуры:
    - Легко тестируется (можно мокировать сервисы и репозитории)
    - Легко расширяется (добавление новых фич не ломает существующий код)
    - Легко поддерживается (каждый модуль отвечает за одну вещь)
    - Переиспользуемость (компоненты можно использовать в других проектах)
    """
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Загружаем настройки и применяем к UI_METRICS и THEME_PROVIDER перед созданием окна
    settings_file = Path("settings.json")
    if settings_file.exists():
        try:
            with settings_file.open("r", encoding="utf-8") as f:
                settings = json.load(f)
                # Настройки шрифтов
                if 'font_family' in settings:
                    UI_METRICS.font_family = settings['font_family']
                if 'font_size' in settings:
                    UI_METRICS.base_font_size = settings['font_size']
                # Настройки отступов
                if 'base_spacing' in settings:
                    UI_METRICS.base_spacing = settings['base_spacing']
                if 'section_spacing' in settings:
                    UI_METRICS.section_spacing = settings['section_spacing']
                if 'container_padding' in settings:
                    UI_METRICS.container_padding = settings['container_padding']
                if 'text_input_vertical_padding' in settings:
                    UI_METRICS.text_input_vertical_padding = settings['text_input_vertical_padding']
                if 'group_title_spacing' in settings:
                    UI_METRICS.group_title_spacing = settings['group_title_spacing']
                # Настройка темы
                theme_name = settings.get('theme', 'dark').strip().lower()
                if theme_name in ['dark', 'light']:
                    THEME_PROVIDER.set_theme(theme_name)
                else:
                    THEME_PROVIDER.set_theme('dark')  # По умолчанию темная тема
        except Exception:
            # Если не удалось загрузить настройки, используем значения по умолчанию
            pass
    
    # Применяем стили с учетом настроек
    style_sheet = build_app_style_sheet(UI_METRICS)
    app.setStyleSheet(style_sheet)
    
    # Устанавливаем иконку приложения
    app_root = Path(__file__).parent
    logo_path = app_root / "icons" / "logo.png"
    if logo_path.exists():
        app_icon = QIcon(str(logo_path))
        app.setWindowIcon(app_icon)
    
    # Создаем главное окно
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
