"""Панель ревью для выбора файлов и ввода промта."""

from __future__ import annotations

from pathlib import Path
from typing import List

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
)
from PyQt5.QtCore import pyqtSignal, Qt


class ReviewPanel(QWidget):
    """Правая панель для подготовки ревью."""

    prompt_saved = pyqtSignal(str)
    enter_clicked = pyqtSignal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attachments: List[Path] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        title = QLabel("Панель ревью")
        title.setStyleSheet("color: #E1E3E6; font-size: 16pt; font-weight: 600;")
        layout.addWidget(title)

        # Блок прикрепленных файлов
        attachments_row = QHBoxLayout()
        attachments_row.setSpacing(10)

        self.attach_button = QPushButton("📎")
        self.attach_button.setToolTip("Прикрепить файлы")
        self.attach_button.setFixedSize(40, 40)
        self.attach_button.setStyleSheet(
            """
            QPushButton {
                background-color: #2B5278;
                border: 1px solid #3D6A98;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 18pt;
            }
            QPushButton:hover {
                background-color: #3D6A98;
            }
            """
        )
        self.attach_button.clicked.connect(self._choose_files)
        attachments_row.addWidget(self.attach_button, 0, Qt.AlignLeft)

        attachments_label = QLabel("Прикрепленные файлы:")
        attachments_label.setStyleSheet("color: #8B9099; font-weight: 600;")
        attachments_row.addWidget(attachments_label, 0, Qt.AlignVCenter)
        attachments_row.addStretch(1)
        layout.addLayout(attachments_row)

        self.attachments_list = QListWidget()
        self.attachments_list.setStyleSheet(
            """
            QListWidget {
                background-color: #1E2732;
                border: 1px solid #2B3945;
                border-radius: 8px;
                color: #E1E3E6;
            }
            QListWidget::item {
                padding: 6px 8px;
            }
            """
        )
        layout.addWidget(self.attachments_list)
        self._update_attachments_height()

        # Поле промта
        prompt_layout = QHBoxLayout()
        prompt_layout.setSpacing(10)

        prompt_label = QLabel("Промт")
        prompt_label.setStyleSheet("color: #8B9099; font-weight: 600;")
        prompt_layout.addWidget(prompt_label)

        self.save_prompt_button = QPushButton("Сохранить")
        self.save_prompt_button.setFixedHeight(32)
        self.save_prompt_button.setStyleSheet(
            """
            QPushButton {
                background-color: #2B5278;
                border: 1px solid #3D6A98;
                border-radius: 6px;
                color: #FFFFFF;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #3D6A98;
            }
            """
        )
        self.save_prompt_button.clicked.connect(self._save_prompt_clicked)
        prompt_layout.addWidget(self.save_prompt_button, 0, Qt.AlignRight)
        prompt_layout.addStretch(1)
        layout.addLayout(prompt_layout)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMinimumHeight(160)
        self.prompt_edit.setStyleSheet(
            """
            QTextEdit {
                background-color: #1E2732;
                border: 1px solid #2B3945;
                border-radius: 8px;
                color: #E1E3E6;
                padding: 10px;
                font-size: 11pt;
            }
            """
        )
        layout.addWidget(self.prompt_edit)

        # Кнопка Enter
        self.enter_button = QPushButton("Enter")
        self.enter_button.setMinimumHeight(45)
        self.enter_button.setStyleSheet(
            """
            QPushButton {
                background-color: #2B5278;
                border: 1px solid #3D6A98;
                border-radius: 8px;
                color: #FFFFFF;
                font-weight: 600;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #3D6A98;
            }
            QPushButton:pressed {
                background-color: #1D3F5F;
            }
            """
        )
        self.enter_button.clicked.connect(self._enter_clicked)
        layout.addWidget(self.enter_button, 0, Qt.AlignRight)

    # --- Публичные методы -------------------------------------------------

    def set_prompt_text(self, text: str):
        """Установить текст промта."""
        self.prompt_edit.setPlainText(text or "")

    def get_prompt_text(self) -> str:
        """Получить текущий текст промта."""
        return self.prompt_edit.toPlainText().strip()

    def clear_attachments(self):
        """Очистить список прикрепленных файлов."""
        self._attachments.clear()
        self.attachments_list.clear()

    # --- Внутренние обработчики -------------------------------------------

    def _choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы для ревью",
            "",
            "Все файлы (*.*)",
        )

        if not files:
            return

        self._attachments = [Path(path) for path in files]
        self.attachments_list.clear()
        for path in self._attachments:
            QListWidgetItem(str(path), self.attachments_list)
        self._update_attachments_height()

    def _save_prompt_clicked(self):
        text = self.get_prompt_text()
        self.prompt_saved.emit(text)

    def _enter_clicked(self):
        self.enter_clicked.emit(self.get_prompt_text(), [str(p) for p in self._attachments])

    def _update_attachments_height(self):
        """Адаптировать высоту списка прикрепленных файлов."""
        count = max(self.attachments_list.count(), 1)
        frame = self.attachments_list.frameWidth() * 2
        if self.attachments_list.count() > 0:
            metrics_height = self.attachments_list.sizeHintForRow(0)
        else:
            metrics_height = self.attachments_list.fontMetrics().height() + 12
        new_height = frame + metrics_height * count
        self.attachments_list.setFixedHeight(new_height)

