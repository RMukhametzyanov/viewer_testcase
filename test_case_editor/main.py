"""Точка входа приложения"""

import sys
from PyQt5.QtWidgets import QApplication
from ui import create_main_window


def main():
    """
    Главная функция приложения
    
    Демонстрирует принцип Dependency Inversion:
    создание зависимостей происходит на верхнем уровне,
    компоненты получают их через injection
    """
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Создаем и показываем главное окно через фабрику
    window = create_main_window()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

