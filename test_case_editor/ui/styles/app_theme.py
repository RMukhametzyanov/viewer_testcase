"""Qt style sheet assembled from configurable UI metrics."""

from .ui_metrics import UI_METRICS, UIMetrics


def build_app_style_sheet(metrics: UIMetrics) -> str:
    return f"""
QWidget {{
    background-color: #18191c;
    color: #f6f6f6;
    font-family: {metrics.font_family};
    font-size: {metrics.base_font_size}px;
}}

QMainWindow,
QDialog {{
    background-color: #18191c;
}}

QFrame,
QGroupBox,
QTextEdit,
QPlainTextEdit {{
    background-color: #212226;
    border: 1px solid #2b2c30;
    border-radius: 0;
    padding: {metrics.container_padding}px;
    color: #f6f6f6;
}}

QLineEdit,
QTextEdit,
QPlainTextEdit,
QComboBox {{
    background-color: #242528;
    border: 1.5px solid #363841;
    border-radius: {metrics.input_radius}px;
    padding: {metrics.control_padding_vertical + metrics.text_vertical_padding}px {metrics.control_padding_horizontal}px;
    color: #f6f6f6;
    min-height: {metrics.control_min_height}px;
    selection-background-color: #406de4;
    selection-color: #ffffff;
}}

QLabel {{
    color: #ececec;
    font-weight: 500;
    padding: 2px 0;
    background-color: transparent;
    border: none;
}}

QGroupBox {{
    margin-top: {metrics.section_spacing}px;
    font-weight: 600;
    color: #3ec6e0;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: {metrics.container_padding + 2}px;
    padding: 0 {metrics.base_spacing}px;
}}

QPushButton {{
    background-color: #252529;
    color: #f6f6f6;
    border: 1px solid #31323a;
    border-radius: {metrics.control_radius}px;
    padding: {metrics.control_padding_vertical}px {metrics.control_padding_horizontal + 6}px;
    font-weight: 600;
    letter-spacing: 0.3px;
    min-height: {metrics.control_min_height}px;
    min-width: {metrics.control_min_width}px;
}}
QPushButton:hover {{
    background-color: #32353f;
}}
QPushButton:pressed {{
    background-color: #1f2128;
}}
QPushButton:disabled {{
    background: #1b1b1f;
    color: #666a74;
}}

QToolButton {{
    background-color: #252529;
    color: #f6f6f6;
    border: 1px solid #31323a;
    border-radius: {metrics.control_radius}px;
    padding: {metrics.control_padding_vertical}px {metrics.control_padding_horizontal + 6}px;
    min-height: {metrics.control_min_height}px;
    min-width: {metrics.control_min_width}px;
}}
QToolButton:hover {{
    background-color: #2f3138;
}}
QToolButton:pressed {{
    background-color: #1f2025;
}}
QToolButton:disabled {{
    background: #1b1b1f;
    color: #5f6066;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 14px;
    margin: 7px 0;
}}
QScrollBar::handle:vertical {{
    background-color: #3ec6e0;
    border-radius: 8px;
    min-height: 33px;
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QTabWidget::pane {{
    border-radius: {metrics.control_radius + 3}px;
    padding: {metrics.tab_padding}px;
    background-color: #212226;
}}
QTabBar::tab {{
    background-color: transparent;
    color: #3ec6e0;
    padding: {metrics.control_padding_vertical}px {metrics.control_padding_horizontal + 8}px;
    margin-right: {metrics.base_spacing}px;
    border-radius: {metrics.control_radius + 1}px;
    font-weight: 600;
    transition: color 0.16s, background-color 0.16s;
}}
QTabBar::tab:selected {{
    background-color: #282c34;
    color: #ffffff;
}}
QTabBar::tab:hover {{
    color: #3894ef;
}}

QMenu {{
    background-color: #232226;
    border-radius: {metrics.control_radius}px;
    padding: {metrics.container_padding}px;
}}
QMenu::item {{
    padding: {metrics.control_padding_vertical}px {metrics.control_padding_horizontal + 4}px;
    border-radius: {metrics.control_radius - 2}px;
    color: #f6f6f6;
}}
QMenu::item:selected {{
    background-color: #3ec6e0;
    color: #18191c;
}}

QTreeWidget,
QListWidget {{
    background-color: #1c1d21;
    border: 1px solid #2b2c30;
    border-radius: {metrics.input_radius}px;
}}
QTreeWidget::item,
QListWidget::item {{
    padding: {metrics.list_item_padding}px;
    min-height: {metrics.control_min_height - 6}px;
}}
QTreeWidget::item:selected,
QListWidget::item:selected {{
    background-color: #2b2f38;
    color: #ffffff;
}}

QStatusBar {{
    background-color: #191a21;
    border-top: none;
    color: #98b4e6;
}}
QStatusBar::item {{
    border: none;
}}
"""


APP_STYLE_SHEET = build_app_style_sheet(UI_METRICS)

