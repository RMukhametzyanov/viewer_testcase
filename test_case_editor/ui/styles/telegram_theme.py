"""Telegram Dark тема для приложения"""

# Основная stylesheet для всего приложения
TELEGRAM_DARK_THEME = """
QMainWindow {
    background-color: #0E1621;
}

QWidget {
    background-color: #17212B;
    color: #E1E3E6;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 10pt;
}

QLineEdit, QTextEdit, QComboBox {
    background-color: #1E2732;
    border: 1px solid #2B3945;
    border-radius: 6px;
    padding: 8px;
    color: #E1E3E6;
    selection-background-color: #2B5278;
}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 2px solid #5288C1;
    background-color: #1E2732;
}

QLineEdit:read-only {
    background-color: #17212B;
    color: #8B9099;
    border: 1px solid #2B3945;
}

QPushButton {
    background-color: #2B5278;
    border: 1px solid #3D6A98;
    border-radius: 8px;
    padding: 10px 18px;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #3D6A98;
    border: 1px solid #5288C1;
}

QPushButton:pressed {
    background-color: #1D3F5F;
}

QGroupBox {
    border: 1px solid #2B3945;
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
    color: #5288C1;
    background-color: #17212B;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 5px 12px;
    color: #5288C1;
    background-color: transparent;
}

QLabel {
    background-color: transparent;
    color: #E1E3E6;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: #17212B;
    width: 12px;
    border-radius: 6px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #2B3945;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #3D6A98;
}

QScrollBar:horizontal {
    background-color: #17212B;
    height: 12px;
    border-radius: 6px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #2B3945;
    border-radius: 6px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #3D6A98;
}

QScrollBar::add-line, QScrollBar::sub-line {
    border: none;
    background: none;
}

QFrame[frameShape="4"], QFrame[frameShape="5"] {
    border: 1px solid #2B3945;
}

QStatusBar {
    background-color: #17212B;
    color: #E1E3E6;
    border-top: 1px solid #2B3945;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #5288C1;
    margin-right: 5px;
}

QComboBox QAbstractItemView {
    background-color: #1E2732;
    border: 1px solid #2B3945;
    border-radius: 6px;
    selection-background-color: #2B5278;
    color: #E1E3E6;
}

QTableWidget {
    background-color: #17212B;
    gridline-color: #2B3945;
    border: 1px solid #2B3945;
    border-radius: 8px;
    outline: 0;
}

QTableWidget::item {
    padding: 10px;
    color: #E1E3E6;
    background-color: #17212B;
    border: none;
    outline: 0;
}

QTableWidget::item:selected {
    background-color: #2B5278;
    color: #FFFFFF;
    border: none;
    outline: 0;
}

QTableWidget::item:focus {
    background-color: #2B5278;
    color: #FFFFFF;
    border: none;
    outline: 0;
}

QTableWidget::item:hover {
    background-color: #1E2732;
}

QHeaderView::section {
    background-color: #17212B;
    color: #E1E3E6;
    padding: 10px;
    border: none;
    border-bottom: 2px solid #2B3945;
    font-weight: bold;
}
"""


def get_button_style(button_type: str = "primary") -> str:
    """Получить стиль для кнопки"""
    styles = {
        "primary": """
            QPushButton {
                background-color: #2B5278;
                border: 1px solid #3D6A98;
                border-radius: 6px;
                padding: 8px 15px;
                color: #FFFFFF;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3D6A98;
                border: 1px solid #5288C1;
            }
            QPushButton:pressed {
                background-color: #1D3F5F;
            }
            QPushButton:disabled {
                background-color: #17212B;
                color: #6B7380;
                border: 1px solid #2B3945;
            }
        """,
        "danger": """
            QPushButton {
                background-color: #F5555D;
                border: 1px solid #F77078;
                border-radius: 6px;
                padding: 8px 15px;
                color: #FFFFFF;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #F77078;
                border: 1px solid #F98B91;
            }
            QPushButton:pressed {
                background-color: #D43F47;
            }
            QPushButton:disabled {
                background-color: #17212B;
                color: #6B7380;
                border: 1px solid #2B3945;
            }
        """,
        "secondary": """
            QPushButton {
                background-color: #2B3945;
                border: 1px solid #3D4B5C;
                border-radius: 6px;
                padding: 8px 15px;
                color: #E1E3E6;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3D4B5C;
                border: 1px solid #4E5D6E;
            }
            QPushButton:pressed {
                background-color: #1E2732;
            }
        """
    }
    return styles.get(button_type, styles["primary"])


def get_panel_style() -> str:
    """Получить стиль для панели"""
    return """
        QFrame {
            background-color: #1E2732;
            border: 1px solid #FFA931;
            border-radius: 6px;
            padding: 5px;
        }
    """


