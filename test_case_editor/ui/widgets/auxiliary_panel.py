"""Дополнительная панель с переключаемыми разделами."""

from __future__ import annotations

from typing import Iterable, List, Optional
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal, QMargins
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QButtonGroup,
    QStackedLayout,
    QLabel,
    QSizePolicy,
    QFrame,
)

from .review_panel import ReviewPanel
from .json_preview_widget import JsonPreviewWidget
from .stats_panel import StatsPanel
from ...models import TestCase
from ..styles.ui_metrics import UI_METRICS


class AuxiliaryPanel(QWidget):
    """Правая панель с переключателями вкладок."""

    review_prompt_saved = pyqtSignal(str)
    review_enter_clicked = pyqtSignal(str, list)

    creation_prompt_saved = pyqtSignal(str)
    creation_enter_clicked = pyqtSignal(str, list)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        methodic_path: Optional[Path] = None,
        default_review_prompt: str = "",
        default_creation_prompt: str = "",
        creation_default_files: Optional[List[Path]] = None,
    ):
        super().__init__(parent)
        self._tabs_order = ["review", "creation", "json", "stats"]
        self._buttons: dict[str, QPushButton] = {}
        self._last_non_stats_tab = "review"
        self._methodic_path = methodic_path
        self._review_default_prompt = default_review_prompt
        self._creation_default_prompt = default_creation_prompt or "Создай ТТ"
        self._creation_default_files = creation_default_files or []
        self._last_creation_prompt_default = (self._creation_default_prompt or "").strip()

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
        )
        main_layout.setSpacing(UI_METRICS.section_spacing)

        button_row = self._create_button_row()
        main_layout.addLayout(button_row)

        self._stack = QStackedLayout()
        self._stack.setStackingMode(QStackedLayout.StackOne)

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

        # Вкладка статистики
        self.stats_panel = StatsPanel()
        self._stack.addWidget(self.stats_panel)

        main_layout.addLayout(self._stack, stretch=1)

        self.ensure_creation_defaults()
        self.select_tab("review")

    def _create_button_row(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(
            QMargins(
                UI_METRICS.base_spacing,
                0,
                UI_METRICS.base_spacing,
                0,
            )
        )
        layout.setSpacing(UI_METRICS.base_spacing)
        layout.setAlignment(Qt.AlignLeft)

        button_group = QButtonGroup(self)
        button_group.setExclusive(True)

        tabs = [
            ("review", "Ревью", "Панель ревью"),
            ("creation", "Создать ТК", "Создать ТК"),
            ("json", "JSON", "JSON превью"),
            ("stats", "Статистика", "Статистика"),
        ]

        for index, (tab_id, text, tooltip) in enumerate(tabs):
            button = QPushButton(text)
            button.setToolTip(tooltip)
            button.setCheckable(True)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            button.setMinimumHeight(UI_METRICS.control_min_height)
            button.setMinimumWidth(UI_METRICS.control_min_width)
            button.setCursor(Qt.PointingHandCursor)
            button_group.addButton(button, index)
            button.clicked.connect(lambda checked, idx=index: checked and self._stack.setCurrentIndex(idx))
            layout.addWidget(button)
            self._buttons[tab_id] = button

        return layout

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
            tab_id = "review"

        index = self._tabs_order.index(tab_id)
        self._stack.setCurrentIndex(index)

        button = self._buttons.get(tab_id)
        if button and not button.isChecked():
            button.setChecked(True)

        if tab_id == "creation":
            self.ensure_creation_defaults()
        if tab_id != "stats":
            self._last_non_stats_tab = tab_id

    def show_stats_tab(self):
        self.select_tab("stats")

    def restore_last_tab(self):
        self.select_tab(self._last_non_stats_tab or "review")

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

    def update_statistics(self, test_cases: List[TestCase]):
        if hasattr(self, "stats_panel"):
            self.stats_panel.update_statistics(test_cases)

    def set_panels_enabled(self, review_enabled: bool, creation_enabled: bool):
        self.review_panel.setEnabled(review_enabled)
        self.creation_panel.setEnabled(creation_enabled)
        if button := self._buttons.get("review"):
            button.setEnabled(review_enabled)
        if button := self._buttons.get("creation"):
            button.setEnabled(creation_enabled)


