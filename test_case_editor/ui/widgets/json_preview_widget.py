"""Панель отображения JSON тест-кейса."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, QRegularExpression, QSize
from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QIcon, QPixmap, QPainter
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPlainTextEdit,
    QHBoxLayout,
    QPushButton,
    QToolButton,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
)
from PyQt5.QtSvg import QSvgRenderer

from ...models import TestCase
from ...utils.resource_path import get_icon_path
from ..styles.ui_metrics import UI_METRICS


class _JsonHighlighter(QSyntaxHighlighter):
    """Подсветка JSON в стиле midnight."""

    def __init__(self, document):
        super().__init__(document)
        self.key_format = QTextCharFormat()
        self.key_format.setForeground(QColor("#9cdcfe"))

        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#c3e88d"))

        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor("#89ddff"))

        self.bool_format = QTextCharFormat()
        self.bool_format.setForeground(QColor("#ffcb6b"))

        self.punct_format = QTextCharFormat()
        self.punct_format.setForeground(QColor("#7f7f7f"))

        self.key_regex = QRegularExpression(r'"([^"\\]|\\.)*"(?=\s*:)')
        self.string_regex = QRegularExpression(r'"([^"\\]|\\.)*"')
        self.number_regex = QRegularExpression(r'\b-?(0[xX][0-9A-Fa-f]+|\d+(\.\d+)?([eE][+-]?\d+)?)\b')
        self.bool_regex = QRegularExpression(r'\b(true|false|null)\b')
        self.punct_regex = QRegularExpression(r'[{}\[\],:]')

    def highlightBlock(self, text: str):
        iterator = self.punct_regex.globalMatch(text)
        while iterator.hasNext():
            match = iterator.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), self.punct_format)

        iterator = self.string_regex.globalMatch(text)
        while iterator.hasNext():
            match = iterator.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), self.string_format)

        iterator = self.key_regex.globalMatch(text)
        while iterator.hasNext():
            match = iterator.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), self.key_format)

        iterator = self.number_regex.globalMatch(text)
        while iterator.hasNext():
            match = iterator.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), self.number_format)

        iterator = self.bool_regex.globalMatch(text)
        while iterator.hasNext():
            match = iterator.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), self.bool_format)


class JsonPreviewWidget(QWidget):
    """Простая панель для просмотра JSON представления тест-кейса."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_path: Optional[Path] = None
        self._setup_ui()
    
    def _load_svg_icon(self, icon_name: str, size: int = 16, color: Optional[str] = None) -> Optional[QIcon]:
        """Загрузить SVG иконку из файла и вернуть QIcon."""
        icon_path = get_icon_path(icon_name)
        
        if not icon_path.exists():
            return None
        
        try:
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            if color:
                svg_content = svg_content.replace('currentColor', color)
                svg_content = svg_content.replace('stroke="currentColor"', f'stroke="{color}"')
                svg_content = svg_content.replace('fill="currentColor"', f'fill="{color}"')
            
            renderer = QSvgRenderer(svg_content.encode('utf-8'))
            if not renderer.isValid():
                return None
            
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            renderer.render(painter)
            painter.end()
            
            return QIcon(pixmap)
        except Exception:
            return None

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        # Используем те же отступы, что и в панели "Отчетность" (эталон)
        content_layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
        )
        content_layout.setSpacing(UI_METRICS.section_spacing)
        
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # Заголовок с кнопкой (как в панели "Отчетность")
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(10)
        
        title_label = QLabel("JSON превью")
        # Используем тот же стиль заголовка, что и в панели "Отчетность"
        title_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # Кнопка копирования с иконкой
        self.copy_button = QToolButton()
        copy_icon = self._load_svg_icon("copy.svg", size=16, color="#ffffff")
        if copy_icon:
            self.copy_button.setIcon(copy_icon)
            self.copy_button.setIconSize(QSize(16, 16))
        else:
            self.copy_button.setText("Копировать")
        self.copy_button.setToolTip("Копировать")
        self.copy_button.setCursor(Qt.PointingHandCursor)
        self.copy_button.setAutoRaise(True)
        self.copy_button.setFixedSize(24, 24)
        self.copy_button.setStyleSheet("""
            QToolButton {
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 0px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.2);
            }
        """)
        self.copy_button.clicked.connect(self._copy_json)  # type: ignore[attr-defined]
        title_layout.addWidget(self.copy_button)
        
        content_layout.addLayout(title_layout)

        self.path_label = QLabel("Файл: -")
        self.path_label.setWordWrap(True)
        content_layout.addWidget(self.path_label)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.text_edit.setFont(QFont("Consolas", 10))
        # Устанавливаем правильную политику размера - не расширяется автоматически
        self.text_edit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        # Включаем горизонтальный скроллбар для длинных строк
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        content_layout.addWidget(self.text_edit, 1)
        self._highlighter = _JsonHighlighter(self.text_edit.document())

        self._set_placeholder()

    def _copy_json(self) -> None:
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "JSON превью", "Нет данных для копирования.")
            return
        self.text_edit.selectAll()
        self.text_edit.copy()
        self.text_edit.moveCursor(self.text_edit.textCursor().Start)
        QMessageBox.information(self, "JSON превью", "JSON скопирован в буфер обмена.")

    def _set_placeholder(self) -> None:
        self.text_edit.setPlainText("// Выберите тест-кейс, чтобы увидеть JSON")
        self.path_label.setText("Файл: -")
        self._current_path = None

    def clear(self) -> None:
        self._set_placeholder()

    def show_test_case(self, test_case: Optional[TestCase]) -> None:
        if not test_case:
            self._set_placeholder()
            return

        payload = test_case.to_dict()
        json_text = json.dumps(payload, ensure_ascii=False, indent=4)
        # Блокируем обновление геометрии при установке текста
        # чтобы предотвратить автоматическое изменение размеров панели
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(json_text)
        self.text_edit.blockSignals(False)

        filepath = getattr(test_case, "_filepath", None)
        if filepath:
            path_obj = Path(filepath)
            self.path_label.setText(f"Файл: {path_obj}")
            self._current_path = path_obj
        else:
            self.path_label.setText("Файл: (не сохранён)")
            self._current_path = None

