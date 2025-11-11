"""Виджет заглушки"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class PlaceholderWidget(QWidget):
    """
    Виджет заглушки для отображения когда не выбран тест-кейс
    
    Соответствует принципу Single Responsibility:
    отвечает только за отображение заглушки
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Настройка интерфейса"""
        self.setStyleSheet("background-color: #17212B;")
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        # Иконка
        icon_label = QLabel("📋")
        icon_label.setFont(QFont("Segoe UI", 72))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("color: #5288C1; background: transparent;")
        layout.addWidget(icon_label)
        
        layout.addSpacing(20)
        
        # Основной текст
        main_text = QLabel("Выберите тест-кейс для начала работы")
        main_text.setFont(QFont("Segoe UI", 16, QFont.Bold))
        main_text.setAlignment(Qt.AlignCenter)
        main_text.setStyleSheet("color: #E1E3E6; background: transparent;")
        main_text.setWordWrap(True)
        layout.addWidget(main_text)
        
        layout.addSpacing(10)
        
        # Счетчик тест-кейсов
        self.count_label = QLabel("Загрузка...")
        self.count_label.setFont(QFont("Segoe UI", 12))
        self.count_label.setAlignment(Qt.AlignCenter)
        self.count_label.setStyleSheet("color: #8B9099; background: transparent;")
        layout.addWidget(self.count_label)
        
        layout.addStretch()
    
    def update_count(self, count: int):
        """Обновить счетчик тест-кейсов"""
        if count == 0:
            text = "Нет тест-кейсов"
        elif count == 1:
            text = "1 тест-кейс"
        elif 2 <= count <= 4:
            text = f"{count} тест-кейса"
        else:
            text = f"{count} тест-кейсов"
        
        self.count_label.setText(text)


