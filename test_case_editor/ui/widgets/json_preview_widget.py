"""Панель отображения JSON тест-кейса."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, QRegularExpression
from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPlainTextEdit,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
)

from ...models import TestCase


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

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("JSON превью")
        header.addWidget(title)
        header.addStretch(1)

        self.copy_button = QPushButton("Копировать")
        self.copy_button.setCursor(Qt.PointingHandCursor)
        self.copy_button.setFixedHeight(28)
        self.copy_button.clicked.connect(self._copy_json)  # type: ignore[attr-defined]
        header.addWidget(self.copy_button, 0, Qt.AlignRight)
        layout.addLayout(header)

        self.path_label = QLabel("Файл: -")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.text_edit.setFont(QFont("Consolas", 10))
        layout.addWidget(self.text_edit, 1)
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
        self.text_edit.setPlainText(json_text)

        filepath = getattr(test_case, "_filepath", None)
        if filepath:
            path_obj = Path(filepath)
            self.path_label.setText(f"Файл: {path_obj}")
            self._current_path = path_obj
        else:
            self.path_label.setText("Файл: (не сохранён)")
            self._current_path = None

