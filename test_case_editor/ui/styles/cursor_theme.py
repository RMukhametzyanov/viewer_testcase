"""Стили в стиле Cursor с поддержкой тем, плавными переходами и мягкими тенями"""

from .ui_metrics import UIMetrics
from .theme_provider import ThemeProvider, THEME_PROVIDER


def build_cursor_style_sheet(metrics: UIMetrics, theme_provider: ThemeProvider = None) -> str:
    """Создать стиль в стиле Cursor"""
    if theme_provider is None:
        theme_provider = THEME_PROVIDER
    
    colors = theme_provider.colors
    
    # Примечание: QSS не поддерживает CSS transitions напрямую
    # Плавность достигается через настройки QApplication.setStyle('Fusion')
    # и использование анимаций в PyQt при необходимости
    
    return f"""
/* ==================== Базовые стили ==================== */
QWidget {{
    background-color: {colors.background};
    color: {colors.text_primary};
    font-family: {metrics.font_family};
    font-size: {metrics.base_font_size}px;
}}

QMainWindow,
QDialog {{
    background-color: {colors.background};
}}

/* ==================== Панели и контейнеры ==================== */
QFrame,
QGroupBox {{
    background-color: {colors.background_elevated};
    border: 1px solid {colors.border_primary};
    border-radius: {metrics.control_radius}px;
    padding: {metrics.container_padding}px;
    color: {colors.text_primary};
}}

QGroupBox {{
    margin-top: {metrics.section_spacing}px;
    font-weight: 600;
    color: {colors.text_primary};
    border: 1px solid {colors.border_secondary};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: {metrics.container_padding + 2}px;
    padding: 0 {metrics.base_spacing}px;
    background-color: {colors.background_elevated};
    border-radius: {metrics.control_radius - 2}px;
}}

/* ==================== Поля ввода ==================== */
QLineEdit,
QTextEdit,
QPlainTextEdit,
QComboBox {{
    background-color: {colors.input_background};
    border: 1px solid {colors.input_border};
    border-radius: {metrics.input_radius}px;
    padding: {metrics.control_padding_vertical + metrics.text_input_vertical_padding}px {metrics.control_padding_horizontal}px;
    color: {colors.text_primary};
    min-height: {metrics.control_min_height}px;
    selection-background-color: {colors.selection_background};
    selection-color: {colors.selection_text};
}}

QLineEdit:hover,
QTextEdit:hover,
QPlainTextEdit:hover,
QComboBox:hover {{
    border-color: {colors.border_hover};
}}

QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QComboBox:focus {{
    border-color: {colors.input_focus};
    border-width: 2px;
}}

/* ==================== QFontComboBox ==================== */
QFontComboBox {{
    background-color: {colors.input_background};
    border: 1px solid {colors.input_border};
    border-radius: {metrics.input_radius}px;
    padding: {metrics.control_padding_vertical + metrics.text_input_vertical_padding}px {metrics.control_padding_horizontal}px;
    color: {colors.text_primary};
    min-height: {metrics.control_min_height}px;
    selection-background-color: {colors.selection_background};
    selection-color: {colors.selection_text};
}}

QFontComboBox:hover {{
    border-color: {colors.border_hover};
}}

QFontComboBox:focus {{
    border-color: {colors.input_focus};
    border-width: 2px;
}}

QFontComboBox QAbstractItemView {{
    background-color: {colors.input_background};
    border: 1px solid {colors.input_border};
    border-radius: {metrics.input_radius}px;
    selection-background-color: {colors.selection_background};
    selection-color: {colors.selection_text};
    padding: 4px;
}}

QFontComboBox QAbstractItemView::item {{
    padding: {metrics.control_padding_vertical}px {metrics.control_padding_horizontal}px;
    background-color: transparent;
    border-radius: {metrics.control_radius - 2}px;
}}

QFontComboBox QAbstractItemView::item:selected {{
    background-color: {colors.selection_background};
    color: {colors.selection_text};
}}

QFontComboBox QAbstractItemView::item:hover {{
    background-color: {colors.background_hover};
}}

/* ==================== Метки ==================== */
QLabel {{
    color: {colors.text_primary};
    font-weight: 400;
    padding: 2px 0;
    background-color: transparent;
    border: none;
}}

/* ==================== Кнопки ==================== */
QPushButton {{
    background-color: {colors.button_background};
    color: {colors.text_primary};
    border: 1px solid {colors.border_primary};
    border-radius: {metrics.control_radius}px;
    padding: {metrics.control_padding_vertical}px {metrics.control_padding_horizontal + 6}px;
    font-weight: 500;
    letter-spacing: 0.2px;
    min-height: {metrics.control_min_height}px;
    min-width: {metrics.control_min_width}px;
}}

QPushButton:hover {{
    background-color: {colors.button_hover};
    border-color: {colors.border_hover};
}}

QPushButton:pressed {{
    background-color: {colors.button_pressed};
}}

QPushButton:disabled {{
    background: {colors.background_elevated};
    color: {colors.text_disabled};
    border-color: {colors.border_secondary};
}}

/* Акцентные кнопки (основные действия) */
QPushButton[class="primary"] {{
    background-color: {colors.accent_primary};
    color: {colors.text_primary};
    border-color: {colors.accent_primary};
}}

QPushButton[class="primary"]:hover {{
    background-color: {colors.accent_hover};
    border-color: {colors.accent_hover};
}}

QPushButton[class="primary"]:pressed {{
    background-color: {colors.accent_pressed};
    border-color: {colors.accent_pressed};
}}

/* ==================== Инструментальные кнопки ==================== */
QToolButton {{
    background-color: {colors.button_background};
    color: {colors.text_primary};
    border: 1px solid {colors.border_primary};
    border-radius: {metrics.control_radius}px;
    padding: {metrics.control_padding_vertical}px {metrics.control_padding_horizontal + 6}px;
    min-height: {metrics.control_min_height}px;
    min-width: {metrics.control_min_width}px;
}}

QToolButton:hover {{
    background-color: {colors.button_hover};
    border-color: {colors.border_hover};
}}

QToolButton:pressed {{
    background-color: {colors.button_pressed};
}}

QToolButton:disabled {{
    background: {colors.background_elevated};
    color: {colors.text_disabled};
    border-color: {colors.border_secondary};
}}

/* ==================== Скроллбары ==================== */
QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 4px 0;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background-color: {colors.border_primary};
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {colors.border_hover};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 12px;
    margin: 0 4px;
    border-radius: 6px;
}}

QScrollBar::handle:horizontal {{
    background-color: {colors.border_primary};
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {colors.border_hover};
}}

/* ==================== Вкладки ==================== */
QTabWidget::pane {{
    border-radius: {metrics.control_radius}px;
    padding: {metrics.tab_padding}px;
    background-color: {colors.background_elevated};
    border: 1px solid {colors.border_secondary};
}}

QTabBar::tab {{
    background-color: transparent;
    color: {colors.text_secondary};
    padding: {metrics.control_padding_vertical}px {metrics.control_padding_horizontal + 8}px;
    margin-right: {metrics.base_spacing / 2}px;
    border-radius: {metrics.control_radius}px;
    font-weight: 500;
}}

QTabBar::tab:selected {{
    background-color: {colors.background_elevated};
    color: {colors.text_primary};
    border-bottom: 2px solid {colors.accent_primary};
}}

QTabBar::tab:hover {{
    color: {colors.accent_primary};
    background-color: {colors.background_hover};
}}

/* ==================== Меню ==================== */
QMenu {{
    background-color: {colors.background_elevated};
    border: 1px solid {colors.border_primary};
    border-radius: {metrics.control_radius}px;
    padding: {metrics.base_spacing / 2}px;
}}

QMenu::item {{
    padding: {metrics.control_padding_vertical}px {metrics.control_padding_horizontal + 4}px;
    border-radius: {metrics.control_radius - 2}px;
    color: {colors.text_primary};
}}

QMenu::item:selected {{
    background-color: {colors.accent_primary};
    color: {colors.text_primary};
}}

QMenu::item:hover {{
    background-color: {colors.background_hover};
}}

/* ==================== Дерево и списки ==================== */
QTreeWidget,
QListWidget {{
    background-color: {colors.background_elevated};
    border: 1px solid {colors.border_primary};
    border-radius: {metrics.input_radius}px;
}}

QTreeWidget::item,
QListWidget::item {{
    padding: {metrics.list_item_padding}px;
    min-height: {metrics.control_min_height - 6}px;
    border-radius: {metrics.control_radius - 2}px;
}}

QTreeWidget::item:hover,
QListWidget::item:hover {{
    background-color: {colors.background_hover};
}}

QTreeWidget::item:selected,
QListWidget::item:selected {{
    background-color: {colors.selection_background};
    color: {colors.selection_text};
}}

QTreeWidget::item:selected:hover,
QListWidget::item:selected:hover {{
    background-color: {colors.accent_hover};
}}

/* ==================== Статусная панель ==================== */
QStatusBar {{
    background-color: {colors.background};
    border-top: 1px solid {colors.border_secondary};
    color: {colors.text_secondary};
    padding: {metrics.header_padding / 2}px;
}}

QStatusBar::item {{
    border: none;
}}

/* ==================== Меню бар ==================== */
QMenuBar {{
    background-color: {colors.background};
    color: {colors.text_primary};
    border: none;
    border-bottom: 1px solid {colors.border_secondary};
    padding: {metrics.base_spacing / 2}px;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: {metrics.control_padding_vertical}px {metrics.control_padding_horizontal + 4}px;
    border-radius: {metrics.control_radius - 2}px;
    color: {colors.text_primary};
}}

QMenuBar::item:selected {{
    background-color: {colors.background_hover};
    color: {colors.text_primary};
}}

QMenuBar::item:pressed {{
    background-color: {colors.button_pressed};
}}

/* ==================== Разделители ==================== */
QSplitter::handle {{
    background-color: {colors.border_secondary};
}}

QSplitter::handle:hover {{
    background-color: {colors.border_primary};
}}

QSplitter::handle:horizontal {{
    width: 1px;
}}

QSplitter::handle:vertical {{
    height: 1px;
}}

/* ==================== Полосы прокрутки в QTextEdit ==================== */
QTextEdit QScrollBar:vertical,
QPlainTextEdit QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 4px 0;
}}

QTextEdit QScrollBar::handle:vertical,
QPlainTextEdit QScrollBar::handle:vertical {{
    background-color: {colors.border_primary};
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}}

/* ==================== QScrollArea ==================== */
QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollArea QWidget {{
    background-color: {colors.background_elevated};
}}

/* ==================== Дополнительные элементы ==================== */
QSpinBox,
QDoubleSpinBox {{
    background-color: {colors.input_background};
    border: 1px solid {colors.input_border};
    border-radius: {metrics.input_radius}px;
    padding: {metrics.control_padding_vertical + metrics.text_input_vertical_padding}px {metrics.control_padding_horizontal}px;
    color: {colors.text_primary};
    min-height: {metrics.control_min_height}px;
}}

QSpinBox:hover,
QDoubleSpinBox:hover {{
    border-color: {colors.border_hover};
}}

QSpinBox:focus,
QDoubleSpinBox:focus {{
    border-color: {colors.input_focus};
    border-width: 2px;
}}

"""

