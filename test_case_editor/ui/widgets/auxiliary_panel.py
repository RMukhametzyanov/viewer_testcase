"""Дополнительная панель с переключаемыми разделами."""

from __future__ import annotations

from typing import Iterable, List, Optional
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QStackedLayout,
    QLabel,
    QSizePolicy,
    QFrame,
)

from .review_panel import ReviewPanel
from .json_preview_widget import JsonPreviewWidget
from .information_panel import InformationPanel
from .files_panel import FilesPanel
from .reports_panel import ReportsPanel
from ...models import TestCase
from ..styles.ui_metrics import UI_METRICS


class AuxiliaryPanel(QWidget):
    """Правая панель с переключателями вкладок."""

    review_prompt_saved = pyqtSignal(str)
    review_enter_clicked = pyqtSignal(str, list)

    creation_prompt_saved = pyqtSignal(str)
    creation_enter_clicked = pyqtSignal(str, list)

    information_data_changed = pyqtSignal()
    generate_report_requested = pyqtSignal()  # Сигнал для запроса генерации отчета
    generate_summary_report_requested = pyqtSignal()  # Сигнал для запроса генерации суммарного отчета
    tab_changed = pyqtSignal(str)  # Сигнал об изменении активной вкладки

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        methodic_path: Optional[Path] = None,
        default_review_prompt: str = "",
        default_creation_prompt: str = "",
        creation_default_files: Optional[List[Path]] = None,
    ):
        super().__init__(parent)
        self._tabs_order = ["information", "review", "creation", "json", "files", "reports"]
        self._methodic_path = methodic_path
        self._review_default_prompt = default_review_prompt
        self._creation_default_prompt = default_creation_prompt or "Создай ТТ"
        self._creation_default_files = creation_default_files or []
        self._last_creation_prompt_default = (self._creation_default_prompt or "").strip()

        self._setup_ui()

    def _setup_ui(self):
        # Устанавливаем правильную политику размера для панели
        # Preferred по горизонтали - не расширяется автоматически
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        
        # Теперь только контентная область без вертикальной панели с кнопками
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
        )
        main_layout.setSpacing(UI_METRICS.section_spacing)

        self._stack = QStackedLayout()
        self._stack.setStackingMode(QStackedLayout.StackOne)

        # Вкладка информации
        self.information_panel = InformationPanel()
        self.information_panel.data_changed.connect(self.information_data_changed.emit)
        self._stack.addWidget(self.information_panel)

        # Вкладка ревью
        self.review_panel = ReviewPanel(title_text="Панель ревью")
        self.review_panel.prompt_saved.connect(self.review_prompt_saved.emit)
        self.review_panel.enter_clicked.connect(self.review_enter_clicked.emit)
        self._stack.addWidget(self.review_panel)

        # Вкладка создания ТК
        self.creation_panel = ReviewPanel(title_text="Создать ТК")
        self.creation_panel.prompt_saved.connect(self.creation_prompt_saved.emit)
        self.creation_panel.enter_clicked.connect(self.creation_enter_clicked.emit)
        self._stack.addWidget(self.creation_panel)

        # Вкладка JSON превью
        self.json_panel = JsonPreviewWidget()
        self._stack.addWidget(self.json_panel)

        # Вкладка файлов
        self.files_panel = FilesPanel()
        self._stack.addWidget(self.files_panel)
        
        # Вкладка отчетности
        self.reports_panel = ReportsPanel()
        self.reports_panel.generate_report_requested.connect(self.generate_report_requested.emit)
        self.reports_panel.generate_summary_report_requested.connect(self.generate_summary_report_requested.emit)
        self._stack.addWidget(self.reports_panel)

        main_layout.addLayout(self._stack, stretch=1)

        self.ensure_creation_defaults()
        self.select_tab("information")

    @staticmethod
    def _build_placeholder(title: str) -> QWidget:
        container = QFrame()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addStretch()

        label = QLabel(title)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        comment = QLabel("Раздел находится в разработке.")
        comment.setAlignment(Qt.AlignCenter)
        layout.addWidget(comment)

        layout.addStretch()
        return container

    # ------------------------------------------------------------------ review

    def select_tab(self, tab_id: str):
        """Активировать вкладку по идентификатору."""
        if tab_id not in self._tabs_order:
            tab_id = "information"

        index = self._tabs_order.index(tab_id)
        self._stack.setCurrentIndex(index)

        # Отправляем сигнал об изменении вкладки (для обновления кнопок в toolbar)
        self.tab_changed.emit(tab_id)

        if tab_id == "creation":
            self.ensure_creation_defaults()

    # ------------------------------------------------------------------ information

    def set_information_test_case(self, test_case: Optional[TestCase]):
        """Установить тест-кейс для панели информации"""
        if hasattr(self, "information_panel"):
            self.information_panel.load_test_case(test_case)

    def update_information_test_case(self, test_case: TestCase):
        """Обновить тест-кейс данными из панели информации"""
        if hasattr(self, "information_panel") and test_case:
            self.information_panel.update_test_case(test_case)

    def set_information_edit_mode(self, enabled: bool):
        """Установить режим редактирования для панели информации"""
        if hasattr(self, "information_panel"):
            self.information_panel.set_edit_mode(enabled)

    # ------------------------------------------------------------------ files

    def set_files_test_case(self, test_case: Optional[TestCase]):
        """Установить тест-кейс для панели файлов"""
        if hasattr(self, "files_panel"):
            self.files_panel.load_test_case(test_case)
    
    # ------------------------------------------------------------------ reports

    def update_reports_panel(self):
        """Обновить панель отчетности"""
        if hasattr(self, "reports_panel"):
            self.reports_panel.refresh_reports()

    # ------------------------------------------------------------------ review

    def set_review_attachments(self, attachments: Iterable[Path]):
        self.review_panel.set_attachments(attachments)

    def set_review_prompt_text(self, text: str):
        self.review_panel.set_prompt_text(text)

    def clear_review_response(self):
        self.review_panel.clear_response()

    def set_review_loading_state(self, is_loading: bool):
        self.review_panel.set_loading_state(is_loading)

    def set_review_response_text(self, text: str):
        self.review_panel.set_response_text(text)

    def set_review_error(self, message: str):
        self.review_panel.set_response_text(message)
        self.review_panel.set_loading_state(False)

    def set_review_files(self, files: List[Path]):
        self.review_panel.set_attachments(files)

    # ---------------------------------------------------------------- creation

    def ensure_creation_defaults(self):
        existing = set(self.creation_panel.get_attachments())
        new_files: List[Path] = []

        if self._methodic_path and self._methodic_path.exists() and self._methodic_path not in existing:
            new_files.append(self._methodic_path)

        for extra in self._creation_default_files:
            if extra and extra.exists() and extra not in existing:
                new_files.append(extra)

        if new_files:
            self.creation_panel.add_attachments(new_files)

        current_prompt = (self.creation_panel.get_prompt_text() or "").strip()
        default_clean = (self._creation_default_prompt or "").strip()
        if not current_prompt or current_prompt == self._last_creation_prompt_default:
            self.creation_panel.set_prompt_text(self._creation_default_prompt)
        self.creation_panel.clear_response()
        self._last_creation_prompt_default = default_clean

    def set_creation_loading_state(self, is_loading: bool):
        self.creation_panel.set_loading_state(is_loading)

    def set_creation_response_text(self, text: str):
        self.creation_panel.set_response_text(text)

    def set_creation_default_prompt(self, text: str):
        self._creation_default_prompt = text or "Создай ТТ"
        self._last_creation_prompt_default = (self._creation_default_prompt or "").strip()
        self.creation_panel.set_prompt_text(self._creation_default_prompt)
        self.creation_panel.clear_response()

    # ---------------------------------------------------------------- JSON

    def set_json_test_case(self, test_case: Optional[TestCase]):
        if not hasattr(self, "json_panel"):
            return
        if test_case:
            self.json_panel.show_test_case(test_case)
        else:
            self.json_panel.clear()


    def set_panels_enabled(self, review_enabled: bool, creation_enabled: bool):
        """Установить доступность панелей Ревью и Создать ТК.
        
        Примечание: Доступность кнопок теперь управляется из main_window через toolbar.
        """
        self.review_panel.setEnabled(review_enabled)
        self.creation_panel.setEnabled(creation_enabled)

    def set_panels_visible(self, review_visible: bool, creation_visible: bool):
        """Установить видимость панелей Ревью и Создать ТК.
        
        Args:
            review_visible: True для показа панели Ревью, False для скрытия
            creation_visible: True для показа панели Создать ТК, False для скрытия
        
        Примечание: Видимость кнопок теперь управляется из main_window через toolbar.
        """
        # Если скрываем панели и текущая активная панель - одна из скрываемых, переключаемся на information
        current_index = self._stack.currentIndex()
        if not review_visible and current_index == self._tabs_order.index("review"):
            self.select_tab("information")
        if not creation_visible and current_index == self._tabs_order.index("creation"):
            self.select_tab("information")


