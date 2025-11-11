"""
Запуск приложения Test Case Editor v2.0
Рефакторинговая версия с применением SOLID принципов
"""

import sys
from pathlib import Path

# Добавляем путь к модулю
sys.path.insert(0, str(Path(__file__).parent))

from PyQt5.QtWidgets import QApplication
from test_case_editor.ui import MainWindow


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
    
    # Создаем главное окно
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()


